import { useState } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { Card, Table, Badge, eur } from "../components/ui.jsx";

export default function Lots() {
  const { token } = useAuth();
  const { data: lots, reload } = usePolling("/lots");
  const [selected, setSelected] = useState(null);
  const { data: items, reload: reloadItems } = usePolling(
    selected ? `/lots/${selected}/items` : null, { enabled: !!selected }
  );

  async function act(path, body) {
    await api.post(token, path, body);
    reload();
    if (selected) reloadItems();
  }

  const lotCols = [
    { key: "id", label: "#" },
    { key: "label", label: "Label", render: (r) => r.label || "—" },
    { key: "total_cost", label: "Coût", render: (r) => eur(r.total_cost) },
    { key: "status", label: "État", render: (r) => <Badge>{r.status}</Badge> },
    { key: "actions", label: "Intake / Segmentation", render: (r) => (
        <div className="flex gap-2">
          <button className="text-info" onClick={() => act("/intake", { lot_id: r.id })}>Intake</button>
          <button className="text-warning" onClick={() => act(`/lots/${r.id}/segment`)}>Segmenter</button>
          <button className="text-slate-300" onClick={() => setSelected(r.id)}>Voir items</button>
        </div>
      ) },
  ];

  const itemCols = [
    { key: "id", label: "#" },
    { key: "product_id", label: "Produit", render: (r) => r.product_id ?? "vrac" },
    { key: "quantity", label: "Qté" },
    { key: "segmentation", label: "Segment.", render: (r) => <Badge severity={r.segmentation === "individual" ? "info" : "warning"}>{r.segmentation}</Badge> },
    { key: "estimated_unit_value", label: "Valeur est.", render: (r) => eur(r.estimated_unit_value) },
    { key: "bulk_group_label", label: "Lot vrac", render: (r) => r.bulk_group_label || "—" },
    { key: "target_platform", label: "Routage", render: (r) => r.target_platform || "—" },
    { key: "promote", label: "", render: (r) =>
        r.product_id ? (
          <button className="text-info" onClick={() => api.post(token, `/lot-items/${r.id}/promote`).then(reloadItems)}>
            Promouvoir
          </button>
        ) : "—" },
  ];

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Lots & Liquidation</h1>
      <Card title="Lots reçus">
        <Table columns={lotCols} rows={lots || []} empty="Aucun lot (créés à l'exécution d'achat Discord)" />
      </Card>
      {selected && (
        <Card title={`Items du lot #${selected}`}>
          <Table columns={itemCols} rows={items || []} empty="Aucun item — lancez l'intake" />
        </Card>
      )}
    </div>
  );
}
