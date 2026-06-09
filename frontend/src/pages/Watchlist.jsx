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

const EMPTY_ADD = {
  search: "", name: "", set: "", card_number: "", language: "EN",
  product_type: "single", tier: "B", is_trinity: false, is_illustration_rare: false, keywords: "",
};

export default function Watchlist() {
  const { token } = useAuth();
  const { data, reload } = usePolling("/watchlist");
  const { data: alerts } = usePolling("/alerts?status=pending", { intervalSec: 60 });
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState({});
  const [showAdd, setShowAdd] = useState(false);
  const [addForm, setAddForm] = useState(EMPTY_ADD);
  const [addMsg, setAddMsg] = useState(null);
  const [adding, setAdding] = useState(false);

  const rows = data || [];
  const peActive = (alerts || []).some((a) => a.payload?.subtype === "accumulation_PE");
  const af = (k) => (e) => setAddForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  async function save(productId) {
    await api.put(token, `/watchlist/${productId}`, draft);
    setEditing(null);
    reload();
  }

  async function addCard(e) {
    e.preventDefault();
    setAddMsg(null);
    if (!addForm.search.trim()) return setAddMsg("Le texte de recherche est requis.");
    setAdding(true);
    try {
      await api.post(token, "/watchlist", { ...addForm, search: addForm.search.trim() });
      setAddForm(EMPTY_ADD);
      setShowAdd(false);
      reload();
    } catch (e2) {
      setAddMsg(e2.message.includes("404")
        ? "Aucun produit trouvé pour cette recherche."
        : `Erreur : ${e2.message}`);
    } finally {
      setAdding(false);
    }
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

      <Card title="Watchlist"
            right={<button onClick={() => setShowAdd((v) => !v)}
              className="rounded bg-info px-3 py-1 text-sm font-medium text-slate-900">+ Ajouter une carte/produit</button>}>
        {showAdd && (
          <form onSubmit={addCard} className="mb-4 grid gap-2 rounded border border-slate-800 p-3 md:grid-cols-3">
            <label className="text-xs md:col-span-3">Recherche PokeTrace (requis)
              <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={addForm.search}
                     onChange={af("search")} placeholder="ex. Umbreon ex Prismatic Evolutions 161" />
            </label>
            <label className="text-xs">Nom (surcharge)
              <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={addForm.name} onChange={af("name")} />
            </label>
            <label className="text-xs">Set (surcharge)
              <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={addForm.set} onChange={af("set")} />
            </label>
            <label className="text-xs">Numéro
              <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={addForm.card_number} onChange={af("card_number")} />
            </label>
            <label className="text-xs">Langue
              <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={addForm.language} onChange={af("language")} />
            </label>
            <label className="text-xs">Type
              <select className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={addForm.product_type} onChange={af("product_type")}>
                <option value="single">single</option>
                <option value="sealed">sealed</option>
              </select>
            </label>
            <label className="text-xs">Tier
              <select className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={addForm.tier} onChange={af("tier")}>
                {["S++", "S", "A", "B", "C"].map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
            </label>
            <div className="flex items-end gap-4 text-xs">
              <label className="flex items-center gap-1"><input type="checkbox" checked={addForm.is_trinity} onChange={af("is_trinity")} /> Trinité</label>
              <label className="flex items-center gap-1"><input type="checkbox" checked={addForm.is_illustration_rare} onChange={af("is_illustration_rare")} /> IR</label>
            </div>
            <label className="text-xs md:col-span-3">Mots-clés
              <input className="mt-1 w-full rounded bg-slate-800 px-2 py-1" value={addForm.keywords} onChange={af("keywords")} />
            </label>
            {addMsg && <p className="text-xs text-critical md:col-span-3">{addMsg}</p>}
            <div className="md:col-span-3">
              <button type="submit" disabled={adding}
                      className="rounded bg-info px-3 py-1 text-sm font-medium text-slate-900 disabled:opacity-60">
                {adding ? "Recherche…" : "Ajouter"}
              </button>
            </div>
          </form>
        )}
        <Table columns={cols} rows={rows} empty="Watchlist vide" />
      </Card>
    </div>
  );
}
