import { usePolling } from "../hooks/usePolling.js";

// Bandeau défilant live : top movers + meilleures opportunités flip.
export default function Ticker() {
  const { data: movers } = usePolling("/movers", { intervalSec: 120 });
  const { data: opps } = usePolling("/retail/opportunities", { intervalSec: 120 });

  const items = [];
  for (const m of (movers || []).slice(0, 8)) {
    const up = (m.rise_pct ?? 0) >= 0;
    items.push({ k: `m${m.product_id}`, label: m.name, val: m.price != null ? `$${Math.round(m.price)}` : "",
      delta: `${up ? "▲" : "▼"}${Math.abs(m.rise_pct ?? 0).toFixed(1)}%`, up });
  }
  for (const o of (opps || []).slice(0, 8)) {
    const up = (o.net_upside_pct ?? 0) >= 0;
    items.push({ k: `o${o.offer_id}`, label: `🛒 ${o.title || o.product_name || ""}`,
      val: o.retail_price != null ? `${Math.round(o.retail_price)}€` : "",
      delta: `${up ? "+" : ""}${o.net_upside_pct}% net`, up });
  }
  if (items.length === 0) return null;
  const loop = [...items, ...items];

  return (
    <div data-tour="ticker" className="overflow-hidden border-b" aria-hidden="true"
         style={{ borderColor: "var(--line)", background: "var(--ticker-bg)" }}>
      <div className="flex gap-10 py-2 font-mono text-[11px] whitespace-nowrap" style={{ width: "max-content", animation: "pa-ticker 38s linear infinite" }}>
        {loop.map((it, i) => (
          <span key={`${it.k}-${i}`} style={{ color: "var(--muted2)" }}>
            {it.label} <span style={{ color: "var(--text)" }}>{it.val}</span>{" "}
            <span style={{ color: it.up ? "var(--green)" : "var(--red)" }}>{it.delta}</span>
          </span>
        ))}
      </div>
    </div>
  );
}
