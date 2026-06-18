import { usePolling } from "../hooks/usePolling.js";
import { useI18n } from "../i18n.jsx";
import { eur } from "../components/ui.jsx";

const panel = { background: "var(--panel)", border: "1px solid var(--border)" };

function StageBadges({ r, t }) {
  const s = r.stages || {};
  const out = [];
  const chip = (key, label, color, bg) => (
    <span key={key} className="rounded-md font-mono text-[9px] font-semibold" style={{ padding: "2px 6px", color, background: bg }}>
      {label}
    </span>
  );
  if (s.capital_secured) out.push(chip("c", t("portfolio.stage.capital"), "var(--green-text)", "rgba(52,211,153,.12)"));
  if (s.structured) out.push(chip("s", t("portfolio.stage.structured"), "var(--yellow-text)", "rgba(255,203,46,.12)"));
  if (s.forced) out.push(chip("f", t("portfolio.stage.forced"), "var(--red-text)", "rgba(244,88,95,.1)"));
  if (r.is_speculative_reserve) out.push(chip("r", t("portfolio.stage.reserve"), "var(--blue-soft)", "rgba(61,123,255,.12)"));
  return out.length ? <div className="flex flex-wrap gap-1">{out}</div> : null;
}

function Stat({ label, value, color }) {
  return (
    <div>
      <div className="font-mono text-[8.5px] uppercase tracking-[0.11em] text-slate-500">{label}</div>
      <div className="mt-1 font-mono text-[14px] font-semibold" style={color ? { color } : undefined}>{value}</div>
    </div>
  );
}

export default function Portfolio() {
  const { data } = usePolling("/positions");
  const { t } = useI18n();
  const rows = data || [];

  const totalValue = rows.reduce((acc, r) => acc + (r.market_value_unit || 0) * (r.quantity || 0), 0);
  const totalPnl = rows.reduce((acc, r) => acc + (r.latent_pnl || 0), 0);
  const pnlUp = totalPnl >= 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-[32px] font-extrabold tracking-tight">{t("portfolio.title")}</h1>
          <p className="mt-1.5 text-sm text-slate-500">
            {rows.length} {t("portfolio.subtitle")}
          </p>
        </div>
        <div className="text-right">
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-slate-500">{t("portfolio.total")}</div>
          <div className="mt-1 flex items-baseline justify-end gap-3">
            <span className="font-mono text-[36px] font-bold leading-none">{eur(totalValue)}</span>
            <span
              className="rounded-lg font-mono text-[13px]"
              style={{
                padding: "4px 10px",
                color: pnlUp ? "var(--green-text)" : "var(--red-text)",
                background: pnlUp ? "rgba(52,211,153,.1)" : "rgba(244,88,95,.1)",
              }}
            >
              {pnlUp ? "▲" : "▼"} {eur(totalPnl)}
            </span>
          </div>
        </div>
      </div>

      {/* Holdings */}
      {rows.length === 0 ? (
        <div className="rounded-2xl p-10 text-center text-sm text-slate-500" style={panel}>{t("portfolio.empty")}</div>
      ) : (
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((r, i) => {
            const pnlUpR = (r.latent_pnl ?? 0) >= 0;
            return (
              <div key={r.id ?? i} className="overflow-hidden rounded-2xl" style={{ ...panel, borderColor: "var(--border2)" }}>
                <div className="flex items-center justify-between gap-2 border-b px-4 py-3" style={{ borderColor: "var(--line)", background: "var(--panel2)" }}>
                  <div className="truncate text-[13px] font-bold leading-tight">{r.product_name}</div>
                  <div className="flex-none rounded-md font-mono text-[9px] font-bold tracking-wide" style={{ padding: "4px 7px", color: "var(--bg)", background: "var(--text)" }}>
                    {t("portfolio.qty")} {r.quantity}
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 px-4 py-3.5">
                  <Stat label={t("portfolio.stat.value")} value={eur(r.market_value_unit)} />
                  <Stat label={t("portfolio.stat.mult")} value={r.multiple ? `×${r.multiple}` : "—"} color="var(--gold)" />
                  <Stat label={t("portfolio.pnl")} value={eur(r.latent_pnl)} color={pnlUpR ? "var(--green-text)" : "var(--red-text)"} />
                  <Stat label={t("portfolio.stat.cost")} value={eur(r.avg_cost)} />
                  <Stat label={t("portfolio.stat.target")} value={eur(r.target_sell_price)} />
                </div>
                <div className="px-4 pb-3.5">
                  <StageBadges r={r} t={t} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
