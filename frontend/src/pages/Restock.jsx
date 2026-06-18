import { useState } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { Card, Table, Badge, eur } from "../components/ui.jsx";

const STATE_LABEL = {
  in_stock: { txt: "✅ En stock", sev: "info" },
  preorder: { txt: "🟡 Précommande", sev: "warning" },
  out_of_stock: { txt: "❌ Rupture", sev: "critical" },
  unknown: { txt: "❔ Inconnu", sev: "info" },
};

export default function Restock() {
  const { token } = useAuth();
  const { data: offers, reload } = usePolling("/retail/offers?watched=true", { intervalSec: 30 });
  const [url, setUrl] = useState("");
  const [msg, setMsg] = useState(null);

  async function addByUrl(e) {
    e.preventDefault();
    setMsg(null);
    if (!url.trim().startsWith("http")) return setMsg("URL invalide.");
    try {
      const res = await api.post(token, "/retail/offers", { url: url.trim() });
      setMsg(res.note || "Offre ajoutée à la veille.");
      setUrl("");
      reload();
    } catch (e2) {
      setMsg(e2.message.includes("400") ? "Détaillant introuvable pour cette URL." : `Erreur : ${e2.message}`);
    }
  }

  async function unwatch(o) {
    await api.put(token, `/retail/offers/${o.id}`, { is_watched: false });
    reload();
  }

  const cols = [
    { key: "title", label: "Produit", render: (o) => (
        <a href={o.url} target="_blank" rel="noreferrer" className="text-info hover:underline">
          {o.title || o.url}
        </a>
      ) },
    { key: "retailer", label: "Enseigne", render: (o) => <span className="text-xs text-slate-400">{o.retailer}</span> },
    { key: "stock_state", label: "État", render: (o) => {
        const s = STATE_LABEL[o.stock_state] || STATE_LABEL.unknown;
        return <Badge severity={s.sev}>{s.txt}</Badge>;
      } },
    { key: "price", label: "Prix", render: (o) => eur(o.price) },
    { key: "last_changed_at", label: "Dernier changement", render: (o) => (
        <span className="text-xs text-slate-500">
          {(o.last_changed_at || o.last_checked_at || "").replace("T", " ").slice(0, 16) || "—"}
        </span>
      ) },
    { key: "act", label: "", render: (o) => (
        <button onClick={() => unwatch(o)} className="text-xs text-critical hover:underline">Retirer</button>
      ) },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Veille restock</h1>

      <Card title="Ajouter une offre par URL">
        <form onSubmit={addByUrl} className="flex flex-wrap gap-2">
          <input
            className="flex-1 rounded bg-slate-800 px-2 py-1 text-sm"
            placeholder="https://www.cultura.com/p/…"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <button type="submit" className="rounded bg-info px-3 py-1 text-sm font-medium text-ink">
            Ajouter à la veille
          </button>
        </form>
        {msg && <p className="mt-2 text-xs text-slate-400">{msg}</p>}
      </Card>

      <Card title="Offres surveillées">
        <Table columns={cols} rows={offers || []} empty="Aucune offre surveillée — ajoute une URL ci-dessus." />
        <p className="mt-2 text-xs text-slate-500">
          Le job <code>retail-check-restocks</code> rafraîchit l'état ; une alerte part
          (Discord + Telegram) sur passage en stock / précommande.
        </p>
      </Card>
    </div>
  );
}
