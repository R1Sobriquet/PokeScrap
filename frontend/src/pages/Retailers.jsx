import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { useI18n } from "../i18n.jsx";
import { Card, Table, Badge, PageHeader } from "../components/ui.jsx";

export default function Retailers() {
  const { token } = useAuth();
  const { t } = useI18n();
  const { data: retailers, reload } = usePolling("/retail/retailers", { intervalSec: 30 });

  async function toggle(r) {
    await api.put(token, `/retail/retailers/${r.id}`, { is_active: !r.is_active });
    reload();
  }

  async function resetCircuit(r) {
    await api.put(token, `/retail/retailers/${r.id}`, { reset_circuit: true });
    reload();
  }

  const cols = [
    { key: "name", label: "Détaillant" },
    { key: "code", label: "Code", render: (r) => <span className="text-xs text-slate-500">{r.code}</span> },
    { key: "enabled", label: "Flag settings", render: (r) => (
        <Badge severity={r.enabled ? "info" : "warning"}>{r.enabled ? "activé" : "off"}</Badge>
      ) },
    { key: "offers", label: "Offres", render: (r) => r.offers },
    { key: "endpoint", label: "Endpoint dispo", render: (r) => (
        <Badge severity={r.availability_endpoint ? "info" : "warning"}>
          {r.availability_endpoint ? "direct" : "page"}
        </Badge>
      ) },
    { key: "latency", label: "Latence détec→alerte", render: (r) => (
        <span className="font-mono text-xs text-slate-400">
          {r.avg_latency_ms != null ? `${r.avg_latency_ms} ms` : "—"}
        </span>
      ) },
    { key: "circuit", label: "Circuit breaker", render: (r) => (
        r.circuit_open
          ? <Badge severity="critical">ouvert ({r.error_count} err)</Badge>
          : <Badge severity="info">{r.error_count ? `${r.error_count} err` : "ok"}</Badge>
      ) },
    { key: "is_active", label: "Actif", render: (r) => (
        <button onClick={() => toggle(r)}
          className={`rounded px-3 py-1 text-xs ${r.is_active ? "bg-info text-ink" : "bg-slate-700 text-slate-300"}`}>
          {r.is_active ? "ON" : "off"}
        </button>
      ) },
    { key: "reset", label: "", render: (r) => (
        r.circuit_open || r.error_count
          ? <button onClick={() => resetCircuit(r)} className="text-xs text-info hover:underline">Réarmer</button>
          : null
      ) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader title={t("nav.detaillants")} subtitle={t("retailers.subtitle")} />
      <Card title="Cibles de veille (Cultura · Fnac · Micromania)">
        <Table columns={cols} rows={retailers || []} empty="Aucun détaillant" />
        <p className="mt-2 text-xs text-slate-500">
          Le <b>flag settings</b> (<code>retail_&lt;code&gt;_enabled</code>) coupe un détaillant sans
          le désactiver. Le <b>circuit breaker</b> s'ouvre après plusieurs erreurs consécutives
          (403/429) ; « Réarmer » remet le compteur à zéro.
        </p>
      </Card>
    </div>
  );
}
