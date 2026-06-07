import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { Card, Table, Badge, eur, pct } from "../components/ui.jsx";

export default function Sets() {
  const { token } = useAuth();
  const { data: sets, reload } = usePolling("/tracked-sets", { intervalSec: 120 });
  const { data: movers } = usePolling("/movers");

  async function toggle(s) {
    await api.put(token, `/tracked-sets/${s.id}`, { is_active: !s.is_active });
    reload();
  }

  const setCols = [
    { key: "name", label: "Set" },
    { key: "set_slug", label: "Slug", render: (s) => <span className="text-xs text-slate-500">{s.set_slug}</span> },
    { key: "min_value_eur", label: "Valeur min", render: (s) => eur(s.min_value_eur) },
    { key: "types", label: "Types", render: (s) => (
        <span className="space-x-1">
          {s.include_single && <Badge>single</Badge>}
          {s.include_sealed && <Badge severity="warning">sealed</Badge>}
        </span>
      ) },
    { key: "is_active", label: "Actif", render: (s) => (
        <button onClick={() => toggle(s)}
          className={`rounded px-3 py-1 text-xs ${s.is_active ? "bg-info text-slate-900" : "bg-slate-700 text-slate-300"}`}>
          {s.is_active ? "ON" : "off"}
        </button>
      ) },
  ];

  const moverCols = [
    { key: "name", label: "Produit" },
    { key: "set_slug", label: "Set", render: (m) => <span className="text-xs text-slate-500">{m.set_slug}</span> },
    { key: "rise_pct", label: "Hausse 7j/30j", render: (m) => (
        <span className={m.rise_pct >= 0 ? "text-info" : "text-critical"}>{pct(m.rise_pct)}</span>
      ) },
    { key: "volume", label: "Volume", render: (m) => m.volume ?? "—" },
    { key: "price", label: "Prix", render: (m) => eur(m.price) },
    { key: "score", label: "Score", render: (m) => (m.score != null ? m.score.toFixed(3) : "—") },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Sets suivis & Top movers</h1>

      <Card title="Sets cibles (auto-watchlist)">
        <Table columns={setCols} rows={sets || []} empty="Aucun set suivi" />
        <p className="mt-2 text-xs text-slate-500">
          Le job <code>sync-tracked-sets</code> peuple la watchlist (source=auto) sans
          écraser tes ajouts manuels. Respecte le quota PokeTrace (1×/jour).
        </p>
      </Card>

      <Card title="Top movers — le radar SIGNALE, il n'achète pas">
        <Table columns={moverCols} rows={movers || []}
               empty="Aucun mover (volume insuffisant ou pas d'historique)" />
        <p className="mt-2 text-xs text-slate-500">
          Hausse confirmée par le volume ; les achats restent soumis aux garde-fous
          (50 %, anti-pump, anti-FOMO, cash).
        </p>
      </Card>
    </div>
  );
}
