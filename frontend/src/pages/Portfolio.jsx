import { usePolling } from "../hooks/usePolling.js";
import { Card, Table, Badge, eur } from "../components/ui.jsx";

export default function Portfolio() {
  const { data } = usePolling("/positions");
  const rows = data || [];

  function stages(r) {
    const s = r.stages || {};
    const out = [];
    if (s.capital_secured) out.push(<Badge key="c" severity="info">Capital ✓</Badge>);
    if (s.structured) out.push(<Badge key="s" severity="warning">25/50/25</Badge>);
    if (s.forced) out.push(<Badge key="f" severity="critical">Forcé</Badge>);
    if (r.is_speculative_reserve) out.push(<Badge key="r" severity="info">Réserve</Badge>);
    return out.length ? <div className="flex gap-1">{out}</div> : "—";
  }

  const cols = [
    { key: "product_name", label: "Produit" },
    { key: "quantity", label: "Qté" },
    { key: "avg_cost", label: "Coût moyen", render: (r) => eur(r.avg_cost) },
    { key: "market_value_unit", label: "Valeur marché", render: (r) => eur(r.market_value_unit) },
    { key: "multiple", label: "×m", render: (r) => (r.multiple ? `×${r.multiple}` : "—") },
    { key: "latent_pnl", label: "PV latente", render: (r) => (
        <span className={r.latent_pnl >= 0 ? "text-info" : "text-critical"}>{eur(r.latent_pnl)}</span>
      ) },
    { key: "stages", label: "Sell engine", render: stages },
    { key: "target_sell_price", label: "Cible", render: (r) => eur(r.target_sell_price) },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Portefeuille</h1>
      <Card><Table columns={cols} rows={rows} empty="Aucune position" /></Card>
    </div>
  );
}
