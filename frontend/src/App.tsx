import { useEffect, useState } from "react";
import "./index.css";

type User = { id: number; name: string };
type Product = { id: number; name: string };
type Order = { id: number; user_id: number; product_id: number; qty: number };

// Backend base URL (via Nginx reverse proxy on AWS Load Balancer)
// You can override this by setting VITE_API_BASE_URL in a .env file.



const API_BASE = "http://ab5a72e72bd224b4d96871d2ce836508-1366229795.us-east-1.elb.amazonaws.com";
function classNames(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

function App() {
  const [users, setUsers] = useState<User[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);
  const [aiInput, setAiInput] = useState("");
  const [aiOutput, setAiOutput] = useState(
    "Ask me about services, scaling, or errors…"
  );
  const [activeTab, setActiveTab] = useState<"catalog" | "users" | "orders">(
    "catalog"
  );

  async function fetchData() {
    try {
      setLoading(true);
      const [uRes, pRes, oRes] = await Promise.all([
        fetch(`${API_BASE}/users/users`),
        fetch(`${API_BASE}/catalog/products`),
        fetch(`${API_BASE}/orders/orders`),
      ]);
      setUsers(await uRes.json());
      setProducts(await pRes.json());
      setOrders(await oRes.json());
    } catch (err) {
      console.error("Error fetching:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
  }, []);

  function handleFakeAiSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!aiInput.trim()) return;

    setAiOutput(
      `🤖 (Demo AI): I analyzed your command "${aiInput}" — in the full AI Ops system, I would check logs, health status, and scaling recommendations.`
    );
    setAiInput("");
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
              Live: EKS Load Balancer
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

      {/* Main Layout */}
      <main className="max-w-6xl mx-auto px-4 py-6 grid gap-6 lg:grid-cols-[2fr,1.3fr]">
        {/* Left: Service Cards + Tabs */}
        <section className="space-y-4">
          {/* Service Status Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <ServiceCard
              name="Users Service"
              path="/users/users"
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
              path="/orders/orders"
              items={orders.length}
              color="from-emerald-500 to-lime-400"
            />
          </div>

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

            <div className="p-4">
              {activeTab === "catalog" && <CatalogTable products={products} />}
              {activeTab === "users" && <UsersTable users={users} />}
              {activeTab === "orders" && <OrdersTable orders={orders} />}
            </div>
          </div>
        </section>

        {/* Right: AI Panel */}
        <aside className="space-y-4">
          {/* AI Assistant */}
          <div className="border border-emerald-500/40 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-950 p-4 shadow-lg shadow-emerald-500/10">
            <h2 className="text-sm font-semibold text-emerald-300 flex items-center gap-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
              AI Ops Assistant (Demo)
            </h2>

            <form onSubmit={handleFakeAiSubmit} className="mt-3 space-y-2">
              <textarea
                value={aiInput}
                onChange={(e) => setAiInput(e.target.value)}
                className="w-full rounded-xl bg-slate-900 border border-slate-700 px-3 py-2 text-sm outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-400 min-h-[72px]"
                placeholder='Ask: "Check health of catalog service"'
              />
              <button
                type="submit"
                className="w-full rounded-xl bg-emerald-500 text-slate-900 text-sm font-medium py-2 hover:bg-emerald-400 transition"
                disabled={!aiInput.trim()}
              >
                Ask AI
              </button>
            </form>

            <div className="mt-3 p-3 rounded-xl bg-slate-900 border border-slate-800 text-xs text-slate-200 max-h-40 overflow-auto">
              {aiOutput}
            </div>
          </div>

          {/* Architecture Summary */}
          <div className="border border-slate-800 rounded-2xl bg-slate-900/70 p-4 text-xs text-slate-300 space-y-2">
            <h3 className="text-sm font-semibold">Architecture Overview</h3>
            <ul className="space-y-1 list-disc list-inside">
              <li>Users, Catalog, Orders → Flask microservices on AWS EKS</li>
              <li>Nginx reverse proxy routing /users /catalog /orders</li>
              <li>Docker images stored in Amazon ECR</li>
              <li>Exposed via AWS Network Load Balancer (HTTP 80)</li>
              <li>Next: add RDS, Redis, and real MCP-based AI Ops Agent</li>
            </ul>
            <p className="mt-2 text-[10px] text-slate-500 break-all">
              API Base: <code>{API_BASE}</code>
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
          <p className="text-xs text-slate-400">{props.name}</p>
          <p className="text-lg font-semibold">{props.items}</p>
        </div>
        <div
          className={`h-9 w-9 rounded-xl bg-gradient-to-br ${props.color}`}
        />
      </div>
      <p className="text-[11px] text-slate-500">
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
