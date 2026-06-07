import { useState } from "react";
import { LineChart, Line, ResponsiveContainer } from "recharts";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { Card, Table, Badge, eur } from "../components/ui.jsx";

function Sparkline({ latest }) {
  if (!latest) return <span className="text-slate-600">—</span>;
  const pts = [
    { i: 0, v: latest.avg_30d },
    { i: 1, v: latest.avg_7d },
    { i: 2, v: latest.avg_1d ?? latest.price_avg },
  ].filter((p) => p.v != null);
  if (pts.length < 2) return <span>{eur(latest.price_avg)}</span>;
  const up = pts[pts.length - 1].v >= pts[0].v;
  return (
    <div className="h-8 w-24">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={pts}>
          <Line type="monotone" dataKey="v" stroke={up ? "#2ECC71" : "#E74C3C"} dot={false} strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function Watchlist() {
  const { token } = useAuth();
  const { data, reload } = usePolling("/watchlist");
  const { data: alerts } = usePolling("/alerts?status=pending", { intervalSec: 60 });
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState({});

  const rows = data || [];
  const peActive = (alerts || []).some((a) => a.payload?.subtype === "accumulation_PE");

  async function save(productId) {
    await api.put(token, `/watchlist/${productId}`, draft);
    setEditing(null);
    reload();
  }

  const cols = [
    { key: "name", label: "Produit", render: (r) => r.product?.name },
    { key: "tier", label: "Tier", render: (r) =>
        editing === r.product_id ? (
          <input className="w-16 rounded bg-slate-800 px-1" defaultValue={r.tier}
                 onChange={(e) => setDraft((d) => ({ ...d, tier: e.target.value }))} />
        ) : <Badge>{r.tier}</Badge> },
    { key: "flags", label: "Flags", render: (r) => (
        <span className="space-x-1">
          {r.is_trinity && <Badge severity="warning">Trinité</Badge>}
          {r.is_illustration_rare && <Badge severity="info">IR</Badge>}
        </span>
      ) },
    { key: "price", label: "Dernier prix", render: (r) => eur(r.latest?.price_avg) },
    { key: "trend", label: "Tendance", render: (r) => <Sparkline latest={r.latest} /> },
    { key: "sales", label: "Ventes", render: (r) => r.latest?.sale_count ?? "—" },
    { key: "keywords", label: "Mots-clés", render: (r) =>
        editing === r.product_id ? (
          <input className="w-40 rounded bg-slate-800 px-1" defaultValue={r.keywords || ""}
                 onChange={(e) => setDraft((d) => ({ ...d, keywords: e.target.value }))} />
        ) : <span className="text-xs text-slate-400">{r.keywords}</span> },
    { key: "edit", label: "", render: (r) =>
        editing === r.product_id ? (
          <button className="text-info" onClick={() => save(r.product_id)}>Enregistrer</button>
        ) : (
          <button className="text-slate-400 hover:text-slate-200"
                  onClick={() => { setEditing(r.product_id); setDraft({}); }}>Éditer</button>
        ) },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Watchlist</h1>
      <div className={`rounded border px-3 py-2 text-sm ${peActive
        ? "border-info/40 bg-info/10 text-info" : "border-slate-800 bg-slate-900 text-slate-400"}`}>
        Signal d'accumulation Prismatic Evolutions : <b>{peActive ? "ACTIF" : "inactif"}</b>
      </div>
      <Card><Table columns={cols} rows={rows} empty="Watchlist vide" /></Card>
    </div>
  );
}
