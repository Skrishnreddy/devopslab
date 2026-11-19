import { StrictMode, useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

interface Product { id: string; name: string; description: string; price_cents: number }
interface Order { id: string; total_cents: number }

const money = (c: number) => `$${(c / 100).toFixed(2)}`;
const session = (() => {
  let s = localStorage.getItem("cloudmart-session");
  if (!s) { s = crypto.randomUUID(); localStorage.setItem("cloudmart-session", s); }
  return s;
})();

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  const body = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = typeof body?.detail === "string" ? body.detail : JSON.stringify(body?.detail ?? body);
    throw new Error(`${res.status} ${res.statusText}${detail ? `: ${detail}` : ""}`);
  }
  return body as T;
}

function App() {
  const [products, setProducts] = useState<Product[]>([]);
  const [cart, setCart] = useState<Record<string, number>>({});
  const [error, setError] = useState<string | null>(null);
  const [order, setOrder] = useState<Order | null>(null);
  const [pod, setPod] = useState<string>("");

  const load = useCallback(async () => {
    try {
      setError(null);
      const [p, c, h] = await Promise.all([
        call<Product[]>("/products"), call<Record<string, number>>(`/cart/${session}`), call<{ pod: string }>("/health"),
      ]);
      setProducts(p); setCart(c); setPod(h.pod);
    } catch (e) { setError((e as Error).message); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  const setQty = async (id: string, quantity: number) => {
    try { setCart(await call(`/cart/${session}`, { method: "PUT", body: JSON.stringify({ product_id: id, quantity }) })); }
    catch (e) { setError((e as Error).message); }
  };
  const checkout = async () => {
    try { setOrder(await call<Order>(`/orders/${session}`, { method: "POST" })); setCart({}); }
    catch (e) { setError((e as Error).message); }
  };

  const items = Object.entries(cart);
  const total = items.reduce((t, [id, q]) => t + q * (products.find((p) => p.id === id)?.price_cents ?? 0), 0);

  return (
    <div className="page">
      <header>
        <h1>CloudMart</h1>
        <span className="muted">Served by API pod {pod || "…"}</span>
      </header>
      {error && (
        <div className="error" role="alert">
          <strong>Something is broken.</strong> {error}
          <button onClick={() => void load()}>Retry</button>
        </div>
      )}
      {order && <div className="ok">Order {order.id} placed: {money(order.total_cents)}. Thanks!</div>}
      <main>
        <section className="grid">
          {products.map((p) => (
            <article key={p.id} className="card">
              <h2>{p.name}</h2>
              <p className="muted">{p.description}</p>
              <div className="row">
                <strong>{money(p.price_cents)}</strong>
                <button onClick={() => void setQty(p.id, (cart[p.id] ?? 0) + 1)}>Add to cart</button>
              </div>
            </article>
          ))}
        </section>
        <aside className="card cart">
          <h2>Cart</h2>
          {items.length === 0 ? <p className="muted">Empty</p> : items.map(([id, q]) => (
            <div key={id} className="row">
              <span>{products.find((p) => p.id === id)?.name ?? id} × {q}</span>
              <button className="link" onClick={() => void setQty(id, 0)}>remove</button>
            </div>
          ))}
          <div className="row total"><span>Total</span><strong>{money(total)}</strong></div>
          <button disabled={!items.length} onClick={() => void checkout()}>Place order</button>
        </aside>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><App /></StrictMode>);
