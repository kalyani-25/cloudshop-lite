import { useEffect, useState } from "react";

type SummaryResponse = {
  lookback_minutes: number;
  summary: {
    users: number;
    catalog: number;
    orders: number;
  };
};

const AIOPS_BASE =
  import.meta.env.VITE_AIOPS_BASE_URL ??
  "http://aec05544a21c3462b9e50aecb6261598-1292359421.us-east-1.elb.amazonaws.com";

export default function AIOpsPanel() {
  const [data, setData] = useState<SummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchSummary = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await fetch(`${AIOPS_BASE}/ai/logs/summary?minutes=60`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const json = await res.json();
        setData(json);
      } catch (err: any) {
        setError(err.message || "Failed to fetch AI-Ops summary");
      } finally {
        setLoading(false);
      }
    };

    fetchSummary();
    const id = setInterval(fetchSummary, 60_000); // refresh every minute
    return () => clearInterval(id);
  }, []);

  if (loading && !data) return <div>Loading AI-Ops summary…</div>;
  if (error) return <div className="text-red-500">AI-Ops error: {error}</div>;
  if (!data) return null;

  return (
    <div className="border rounded-lg p-4 mt-4 bg-slate-900/40 text-sm">
      <h2 className="font-semibold mb-2">AI-Ops Error Summary (last {data.lookback_minutes} min)</h2>
      <ul className="space-y-1">
        <li>Users service: {data.summary.users} errors</li>
        <li>Catalog service: {data.summary.catalog} errors</li>
        <li>Orders service: {data.summary.orders} errors</li>
      </ul>
    </div>
  );
}
