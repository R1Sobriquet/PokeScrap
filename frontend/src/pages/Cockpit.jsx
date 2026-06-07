import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { usePolling } from "../hooks/usePolling.js";
import { Card, Kpi, eur, pct } from "../components/ui.jsx";

export default function Cockpit() {
  const { data, loading } = usePolling("/cockpit");
  if (loading || !data) return <p className="text-slate-400">Chargement…</p>;
  const k = data.kpis;
  const t = data.tier;
  const a = data.allocation;

  return (
    <div className="space-y-5">
      <h1 className="text-xl font-bold">Cockpit</h1>

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <Kpi label="Valeur portefeuille" value={eur(k.total_portfolio_value)} />
        <Kpi label="Capital investi" value={eur(k.capital_invested)} />
        <Kpi label="Cash disponible" value={eur(k.cash_total)} />
        <Kpi label="Profit net réalisé" value={eur(k.realized_profit_net)} />
        <Kpi label="Rotation capital" value={k.capital_rotation_rate ?? "—"} />
      </div>

      <div className="grid gap-3 md:grid-cols-3">
        <Card title="Cascade de trésorerie">
          <dl className="space-y-1 text-sm">
            <Row label="Cash total" value={eur(k.cash_total)} />
            <Row label="Cash verrouillé (30/70)" value={eur(k.cash_locked)} />
            <Row label="Cash actif" value={eur(k.cash_active)} />
            <Row label="Provision fiscale (info)" value={eur(k.tax_provision)} muted />
          </dl>
        </Card>

        <Card title={`Palier ${t.current}${t.current_name ? " — " + t.current_name : ""}`}>
          {t.progress !== null ? (
            <>
              <div className="h-3 w-full overflow-hidden rounded bg-slate-800">
                <div className="h-3 bg-info" style={{ width: `${(t.progress * 100).toFixed(0)}%` }} />
              </div>
              <div className="mt-2 text-xs text-slate-400">
                {eur(t.capital_min)} → {eur(t.capital_max)} (vers palier {t.next ?? "—"})
              </div>
            </>
          ) : (
            <div className="text-sm text-slate-400">Palier maximal ou hors bande.</div>
          )}
          <div className="mt-3 text-sm">
            Capital opérationnel : <b>{eur(k.operational_capital)}</b>
          </div>
        </Card>

        <Card title="Allocation réelle vs cible">
          {a ? (
            <dl className="space-y-1 text-sm">
              <Row label="Stock" value={`${pct(a.stock_pct)} (cible ${a.target_stock_pct ?? "—"})`} />
              <Row label="Cash" value={`${pct(a.cash_pct)} (cible ${a.target_cash_pct ?? "—"})`} />
              <Row label="Alertes en attente" value={data.pending_alerts} />
            </dl>
          ) : (
            <div className="text-sm text-slate-400">Capital opérationnel nul.</div>
          )}
        </Card>
      </div>

      <Card title={`Valeur du portefeuille (${data.history.length} snapshots)`}>
        {data.history.length ? (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data.history}>
              <XAxis dataKey="date" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip contentStyle={{ background: "#0f172a", border: "1px solid #1e293b" }} />
              <Line type="monotone" dataKey="total_portfolio_value" stroke="#2ECC71" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="py-6 text-center text-sm text-slate-500">
            Pas encore d'historique (le snapshot KPI quotidien le remplit).
          </div>
        )}
      </Card>
    </div>
  );
}

function Row({ label, value, muted }) {
  return (
    <div className="flex justify-between">
      <dt className={muted ? "text-slate-500" : "text-slate-400"}>{label}</dt>
      <dd className="font-medium">{value}</dd>
    </div>
  );
}
