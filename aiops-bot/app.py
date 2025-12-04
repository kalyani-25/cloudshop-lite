from fastapi import FastAPI, Query
from datetime import datetime, timedelta, timezone
import boto3
import os
import time
import subprocess
import json
import re
from pydantic import BaseModel
# ---------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------
REGION = os.environ.get("AWS_REGION", "us-east-1")
LOG_GROUP = os.environ.get("LOG_GROUP", "/aws/eks/cloudshop-lite/cluster")


def get_logs_client():
    return boto3.client("logs", region_name=REGION)


def get_cw_client():
    return boto3.client("cloudwatch", region_name=REGION)

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _time_range(minutes: int = 15):
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=minutes)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000)


def _run_logs_query(query: str, minutes: int):
    start_ms, end_ms = _time_range(minutes)
    logs_client = get_logs_client()

    start_query = logs_client.start_query(
        logGroupName=LOG_GROUP,
        startTime=start_ms // 1000,
        endTime=end_ms // 1000,
        queryString=query,
    )
    qid = start_query["queryId"]

    while True:
        res = logs_client.get_query_results(queryId=qid)
        if res["status"] in ("Complete", "Failed", "Cancelled"):
            return res
        time.sleep(1)


def _results_to_rows(res):
    items = []
    for r in res.get("results", []):
        row = {f["field"]: f["value"] for f in r}
        items.append(row)
    return items


def _run_kubectl(args: list[str]):
    """
    Run a kubectl command and return a structured result with stdout/stderr/exit code.
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


app = FastAPI(title="CloudShop AI-Ops Bot")


# Request model for the chat endpoint
class ChatRequest(BaseModel):
    question: str
# ---------------------------------------------------------------------
# Base health
# ---------------------------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "aiops-bot",
        "region": REGION,
        "log_group": LOG_GROUP,
    }


@app.get("/ai/health")
def ai_health():
    return health()


# ---------------------------------------------------------------------
# 1) Recent raw error logs
# ---------------------------------------------------------------------
@app.get("/logs/errors")
def recent_errors(minutes: int = 15, limit: int = 50):
    query = f"""
    fields @timestamp, @message, @logStream
    | filter @message like /ERROR|Error|Exception/
    | sort @timestamp desc
    | limit {limit}
    """
    res = _run_logs_query(query, minutes)
    items = _results_to_rows(res)
    return {"minutes": minutes, "count": len(items), "results": items}


@app.get("/ai/logs/errors")
def ai_recent_errors(minutes: int = 15, limit: int = 50):
    return recent_errors(minutes=minutes, limit=limit)


# ---------------------------------------------------------------------
# 2) Error summary per service
# ---------------------------------------------------------------------
@app.get("/logs/error_summary")
def error_summary(minutes: int = 30):
    services = ["catalog", "orders", "users"]
    summary = {}

    for svc in services:
        svc_query = f"""
        fields @timestamp, @message, @logStream
        | filter @message like /ERROR|Error|Exception/
        | filter @logStream like /{svc}/
        | stats count() as errors
        """
        svc_res = _run_logs_query(svc_query, minutes)
        rows = _results_to_rows(svc_res)
        summary[svc] = int(rows[0].get("errors", 0)) if rows else 0

    return {"lookback_minutes": minutes, "summary": summary}


@app.get("/ai/logs/error_summary")
def ai_error_summary(minutes: int = 30):
    return error_summary(minutes=minutes)


# ---------------------------------------------------------------------
# 3) Service-specific errors
# ---------------------------------------------------------------------
@app.get("/logs/service_errors")
def service_errors(
    service: str = Query(..., description="Service name: catalog, orders, users, etc."),
    minutes: int = 30,
    limit: int = 50,
):
    query = f"""
    fields @timestamp, @message, @logStream
    | filter @message like /ERROR|Error|Exception/
    | filter @logStream like /{service}/
    | sort @timestamp desc
    | limit {limit}
    """
    res = _run_logs_query(query, minutes)
    items = _results_to_rows(res)
    status = "Complete" if res.get("status") == "Complete" else res.get(
        "status", "Unknown"
    )
    return {
        "lookback_minutes": minutes,
        "service": service,
        "status": status,
        "results": items,
    }


@app.get("/ai/logs/service_errors")
def ai_service_errors(
    service: str = Query(..., description="Service name: catalog, orders, users, etc."),
    minutes: int = 30,
    limit: int = 50,
):
    return service_errors(service=service, minutes=minutes, limit=limit)


# ---------------------------------------------------------------------
# 4) Top endpoints by request count
# ---------------------------------------------------------------------
@app.get("/logs/top_endpoints")
def top_endpoints(minutes: int = 30, limit: int = 10):
    query = f"""
    fields @timestamp, requestURI
    | filter ispresent(requestURI)
    | stats count() as hits by requestURI
    | sort hits desc
    | limit {limit}
    """
    res = _run_logs_query(query, minutes)
    rows = _results_to_rows(res)
    endpoints = [
        {"endpoint": r.get("requestURI", "unknown"), "hits": int(r.get("hits", 0))}
        for r in rows
    ]
    return {"lookback_minutes": minutes, "endpoints": endpoints}


@app.get("/ai/logs/top_endpoints")
def ai_top_endpoints(minutes: int = 30, limit: int = 10):
    return top_endpoints(minutes=minutes, limit=limit)


# ---------------------------------------------------------------------
# 5) CPU metric
# ---------------------------------------------------------------------
@app.get("/metrics/cpu")
def cpu_utilization(
    deployment: str = Query("orders-deployment"),
    namespace: str = Query("cloudshop"),
    period: int = 60,
    minutes: int = 15,
):
    end = datetime.utcnow()
    start = end - timedelta(minutes=minutes)
    cw_client = get_cw_client()

    resp = cw_client.get_metric_statistics(
        Namespace="ContainerInsights",
        MetricName="pod_cpu_utilization",
        Dimensions=[
            {"Name": "ClusterName", "Value": "cloudshop-lite"},
            {"Name": "Namespace", "Value": namespace},
            {"Name": "PodName", "Value": deployment},
        ],
        StartTime=start,
        EndTime=end,
        Period=period,
        Statistics=["Average"],
    )

    points = sorted(resp.get("Datapoints", []), key=lambda x: x["Timestamp"])
    return {
        "metric": "pod_cpu_utilization",
        "namespace": namespace,
        "deployment": deployment,
        "datapoints": [
            {"timestamp": p["Timestamp"].isoformat(), "avg": p["Average"]}
            for p in points
        ],
    }


@app.get("/ai/metrics/cpu")
def ai_cpu_utilization(
    deployment: str = Query("orders-deployment"),
    namespace: str = "cloudshop",
    period: int = 60,
    minutes: int = 15,
):
    return cpu_utilization(
        deployment=deployment, namespace=namespace, period=period, minutes=minutes
    )


# ---------------------------------------------------------------------
# 6) K8s observability & operations
# ---------------------------------------------------------------------
@app.get("/k8s/pod_status")
def k8s_pod_status(namespace: str = "cloudshop"):
    """
    Get status of all pods in a namespace.
    """
    try:
        result = subprocess.run(
            ["kubectl", "get", "pods", "-n", namespace, "-o", "json"],
            capture_output=True,
            text=True,
            check=False,
        )
        stdout = result.stdout.strip()
        parsed = {}
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


@app.get("/ai/k8s/pod_status")
def ai_k8s_pod_status(namespace: str = "cloudshop"):
    return k8s_pod_status(namespace=namespace)


@app.post("/k8s/restart_deployment")
def k8s_restart_deployment(deployment: str, namespace: str = "cloudshop"):
    """
    Restart a Kubernetes deployment.
    """
    return _run_kubectl(
        ["rollout", "restart", f"deployment/{deployment}", "-n", namespace]
    )


@app.post("/ai/k8s/restart_deployment")
def ai_k8s_restart_deployment(deployment: str, namespace: str = "cloudshop"):
    return k8s_restart_deployment(deployment=deployment, namespace=namespace)


@app.post("/k8s/scale_deployment")
def k8s_scale_deployment(
    deployment: str, replicas: int, namespace: str = "cloudshop"
):
    """
    Scale a Kubernetes deployment.
    """
    return _run_kubectl(
        ["scale", f"deployment/{deployment}", f"--replicas={replicas}", "-n", namespace]
    )


@app.post("/ai/k8s/scale_deployment")
def ai_k8s_scale_deployment(
    deployment: str, replicas: int, namespace: str = "cloudshop"
):
    return k8s_scale_deployment(
        deployment=deployment, replicas=replicas, namespace=namespace
    )


@app.get("/k8s/rollout_status")
def k8s_rollout_status(
    deployment: str,
    namespace: str = "cloudshop",
    timeout_seconds: int = 120,
):
    """
    Get rollout status for a deployment.
    Equivalent to: kubectl rollout status deployment/<deployment> -n <namespace> --timeout=<timeout_seconds>s
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


@app.get("/ai/k8s/rollout_status")
def ai_k8s_rollout_status(
    deployment: str,
    namespace: str = "cloudshop",
    timeout_seconds: int = 120,
):
    return k8s_rollout_status(
        deployment=deployment, namespace=namespace, timeout_seconds=timeout_seconds
    )


@app.post("/k8s/self_heal_orders")
def k8s_self_heal_orders(
    deployment: str = "orders-deployment",
    namespace: str = "cloudshop",
    minutes: int = 30,
    timeout_seconds: int = 120,
):
    """
    Self-heal flow for the orders service:

    1. Check error_summary for the last N minutes.
    2. If orders has non-zero errors:
        a. Restart the deployment.
        b. Wait for rollout status.
        c. Check error_summary again.
    """
    steps = {}

    # 1. Pre-check: error summary
    try:
        pre = error_summary(minutes=minutes)
        steps["pre_error_summary"] = pre
        orders_errors_before = pre.get("summary", {}).get("orders", 0)
    except Exception as e:
        steps["pre_error_summary_error"] = str(e)
        orders_errors_before = None

    if orders_errors_before is not None and orders_errors_before == 0:
        return {
            "status": "no_action_needed",
            "reason": "Orders service has 0 errors in the last period.",
            "deployment": deployment,
            "namespace": namespace,
            "orders_errors_before": orders_errors_before,
            "orders_errors_after": orders_errors_before,
            "steps": steps,
        }

    # 2a. Restart deployment
    steps["restart"] = _run_kubectl(
        ["rollout", "restart", f"deployment/{deployment}", "-n", namespace]
    )

    # 2b. Rollout status
    steps["rollout_status"] = _run_kubectl(
        [
            "rollout",
            "status",
            f"deployment/{deployment}",
            "-n",
            namespace,
            f"--timeout={timeout_seconds}s",
        ]
    )

    # 2c. Post-check: error summary again
    try:
        post = error_summary(minutes=minutes)
        steps["post_error_summary"] = post
        orders_errors_after = post.get("summary", {}).get("orders", 0)
    except Exception as e:
        steps["post_error_summary_error"] = str(e)
        orders_errors_after = None

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


@app.post("/ai/k8s/self_heal_orders")
def ai_k8s_self_heal_orders(
    deployment: str = "orders-deployment",
    namespace: str = "cloudshop",
    minutes: int = 30,
    timeout_seconds: int = 120,
):
    return k8s_self_heal_orders(
        deployment=deployment,
        namespace=namespace,
        minutes=minutes,
        timeout_seconds=timeout_seconds,
    )


# ---------------------------------------------------------------------
# 7) AI-Ops Chatbot endpoint (natural language, demo friendly)
# ---------------------------------------------------------------------
def _guess_deployment_from_question(q: str) -> str:
    """Map 'orders', 'catalog', 'users' in the question to a deployment name."""
    if "orders" in q:
        return "orders-deployment"
    if "catalog" in q:
        return "catalog-deployment"
    if "users" in q or "user service" in q:
        return "users-deployment"
    # fallback: just use orders-deployment
    return "orders-deployment"


@app.post("/ai/chat")
def ai_chat(req: ChatRequest):
    """
    Simple rule-based AI-Ops assistant.
    It looks at the user's question and calls the right helper APIs,
    then returns a friendly, human-style explanation.
    """
    q = (req.question or "").lower().strip()

    # Try to extract "X minutes" from the question
    m = re.search(r"(\d+)\s*(min|mins|minute|minutes)?", q)
    minutes = int(m.group(1)) if m else 30
    limit = 5

    # ------------------------------------------------------------------
    # 1) Error summary across services
    # ------------------------------------------------------------------
    if "error" in q and ("summary" in q or "overall" in q or "system" in q):
        res = error_summary(minutes=minutes)
        summary = res.get("summary", {})
        if not summary:
            answer = (
                f"I checked the CloudWatch logs for the last {minutes} minutes, "
                "but I didn’t see any errors recorded for catalog, orders, or users."
            )
        else:
            parts = []
            for svc, count in summary.items():
                if count == 0:
                    parts.append(f"{svc}: 0 errors ✅")
                else:
                    parts.append(f"{svc}: {count} errors ⚠️")

            bullet_lines = "\n".join(f"- {p}" for p in parts)

            answer = (
                f"Here’s the error summary for the last {minutes} minutes:\n\n"
                f"{bullet_lines}\n\n"
                "This lets you quickly see which service is noisy."
            )

        return {
            "question": req.question,
            "minutes": minutes,
            "intent": "error_summary",
            "endpoint": "/ai/logs/error_summary",
            "answer": answer,
            "data": res,
        }

    # ------------------------------------------------------------------
    # 2) Service-specific errors
    # ------------------------------------------------------------------
    if "errors" in q or "error" in q:
        svc = None
        if "orders" in q:
            svc = "orders"
        elif "catalog" in q:
            svc = "catalog"
        elif "users" in q or "user service" in q:
            svc = "users"

        if svc:
            res = service_errors(service=svc, minutes=minutes, limit=limit)
            items = res.get("results", [])
            count = len(items)

            if count == 0:
                answer = (
                    f"I checked the logs for **{svc}** over the last {minutes} minutes "
                    "and didn’t see any matching error entries. Looks clean ✅"
                )
            else:
                answer_lines = [
                    f"I inspected recent errors for **{svc}** in the last {minutes} minutes.",
                    f"I found **{count}** recent error log entries. Here are the most recent ones:",
                    "",
                ]
                for i, row in enumerate(items[:3]):
                    ts = row.get("@timestamp", "unknown time")
                    msg = row.get("@message", "").strip()
                    if len(msg) > 120:
                        msg = msg[:120] + "..."
                    answer_lines.append(f"{i+1}. [{ts}] {msg}")

                answer_lines.append(
                    "\nYou can dig deeper by looking at the full log entries in CloudWatch."
                )
                answer = "\n".join(answer_lines)

            return {
                "question": req.question,
                "minutes": minutes,
                "intent": "service_errors",
                "service": svc,
                "endpoint": "/ai/logs/service_errors",
                "answer": answer,
                "data": res,
            }

    # ------------------------------------------------------------------
    # 3) Top endpoints by traffic
    # ------------------------------------------------------------------
    if "top" in q and ("endpoint" in q or "endpoints" in q or "traffic" in q or "requests" in q):
        res = top_endpoints(minutes=minutes, limit=limit)
        eps = res.get("endpoints", [])
        if not eps:
            answer = (
                f"In the last {minutes} minutes I didn’t see any HTTP traffic in the logs."
            )
        else:
            lines = []
            for e in eps:
                ep = e.get("endpoint", "unknown")
                hits = e.get("hits", 0)
                lines.append(f"- `{ep}` → {hits} hits")
            answer = (
                f"Here are the **top {len(eps)} endpoints by traffic** in the last {minutes} minutes:\n\n"
                + "\n".join(lines)
                + "\n\nThis helps you see which parts of CloudShop are getting the most load."
            )
        return {
            "question": req.question,
            "minutes": minutes,
            "intent": "top_endpoints",
            "endpoint": "/ai/logs/top_endpoints",
            "answer": answer,
            "data": res,
        }

    # ------------------------------------------------------------------
    # 4) Pod status / health
    # ------------------------------------------------------------------
    if ("pod" in q or "pods" in q or "kubernetes" in q or "k8s" in q) and (
        "status" in q or "health" in q or "ready" in q
    ):
        res = k8s_pod_status(namespace="cloudshop")
        items = (res.get("stdout_json") or {}).get("items", [])
        not_ready = []
        for p in items:
            name = p.get("metadata", {}).get("name", "unknown")
            phase = p.get("status", {}).get("phase", "Unknown")
            conditions = p.get("status", {}).get("conditions", []) or []
            ready_cond = next(
                (c for c in conditions if c.get("type") == "Ready"), None
            )
            ready = bool(ready_cond and ready_cond.get("status") == "True")
            if phase != "Running" or not ready:
                not_ready.append((name, phase))

        if not_ready:
            lines = [f"- {name} (phase = {phase})" for name, phase in not_ready]
            answer = (
                "I checked the Kubernetes pods in the **cloudshop** namespace.\n\n"
                "Some pods are **not Ready**:\n"
                + "\n".join(lines)
                + "\n\nYou may want to investigate these pods further."
            )
        else:
            answer = (
                "I checked the Kubernetes pods in the **cloudshop** namespace.\n\n"
                "✅ All pods appear to be Running and Ready."
            )

        return {
            "question": req.question,
            "intent": "pod_status",
            "endpoint": "/ai/k8s/pod_status",
            "answer": answer,
            "data": res,
        }

    # ------------------------------------------------------------------
    # 5) Restart deployment (generic tool)
    # ------------------------------------------------------------------
    if "restart" in q and ("deployment" in q or "service" in q):
        deployment = _guess_deployment_from_question(q)
        res = k8s_restart_deployment(deployment=deployment, namespace="cloudshop")

        answer = (
            f"I triggered a rollout restart for the **{deployment}** deployment "
            "in the `cloudshop` namespace.\n\n"
            f"- Command: `{res.get('cmd')}`\n"
            f"- Exit code: {res.get('returncode')}\n"
        )
        if res.get("stderr"):
            answer += f"- stderr: {res.get('stderr')}\n"

        return {
            "question": req.question,
            "intent": "restart_deployment",
            "deployment": deployment,
            "endpoint": "/ai/k8s/restart_deployment",
            "answer": answer,
            "data": res,
        }

    # ------------------------------------------------------------------
    # 6) Scale deployment (generic tool)
    # ------------------------------------------------------------------
    if "scale" in q and ("deployment" in q or "service" in q):
        deployment = _guess_deployment_from_question(q)
        replicas_match = re.search(r"(\d+)\s*(replica|replicas)?", q)
        replicas = int(replicas_match.group(1)) if replicas_match else 2

        res = k8s_scale_deployment(
            deployment=deployment,
            replicas=replicas,
            namespace="cloudshop",
        )

        answer = (
            f"I scaled the **{deployment}** deployment in `cloudshop` to **{replicas}** replicas.\n\n"
            f"- Command: `{res.get('cmd')}`\n"
            f"- Exit code: {res.get('returncode')}\n"
        )
        if res.get("stderr"):
            answer += f"- stderr: {res.get('stderr')}\n"

        return {
            "question": req.question,
            "intent": "scale_deployment",
            "deployment": deployment,
            "replicas": replicas,
            "endpoint": "/ai/k8s/scale_deployment",
            "answer": answer,
            "data": res,
        }

    # ------------------------------------------------------------------
    # 7) Rollout status (generic tool)
    # ------------------------------------------------------------------
    if "rollout status" in q or "deployment status" in q:
        deployment = _guess_deployment_from_question(q)
        res = k8s_rollout_status(
            deployment=deployment, namespace="cloudshop", timeout_seconds=120
        )

        answer = (
            f"I checked the rollout status for **{deployment}** in `cloudshop`.\n\n"
            f"- Command: `{res.get('cmd')}`\n"
            f"- Exit code: {res.get('returncode')}\n"
        )
        if res.get("stdout"):
            answer += f"- Output:\n{res.get('stdout')}\n"
        if res.get("stderr"):
            answer += f"\n- stderr:\n{res.get('stderr')}\n"

        return {
            "question": req.question,
            "intent": "rollout_status",
            "deployment": deployment,
            "endpoint": "/ai/k8s/rollout_status",
            "answer": answer,
            "data": res,
        }

    # ------------------------------------------------------------------
    # 8) Self-heal orders service
    # ------------------------------------------------------------------
    if ("self heal" in q) or ("self-heal" in q) or ("fix orders" in q) or (
        "restart orders" in q
    ):
        res = k8s_self_heal_orders()
        status = res.get("status")
        before = res.get("orders_errors_before")
        after = res.get("orders_errors_after")

        answer = (
            "I ran the **self-heal playbook** for the orders service:\n\n"
            f"- Initial orders error count: {before}\n"
            f"- Final orders error count: {after}\n"
            f"- Overall self-heal status: **{status}**\n\n"
            "Behind the scenes, this restarted the orders deployment, waited for the rollout, "
            "and then re-checked the error summary."
        )

        return {
            "question": req.question,
            "intent": "self_heal_orders",
            "endpoint": "/ai/k8s/self_heal_orders",
            "answer": answer,
            "data": res,
        }

    # ------------------------------------------------------------------
    # 9) Fallback / help
    # ------------------------------------------------------------------
    help_text = (
        "I didn’t quite understand that request yet.\n\n"
        "Here are the AI-Ops tools I support:\n\n"
        "- error_summary: Get error counts per service for the last N minutes.\n"
        "  (wraps GET /logs/error_summary?minutes=...)\n"
        "- top_endpoints: Get top endpoints by traffic for the last N minutes.\n"
        "  (wraps GET /logs/top_endpoints?minutes=&limit=)\n"
        "- service_errors: Get error events for a specific service.\n"
        "  (wraps GET /logs/service_errors?service=&minutes=)\n"
        "- restart_deployment: Restart a Kubernetes deployment.\n"
        "  (kubectl rollout restart deployment/<deployment> -n <namespace>)\n"
        "- scale_deployment: Scale a deployment to N replicas.\n"
        "  (kubectl scale deployment/<deployment> --replicas=<replicas> -n <namespace>)\n"
        "- rollout_status: Get rollout status for a deployment.\n"
        "  (kubectl rollout status deployment/<deployment> -n <namespace> --timeout=<seconds>s)\n"
        "- pod_status: Get status of all pods in a namespace.\n"
        "  (kubectl get pods -n <namespace> -o json)\n"
        "- self_heal_orders: Automatic self-heal for the orders service.\n"
        "  (check errors → restart → wait for rollout → re-check errors)\n\n"
        "Try questions like:\n"
        "- \"Show error summary for last 30 minutes\"\n"
        "- \"Show orders service errors\"\n"
        "- \"What are the top endpoints?\"\n"
        "- \"Check pod status\"\n"
        "- \"Restart orders deployment\"\n"
        "- \"Scale orders deployment to 3 replicas\"\n"
        "- \"Check rollout status of orders deployment\"\n"
        "- \"Self heal orders\"\n"
    )

    return {
        "question": req.question,
        "intent": "unknown",
        "answer": help_text,
        "data": {},
    }
