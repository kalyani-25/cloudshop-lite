from typing import Any, Dict
import os
import subprocess
import json

import requests
from mcp.server.fastmcp import FastMCP

# -------------------------------------------------------------------
# Config: AI-Ops FastAPI base URL
# -------------------------------------------------------------------
# Default is  current AI-Ops LoadBalancer.
# can override it with env var AIOPS_BASE_URL if needed.
AIOPS_BASE = os.getenv(
    "AIOPS_BASE_URL",
    "http://aec05544a21c3462b9e50aecb6261598-1292359421.us-east-1.elb.amazonaws.com",
)

# Create MCP server
mcp = FastMCP("CloudShop AI-Ops MCP", json_response=True)


# -------------------------------------------------------------------
# Helper to call existing AI-Ops REST endpoints
# -------------------------------------------------------------------
def _get_json(path: str, params: Dict[str, Any]) -> Any:
    """Call the existing AI-Ops REST API and return JSON."""
    url = f"{AIOPS_BASE}{path}"
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    return resp.json()


# -------------------------------------------------------------------
# Helper: Run kubectl commands for K8s operations
# -------------------------------------------------------------------
def _run_kubectl(args: list[str]) -> Dict[str, Any]:
    """
    Run a kubectl command and return a structured result
    with stdout/stderr/exit code so the LLM can reason about it.
    """
    try:
        result = subprocess.run(
            ["kubectl"] + args,
            capture_output=True,
            text=True,
            check=False,
        )
        return {
            "cmd": "kubectl " + " ".join(args),
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except Exception as e:
        return {
            "cmd": "kubectl " + " ".join(args),
            "error": str(e),
        }


# -------------------------------------------------------------------
# AI-Ops log/metrics tools
# -------------------------------------------------------------------
@mcp.tool()
def error_summary(minutes: int = 30) -> Any:
    """
    Get error counts per service for the last N minutes.
    Wraps GET /logs/error_summary?minutes=...
    """
    return _get_json("/logs/error_summary", {"minutes": minutes})


@mcp.tool()
def top_endpoints(minutes: int = 30, limit: int = 5) -> Any:
    """
    Get top endpoints by traffic for the last N minutes.
    Wraps GET /logs/top_endpoints?minutes=&limit=
    """
    return _get_json("/logs/top_endpoints", {"minutes": minutes, "limit": limit})


@mcp.tool()
def service_errors(service: str, minutes: int = 30) -> Any:
    """
    Get error events for a specific service over the last N minutes.
    Wraps GET /logs/service_errors?service=&minutes=
    """
    return _get_json(
        "/logs/service_errors",
        {"service": service, "minutes": minutes},
    )


# -------------------------------------------------------------------
# Kubernetes operations tools
# -------------------------------------------------------------------
@mcp.tool()
def restart_deployment(deployment: str, namespace: str = "cloudshop") -> Any:
    """
    Restart a Kubernetes deployment in the given namespace.

    Equivalent to:
      kubectl rollout restart deployment/<deployment> -n <namespace>
    """
    return _run_kubectl(
        ["rollout", "restart", f"deployment/{deployment}", "-n", namespace]
    )


@mcp.tool()
def scale_deployment(
    deployment: str,
    replicas: int,
    namespace: str = "cloudshop",
) -> Any:
    """
    Scale a Kubernetes deployment to the desired number of replicas.

    Equivalent to:
      kubectl scale deployment/<deployment> --replicas=<replicas> -n <namespace>
    """
    return _run_kubectl(
        ["scale", f"deployment/{deployment}", f"--replicas={replicas}", "-n", namespace]
    )


@mcp.tool()
def rollout_status(
    deployment: str,
    namespace: str = "cloudshop",
    timeout_seconds: int = 60,
) -> Any:
    """
    Get rollout status for a deployment.

    Equivalent to:
      kubectl rollout status deployment/<deployment> -n <namespace> --timeout=<timeout_seconds>s
    """
    return _run_kubectl(
        [
            "rollout",
            "status",
            f"deployment/{deployment}",
            "-n",
            namespace,
            f"--timeout={timeout_seconds}s",
        ]
    )


# -------------------------------------------------------------------
# Kubernetes observability tools
# -------------------------------------------------------------------
@mcp.tool()
def pod_status(namespace: str = "cloudshop") -> Any:
    """
    Get status of all pods in a namespace, returning parsed JSON plus raw info.

    Equivalent to:
      kubectl get pods -n <namespace> -o json
    """
    try:
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = result.stdout.strip()
        parsed: Any = {}
        if stdout:
            try:
                parsed = json.loads(stdout)
            except json.JSONDecodeError:
                parsed = {"parse_error": "Failed to decode JSON", "raw": stdout}

        return {
            "cmd": f"kubectl get pods -n {namespace} -o json",
            "returncode": result.returncode,
            "stdout_json": parsed,
            "stderr": result.stderr.strip(),
        }
    except Exception as e:
        return {
            "cmd": f"kubectl get pods -n {namespace} -o json",
            "error": str(e),
        }


# -------------------------------------------------------------------
# One-shot AI-Ops action: self-heal orders service
# -------------------------------------------------------------------
@mcp.tool()
def self_heal_orders(
    deployment: str = "orders-deployment",
    namespace: str = "cloudshop",
    minutes: int = 30,
    timeout_seconds: int = 120,
) -> Any:
    """
    Self-heal flow for the orders service:

    1. Check error_summary for the last N minutes.
    2. If orders has non-zero errors:
        a. Restart the deployment.
        b. Wait for rollout_status to complete (or timeout).
        c. Check error_summary again.
    3. Return a structured summary of all steps.
    """

    steps: Dict[str, Any] = {}

    # 1. Pre-check: error summary
    try:
        pre_errors = _get_json("/logs/error_summary", {"minutes": minutes})
        steps["pre_error_summary"] = pre_errors
        orders_errors_before = pre_errors.get("orders", 0)
    except Exception as e:
        steps["pre_error_summary_error"] = str(e)
        orders_errors_before = None

    # If we could read error counts and there are no errors, no action needed
    if orders_errors_before is not None and orders_errors_before == 0:
        return {
            "status": "no_action_needed",
            "reason": "Orders service has 0 errors in the last period.",
            "details": steps,
        }

    # 2a. Restart deployment
    restart_result = _run_kubectl(
        ["rollout", "restart", f"deployment/{deployment}", "-n", namespace]
    )
    steps["restart"] = restart_result

    # 2b. Check rollout status
    status_result = _run_kubectl(
        [
            "rollout",
            "status",
            f"deployment/{deployment}",
            "-n",
            namespace,
            f"--timeout={timeout_seconds}s",
        ]
    )
    steps["rollout_status"] = status_result

    # 2c. Post-check: error summary again
    try:
        post_errors = _get_json("/logs/error_summary", {"minutes": minutes})
        steps["post_error_summary"] = post_errors
        orders_errors_after = post_errors.get("orders", 0)
    except Exception as e:
        steps["post_error_summary_error"] = str(e)
        orders_errors_after = None

    # Final status
    final_status = "completed"
    if orders_errors_after is not None and orders_errors_after > 0:
        final_status = "completed_but_errors_still_present"

    return {
        "status": final_status,
        "deployment": deployment,
        "namespace": namespace,
        "orders_errors_before": orders_errors_before,
        "orders_errors_after": orders_errors_after,
        "steps": steps,
    }


# -------------------------------------------------------------------
# Entry point (HTTP transport for MCP Inspector)
# -------------------------------------------------------------------
if __name__ == "__main__":
    # HTTP transport so MCP Inspector / other clients can connect via URL
    mcp.run(transport="streamable-http")
