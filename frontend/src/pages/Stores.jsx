import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { useI18n } from "../i18n.jsx";
import { Card, Table, Badge, PageHeader, eur } from "../components/ui.jsx";

const STORE_STATE = {
  in_store: { label: "🏬 Dispo", sev: "info" },
  limited: { label: "🟠 Faible", sev: "warning" },
  out_of_store: { label: "❌ Indispo", sev: "critical" },
  unknown: { label: "❔ Inconnu", sev: "info" },
};

export default function Stores() {
  const { token } = useAuth();
  const { t } = useI18n();
  const { data: stores, reload } = usePolling("/retail/stores", { intervalSec: 120 });
  const { data: avail } = usePolling("/retail/store-availability", { intervalSec: 60 });

  async function toggle(s) {
    await api.put(token, `/retail/stores/${s.id}`, { is_watched: !s.is_watched });
    reload();
  }

  const storeCols = [
    { key: "retailer", label: "Enseigne", render: (s) => <span className="text-xs text-slate-400">{s.retailer}</span> },
    { key: "name", label: "Magasin" },
    { key: "city", label: "Ville", render: (s) => <span className="text-xs text-slate-500">{s.city || "—"} {s.postal || ""}</span> },
    { key: "store_code", label: "Code", render: (s) => <span className="font-mono text-[10px] text-slate-600">{s.store_code}</span> },
    { key: "is_watched", label: "Suivi", render: (s) => (
        <button onClick={() => toggle(s)}
          className={`rounded px-3 py-1 text-xs ${s.is_watched ? "bg-info text-ink" : "bg-slate-700 text-slate-300"}`}>
          {s.is_watched ? "ON" : "off"}
        </button>
      ) },
  ];

  const availCols = [
    { key: "title", label: "Produit" },
    { key: "store", label: "Magasin", render: (a) => <span className="text-xs text-slate-400">{a.store}{a.city ? ` · ${a.city}` : ""}</span> },
    { key: "availability_state", label: "État", render: (a) => {
        const s = STORE_STATE[a.availability_state] || STORE_STATE.unknown;
        return <Badge severity={s.sev}>{s.label}</Badge>;
      } },
    { key: "price", label: "Prix", render: (a) => eur(a.price) },
    { key: "last_changed_at", label: "Changé", render: (a) => (
        <span className="font-mono text-[10px] text-slate-600">{(a.last_changed_at || "").replace("T", " ").slice(5, 16) || "—"}</span>
      ) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title={t("stores.title")} subtitle={t("stores.subtitle")} badge="POKÉSTOCK FR · MAGASIN" />
      <Card title="Magasins suivis (zone Agen)">
        <Table columns={storeCols} rows={stores || []} empty={t("stores.empty")} />
      </Card>
      <Card title={t("stores.avail.title")}>
        <Table columns={availCols} rows={avail || []} empty={t("stores.avail.empty")} />
      </Card>
    </div>
  );
}
