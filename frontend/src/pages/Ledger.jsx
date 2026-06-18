import { usePolling } from "../hooks/usePolling.js";
import { exportUrl } from "../api.js";
import { useI18n } from "../i18n.jsx";
import { Card, Table, Kpi, PageHeader, eur } from "../components/ui.jsx";

export default function Ledger() {
  const { t } = useI18n();
  const { data: txs } = usePolling("/transactions");
  const { data: cockpit } = usePolling("/cockpit", { intervalSec: 60 });
  const k = cockpit?.kpis;

  const cols = [
    { key: "occurred_at", label: "Date", render: (r) => (r.occurred_at || "").slice(0, 10) },
    { key: "tx_type", label: "Type" },
    { key: "gross_amount", label: "Brut", render: (r) => eur(r.gross_amount) },
    { key: "platform_fees", label: "Frais", render: (r) => eur(r.platform_fees) },
    { key: "net_amount", label: "Net", render: (r) => eur(r.net_amount) },
    { key: "cost_basis", label: "COGS", render: (r) => eur(r.cost_basis) },
  ];

  return (
    <div className="space-y-4">
      <PageHeader
        title={t("nav.ledger")}
        subtitle={t("ledger.subtitle")}
        right={
          <a href={exportUrl("/ledger/export.csv")} className="rounded-lg px-3 py-2 text-sm text-slate-200 hover:bg-slate-800" style={{ border: "1px solid var(--border2)", background: "var(--panel2)" }}>
            Export CSV
          </a>
        }
      />

      {k && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Kpi label="Profit net réalisé" value={eur(k.realized_profit_net)} />
          <Kpi label="Chiffre d'affaires" value={eur(k.turnover_cumulative)} />
          <Kpi label="Cash verrouillé (30%)" value={eur(k.cash_locked)} sub="réinjecté = cash actif (70%)" />
          <Kpi label="Provision fiscale 12,3%" value={eur(k.tax_provision)} sub="informative" />
        </div>
      )}

      <Card title="Grand livre (transactions)">
        <Table columns={cols} rows={txs || []} empty="Aucune transaction" />
      </Card>
    </div>
  );
}
