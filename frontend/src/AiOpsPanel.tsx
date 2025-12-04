import React, { useEffect, useState } from "react";

type ErrorSummary = Record<string, number>;

type TopEndpoint = {
  endpoint: string;
  hits: number;
};

type PodStatus = {
  cmd: string;
  returncode: number;
  stdout_json: {
    items?: Array<{
      metadata?: { name?: string };
      status?: { phase?: string; conditions?: any[]; containerStatuses?: any[] };
    }>;
  };
  stderr?: string;
};

type SelfHealResult = {
  status: string;
  deployment: string;
  namespace: string;
  orders_errors_before: number | null;
  orders_errors_after: number | null;
  steps: any;
};

const API_BASE =
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : "";

const AIOPS_BASE =
  import.meta.env.VITE_AIOPS_BASE_URL !== undefined &&
  import.meta.env.VITE_AIOPS_BASE_URL !== ""
    ? import.meta.env.VITE_AIOPS_BASE_URL
    : `${API_BASE}/ai`;

function aiUrl(path: string) {
  // path like "/logs/error_summary"
  return `${AIOPS_BASE}${path}`;
}

export const AiOpsPanel: React.FC = () => {
  const [errorSummary, setErrorSummary] = useState<ErrorSummary | null>(null);
  const [topEndpoints, setTopEndpoints] = useState<TopEndpoint[] | null>(null);
  const [podStatus, setPodStatus] = useState<PodStatus | null>(null);
  const [selfHealResult, setSelfHealResult] = useState<SelfHealResult | null>(null);

  const [loading, setLoading] = useState(false);
  const [healLoading, setHealLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function fetchAll() {
    try {
      setLoading(true);
      setError(null);

      const [errRes, topRes, podRes] = await Promise.all([
        fetch(aiUrl("/logs/error_summary?minutes=30")),
        fetch(aiUrl("/logs/top_endpoints?minutes=30&limit=5")),
        fetch(aiUrl("/k8s/pod_status?namespace=cloudshop")),
      ]);

      if (!errRes.ok || !topRes.ok || !podRes.ok) {
        throw new Error("One of the AI-Ops API calls failed");
      }

      const errJson = await errRes.json();
      const topJson = await topRes.json();
      const podJson = await podRes.json();

      // error_summary is already a map {service: count}
      setErrorSummary(errJson);

      // top_endpoints returns {lookback_minutes, endpoints: [{endpoint, hits}]}
      setTopEndpoints(topJson.endpoints || []);

      setPodStatus(podJson);
    } catch (e: any) {
      console.error(e);
      setError(e.message || "Failed to load AI-Ops data");
    } finally {
      setLoading(false);
    }
  }

  async function triggerSelfHeal() {
    try {
      setHealLoading(true);
      setError(null);
      setSelfHealResult(null);

      const res = await fetch(aiUrl("/k8s/self_heal_orders"), {
        method: "POST",
      });

      if (!res.ok) {
        throw new Error(`Self-heal failed with status ${res.status}`);
      }

      const json = await res.json();
      setSelfHealResult(json);

      // Refresh panels after healing
      fetchAll();
    } catch (e: any) {
      console.error(e);
      setError(e.message || "Failed to self-heal orders");
    } finally {
      setHealLoading(false);
    }
  }

  useEffect(() => {
    fetchAll();
  }, []);

  // Helper to summarize pods not Ready
  const pods = podStatus?.stdout_json?.items || [];
  const notReadyPods = pods.filter((p) => {
    const phase = p.status?.phase;
    if (phase !== "Running") return true;
    // check Ready condition
    const conditions = p.status?.conditions || [];
    const readyCond = conditions.find((c: any) => c.type === "Ready");
    return readyCond && readyCond.status !== "True";
  });

  return (
    <div className="aiops-panel" style={{ border: "1px solid #444", borderRadius: 8, padding: 16, marginTop: 24 }}>
      <h2>🧠 AI-Ops Dashboard</h2>

      {loading && <p>Loading AI-Ops data…</p>}
      {error && <p style={{ color: "red" }}>Error: {error}</p>}

      <button onClick={fetchAll} disabled={loading} style={{ marginBottom: 12 }}>
        🔄 Refresh status
      </button>

      {/* Error Summary */}
      <section style={{ marginBottom: 16 }}>
        <h3>❗ Error summary (last 30 min)</h3>
        {!errorSummary && <p>No data yet.</p>}
        {errorSummary && (
          <ul>
            {Object.entries(errorSummary).map(([service, count]) => (
              <li key={service}>
                <strong>{service}</strong>: {count}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Top Endpoints */}
      <section style={{ marginBottom: 16 }}>
        <h3>🚦 Top endpoints (last 30 min)</h3>
        {!topEndpoints && <p>No data yet.</p>}
        {topEndpoints && (
          <ol>
            {topEndpoints.map((ep) => (
              <li key={ep.endpoint}>
                <code>{ep.endpoint}</code> — {ep.hits} hits
              </li>
            ))}
          </ol>
        )}
      </section>

      {/* Pod Status */}
      <section style={{ marginBottom: 16 }}>
        <h3>📦 Pod status (namespace: cloudshop)</h3>
        {podStatus && (
          <>
            <p>
              Command: <code>{podStatus.cmd}</code>
            </p>
            {notReadyPods.length === 0 ? (
              <p>✅ All pods are Ready.</p>
            ) : (
              <>
                <p>⚠ Pods NOT Ready: {notReadyPods.length}</p>
                <ul>
                  {notReadyPods.map((p) => (
                    <li key={p.metadata?.name}>
                      <code>{p.metadata?.name}</code> — phase: {p.status?.phase}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </section>

      {/* Self-Heal */}
      <section>
        <h3>🛠 Self-heal orders service</h3>
        <button onClick={triggerSelfHeal} disabled={healLoading}>
          {healLoading ? "Healing…" : "Run self_heal_orders"}
        </button>
        {selfHealResult && (
          <div style={{ marginTop: 8 }}>
            <p>
              Status:{" "}
              <strong>
                {selfHealResult.status} (before: {selfHealResult.orders_errors_before}, after:{" "}
                {selfHealResult.orders_errors_after})
              </strong>
            </p>
            <details>
              <summary>Show raw self-heal details</summary>
              <pre style={{ whiteSpace: "pre-wrap" }}>
                {JSON.stringify(selfHealResult, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </section>
    </div>
  );
};
