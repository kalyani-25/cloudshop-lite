import React, { useEffect, useState } from "react";
import "./index.css";

type User = { id: number; name: string };
type Product = { id: number; name: string };
type Order = { id: number; user_id: number; product_id: number; qty: number };

// ---------- Config / Env ----------

const FRONTEND_URL =
  import.meta.env.VITE_FRONTEND_URL !== undefined
    ? import.meta.env.VITE_FRONTEND_URL
    : (typeof window !== "undefined" ? window.location.origin : "");

// All services (users/catalog/orders + aiops) are behind Nginx/ELB,
// so we use relative paths from the browser.
const API_BASE =
  import.meta.env.VITE_API_BASE_URL !== undefined
    ? import.meta.env.VITE_API_BASE_URL
    : "";

/**
 * AIOPS_BASE:
 * To avoid CORS, we want the browser to call /ai/... on the SAME origin
 * (Nginx will proxy /ai/* to aiops-bot-service inside the cluster).
 * So we intentionally force this to be "".
 */
const AIOPS_BASE = ""; // <- always go through Nginx

// Utility
function classNames(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

const QUICK_ACTIONS = [
  {
    name: "Error summary",
    description: "Get error counts per service (catalog, orders, users)",
    prompt: "Show error summary for last 30 minutes",
  },
  {
    name: "Top endpoints",
    description: "See which APIs are getting the most traffic",
    prompt: "What are the top endpoints in the last 30 minutes?",
  },
  {
    name: "Service errors",
    description: "Inspect recent errors for a specific service",
    prompt: "Show orders service errors in the last 30 minutes",
  },
  {
    name: "Pod status",
    description: "Check Kubernetes pod health in the cloudshop namespace",
    prompt: "Check pod status in Kubernetes",
  },
  {
    name: "Restart deployment",
    description: "Restart a K8s deployment via kubectl rollout restart",
    prompt: "Restart orders deployment",
  },
  {
    name: "Scale deployment",
    description: "Scale a deployment to more or fewer replicas",
    prompt: "Scale orders deployment to 3 replicas",
  },
  {
    name: "Rollout status",
    description: "Check rollout status for a deployment",
    prompt: "Check rollout status for orders-deployment",
  },
  {
    name: "Self-heal orders",
    description:
      "Run self-heal flow: error check → restart → rollout status → re-check errors",
    prompt: "Self heal orders service",
  },
];

function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [aiInput, setAiInput] = useState("");
  const [aiOutput, setAiOutput] = useState(
    [
      "Ask me things like:",
      '- "Show error summary for last 30 minutes"',
      '- "What are the top endpoints?"',
      '- "Check pod status"',
      '- "Self heal orders"',
    ].join("\n")
  );
  const [activeTab, setActiveTab] = useState<"catalog" | "users" | "orders">(
    "catalog"
  );

  // ---------- Data Fetch for Core Microservices ----------
  async function fetchData() {
    try {
      setLoading(true);
      setError(null);

      // ✅ All three paths match your working curl commands:
      //   /users
      //   /catalog/products
      //   /orders
      const usersUrl = `${API_BASE}/users`;
      const catalogUrl = `${API_BASE}/catalog/products`;
      const ordersUrl = `${API_BASE}/orders`;

      console.log("🔎 Fetching data from:", { usersUrl, catalogUrl, ordersUrl });

      const [uRes, pRes, oRes] = await Promise.all([
        fetch(usersUrl),
        fetch(catalogUrl),
        fetch(ordersUrl),
      ]);

      if (!uRes.ok || !pRes.ok || !oRes.ok) {
        const msg = `HTTP error:
  users:  ${uRes.status} ${uRes.statusText}
  catalog:${pRes.status} ${pRes.statusText}
  orders: ${oRes.status} ${oRes.statusText}`;
        console.error(msg);
        setError(msg);
        return;
      }

      const [uJson, pJson, oJson] = await Promise.all([
        uRes.json(),
        pRes.json(),
        oRes.json(),
      ]);

      console.log("✅ Parsed lengths:", {
        users: Array.isArray(uJson) ? uJson.length : "not-array",
        products: Array.isArray(pJson) ? pJson.length : "not-array",
        orders: Array.isArray(oJson) ? oJson.length : "not-array",
      });

      setUsers(uJson);
      setProducts(pJson);
      setOrders(oJson);
    } catch (err: any) {
      console.error("Error fetching:", err);
      setError(`Network or CORS error: ${String(err?.message ?? err)}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
  }, []);

  // ---------- AI-Ops chat using /ai/chat ----------
  async function handleAiSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!aiInput.trim()) return;

    const question = aiInput.trim();
    setAiOutput(`⏳ Sending to AI-Ops bot...\n\nQuestion: ${question}`);

    try {
      const res = await fetch(`${AIOPS_BASE}/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      if (!res.ok) {
        const txt = await res.text();
        setAiOutput(
          [
            "❌ AI-Ops error",
            "",
            `Status: ${res.status} ${res.statusText}`,
            "",
            txt,
          ].join("\n")
        );
        return;
      }

      const data = (await res.json()) as {
        answer?: string;
        intent?: string;
        endpoint?: string;
        kind?: string;
        raw?: any;
      };

      const lines: string[] = [];

      if (data.intent || data.kind) {
        lines.push(`🧠 Intent: ${data.intent ?? data.kind}`);
      }
      if ((data as any).endpoint) {
        lines.push(`Endpoint: ${(data as any).endpoint}`);
      }
      if (lines.length) lines.push("");

      if (data.answer) {
        lines.push(data.answer);
      } else {
        lines.push("Raw response:");
        lines.push(JSON.stringify(data, null, 2));
      }

      setAiOutput(lines.join("\n"));
    } catch (err: any) {
      console.error("AI-Ops call failed:", err);
      setAiOutput(
        `❌ Failed to reach AI-Ops bot.\n\nReason: ${String(
          err?.message ?? err
        )}`
      );
    }
  }

  function handleQuickAction(prompt: string) {
    setAiInput(prompt);
  }

  return (
    <div className="min-h-screen">
      {/* Top Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center text-slate-900 font-extrabold text-lg">
              CS
            </div>
            <div>
              <h1 className="text-lg font-semibold">CloudShop Lite</h1>
              <p className="text-xs text-slate-400">
                Cloud-native microservices on AWS EKS + AI Ops
              </p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <span className="hidden sm:inline-flex items-center rounded-full border border-emerald-500/40 px-3 py-1 text-[10px] uppercase tracking-wide text-emerald-300 bg-slate-900/80">
              LIVE: EKS LOAD BALANCER
            </span>
            <button
              onClick={fetchData}
              className="px-3 py-1.5 rounded-lg text-sm border border-emerald-500/60 text-emerald-300 hover:bg-emerald-500/10 transition"
            >
              {loading ? "Refreshing…" : "Refresh Data"}
            </button>
          </div>
        </div>
      </header>

      {/* Main Layout – make AI-Ops wider */}
      <main className="max-w-6xl mx-auto px-4 py-6 grid gap-6 lg:grid-cols-[1.1fr,1.9fr]">
        {/* Left: Service Cards + Tabs (slightly smaller column) */}
        <section className="space-y-4">
          {/* Service Status Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <ServiceCard
              name="Users Service"
              path="/users"
              items={users.length}
              color="from-sky-500 to-cyan-400"
            />
            <ServiceCard
              name="Catalog Service"
              path="/catalog/products"
              items={products.length}
              color="from-violet-500 to-indigo-400"
            />
            <ServiceCard
              name="Orders Service"
              path="/orders"  // ✅ display correct path
              items={orders.length}
              color="from-emerald-500 to-lime-400"
            />
          </div>

          {/* Error Banner (if any) */}
          {error && (
            <div className="rounded-xl border border-red-500/60 bg-red-950/40 px-3 py-2 text-[11px] text-red-200 whitespace-pre-wrap">
              <strong className="block mb-1">API Error</strong>
              {error}
            </div>
          )}

          {/* Tabs Section */}
          <div className="border border-slate-800 rounded-2xl bg-slate-900/60 overflow-hidden">
            <div className="flex border-b border-slate-800">
              <TabButton
                active={activeTab === "catalog"}
                onClick={() => setActiveTab("catalog")}
              >
                Catalog
              </TabButton>
              <TabButton
                active={activeTab === "users"}
                onClick={() => setActiveTab("users")}
              >
                Users
              </TabButton>
              <TabButton
                active={activeTab === "orders"}
                onClick={() => setActiveTab("orders")}
              >
                Orders
              </TabButton>
            </div>

            <div className="p-4 max-h-[320px] overflow-auto">
              {activeTab === "catalog" && <CatalogTable products={products} />}
              {activeTab === "users" && <UsersTable users={users} />}
              {activeTab === "orders" && <OrdersTable orders={orders} />}
            </div>
          </div>
        </section>

        {/* Right: BIG AI-Ops Panel */}
        <aside className="space-y-4">
          {/* AI Assistant */}
          <div className="border border-emerald-500/40 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-950 p-4 shadow-lg shadow-emerald-500/10 min-h-[340px] flex flex-col">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-emerald-300 flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                AI Ops Assistant (CloudWatch + K8s)
              </h2>
              <span className="text-[10px] text-emerald-200 uppercase tracking-wide">
                /ai/chat
              </span>
            </div>

            <form onSubmit={handleAiSubmit} className="mt-3 space-y-2">
              <textarea
                value={aiInput}
                onChange={(e) => setAiInput(e.target.value)}
                className="w-full rounded-xl bg-slate-900 border border-slate-700 px-3 py-2 text-sm outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400 min-h-[80px]"
                placeholder='Examples:
- "Show error summary for last 30 minutes"
- "What are the top endpoints?"
- "Check pod status"
- "Self heal orders"'
              />
              <button
                type="submit"
                className="w-full rounded-xl bg-emerald-500 text-slate-900 text-sm font-medium py-2 hover:bg-emerald-400 transition disabled:opacity-60"
                disabled={!aiInput.trim()}
              >
                Ask AI
              </button>
            </form>

            {/* Quick actions */}
            <div className="mt-3">
              <p className="text-[11px] text-slate-400 mb-1">
                Quick actions (click to pre-fill prompt):
              </p>
              <div className="flex flex-wrap gap-1.5">
                {QUICK_ACTIONS.map((qa) => (
                  <button
                    key={qa.name}
                    type="button"
                    onClick={() => handleQuickAction(qa.prompt)}
                    className="px-2 py-1 rounded-full border border-emerald-500/40 bg-slate-900/70 text-[10px] text-emerald-200 hover:bg-emerald-500/10 transition"
                  >
                    {qa.name}
                  </button>
                ))}
              </div>
            </div>

            {/* Output */}
            <div className="mt-3 p-3 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 max-h-56 overflow-auto whitespace-pre-wrap flex-1">
              {aiOutput}
            </div>
          </div>

          {/* Architecture / Tools Summary */}
          <div className="border border-slate-800 rounded-2xl bg-slate-900/70 p-4 text-xs text-slate-300 space-y-2">
            <h3 className="text-sm font-semibold mb-1">AI-Ops Tools Available</h3>
            <ul className="space-y-1 list-disc list-inside">
              <li>
                <strong>error_summary</strong> – error counts per service via{" "}
                <code>/ai/logs/error_summary?minutes=...</code>
              </li>
              <li>
                <strong>top_endpoints</strong> – traffic by endpoint via{" "}
                <code>/ai/logs/top_endpoints?minutes=&amp;limit=</code>
              </li>
              <li>
                <strong>service_errors</strong> – detailed errors per service via{" "}
                <code>/ai/logs/service_errors?service=&amp;minutes=</code>
              </li>
              <li>
                <strong>pod_status</strong> – Kubernetes pod health via{" "}
                <code>/ai/k8s/pod_status</code>
              </li>
              <li>
                <strong>restart_deployment</strong> –{" "}
                <code>/ai/k8s/restart_deployment</code>
              </li>
              <li>
                <strong>scale_deployment</strong> –{" "}
                <code>/ai/k8s/scale_deployment</code>
              </li>
              <li>
                <strong>rollout_status</strong> – checked inside{" "}
                <code>self_heal_orders</code>
              </li>
              <li>
                <strong>self_heal_orders</strong> – full playbook via{" "}
                <code>/ai/k8s/self_heal_orders</code>
              </li>
            </ul>
            <p className="mt-2 text-[10px] text-slate-500 break-all">
              Frontend URL: <code>{FRONTEND_URL || "(resolved at runtime)"}</code>
            </p>
            <p className="text-[10px] text-slate-500 break-all">
              API Base: <code>{API_BASE || "(relative to frontend host)"}</code>
            </p>
            <p className="text-[10px] text-slate-500 break-all">
              AI-Ops Endpoint Base: <code>/ai/* via Nginx → aiops-bot-service</code>
            </p>
          </div>
        </aside>
      </main>
    </div>
  );
}

/******************************
 * COMPONENTS
 ******************************/

function ServiceCard(props: {
  name: string;
  path: string;
  items: number;
  color: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-3 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-[11px] text-slate-400">{props.name}</p>
          <p className="text-base font-semibold">{props.items}</p>
        </div>
        <div
          className={`h-7 w-7 rounded-xl bg-gradient-to-br ${props.color}`}
        />
      </div>
      <p className="text-[10px] text-slate-500">
        Source: <code className="text-slate-300">{props.path}</code>
      </p>
    </div>
  );
}

function TabButton(props: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={props.onClick}
      className={classNames(
        "flex-1 text-sm py-2 border-b-2 transition",
        props.active
          ? "border-emerald-400 text-emerald-300 bg-slate-900"
          : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-900/60"
      )}
    >
      {props.children}
    </button>
  );
}

function CatalogTable({ products }: { products: Product[] }) {
  if (!products.length)
    return <p className="text-xs text-slate-400">No products found.</p>;
  return (
    <table className="min-w-full text-xs">
      <thead>
        <tr className="border-b border-slate-700 text-slate-400">
          <th className="text-left py-2">ID</th>
          <th className="text-left py-2">Name</th>
        </tr>
      </thead>
      <tbody>
        {products.map((p) => (
          <tr key={p.id} className="border-b border-slate-900">
            <td className="py-1.5">{p.id}</td>
            <td className="py-1.5">{p.name}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function UsersTable({ users }: { users: User[] }) {
  if (!users.length)
    return <p className="text-xs text-slate-400">No users found.</p>;
  return (
    <table className="min-w-full text-xs">
      <thead>
        <tr className="border-b border-slate-700 text-slate-400">
          <th className="text-left py-2">ID</th>
          <th className="text-left py-2">Name</th>
        </tr>
      </thead>
      <tbody>
        {users.map((u) => (
          <tr key={u.id} className="border-b border-slate-900">
            <td className="py-1.5">{u.id}</td>
            <td className="py-1.5">{u.name}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function OrdersTable({ orders }: { orders: Order[] }) {
  if (!orders.length)
    return <p className="text-xs text-slate-400">No orders yet.</p>;

  return (
    <table className="min-w-full text-xs">
      <thead>
        <tr className="border-b border-slate-700 text-slate-400">
          <th className="text-left py-2">ID</th>
          <th className="text-left py-2">User</th>
          <th className="text-left py-2">Product</th>
          <th className="text-left py-2">Qty</th>
        </tr>
      </thead>
      <tbody>
        {orders.map((o) => (
          <tr key={o.id} className="border-b border-slate-900">
            <td className="py-1.5">{o.id}</td>
            <td className="py-1.5">{o.user_id}</td>
            <td className="py-1.5">{o.product_id}</td>
            <td className="py-1.5">{o.qty}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default App;
