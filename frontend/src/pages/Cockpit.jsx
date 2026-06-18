import { useNavigate } from "react-router-dom";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { usePolling } from "../hooks/usePolling.js";
import { useI18n } from "../i18n.jsx";
import { eur, pct } from "../components/ui.jsx";
import ProductImage from "../components/ProductImage.jsx";

const panel = { background: "var(--panel)", border: "1px solid var(--border)" };

// Carte « jauge » du design : label mono, pastille d'état, grande valeur mono,
// barre de progression animée, légende.
function GaugeCard({ label, value, pill, pillColor, pillBg, barPct, barGrad, caption }) {
  return (
    <div className="rounded-2xl p-5 transition-colors" style={panel}>
      <div className="flex items-center justify-between">
        <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-slate-500">{label}</div>
        {pill && (
          <div className="rounded-full px-2.5 py-0.5 text-[11px] font-semibold" style={{ color: pillColor, background: pillBg }}>
            {pill}
          </div>
        )}
      </div>
      <div className="mt-3 font-mono text-[28px] font-bold leading-none">{value}</div>
      <div className="mt-3 h-1 overflow-hidden rounded" style={{ background: "var(--bar)" }}>
        <div
          style={{
            width: `${Math.max(0, Math.min(100, barPct || 0))}%`,
            height: "100%",
            borderRadius: 2,
            transformOrigin: "left",
            animation: "pa-grow .9s cubic-bezier(.22,1,.36,1) both",
            background: barGrad,
          }}
        />
      </div>
      {caption && <div className="mt-2.5 text-[12.5px] text-slate-500">{caption}</div>}
    </div>
  );
}

function MonoRow({ label, value, muted }) {
  return (
    <div className="flex items-center justify-between py-1">
      <dt className={muted ? "text-slate-500" : "text-slate-400"}>{label}</dt>
      <dd className="font-mono text-sm font-medium text-slate-100">{value}</dd>
    </div>
  );
}

function SectionLabel({ children, right }) {
  return (
    <div className="flex items-baseline justify-between">
      <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-slate-500">{children}</div>
      {right}
    </div>
  );
}

export default function Cockpit() {
  const { data, loading } = usePolling("/cockpit");
  const { data: movers } = usePolling("/movers");
  const { data: sets } = usePolling("/tracked-sets", { intervalSec: 120 });
  const { t } = useI18n();
  const navigate = useNavigate();
  if (loading || !data) return <p className="text-slate-400">{t("common.loading")}</p>;
  const k = data.kpis;
  const tier = data.tier;
  const a = data.allocation;
  const profitUp = (k.realized_profit_net ?? 0) >= 0;
  const investedPct = k.total_portfolio_value ? (k.capital_invested / k.total_portfolio_value) * 100 : 0;

  return (
    <div className="space-y-8">
      {/* En-tête */}
      <div className="flex items-baseline justify-between">
        <div>
          <h1 className="text-[28px] font-extrabold tracking-tight">{t("cockpit.title")}</h1>
          <p className="mt-1.5 text-sm text-slate-500">{t("cockpit.greeting")}</p>
        </div>
        <div className="flex items-center gap-2 font-mono text-[11px] tracking-[0.1em] text-slate-500">
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--green)", animation: "pa-pulse 1.6s infinite" }} />
          {t("cockpit.live")}
        </div>
      </div>

      {/* Vue d'ensemble — jauges */}
      <div>
        <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-slate-500">
          {t("cockpit.section.overview")}
        </div>
        <div className="mt-3 grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
          <GaugeCard
            label={t("cockpit.kpi.portfolio")}
            value={eur(k.total_portfolio_value)}
            pill={a ? `${pct(a.stock_pct)} ${t("cockpit.pill.stock")}` : null}
            pillColor="var(--blue-soft)"
            pillBg="rgba(61,123,255,.12)"
            barPct={a?.stock_pct}
            barGrad="linear-gradient(90deg, #2E5FD6, #3D7BFF)"
            caption={`${t("cockpit.tier.opcapital")} · ${eur(k.operational_capital)}`}
          />
          <GaugeCard
            label={t("cockpit.kpi.invested")}
            value={eur(k.capital_invested)}
            pill={`×${k.capital_rotation_rate ?? "—"}`}
            pillColor="var(--yellow-text)"
            pillBg="rgba(255,203,46,.12)"
            barPct={investedPct}
            barGrad="linear-gradient(90deg, #D6A21F, #FFCB2E)"
            caption={`${t("cockpit.kpi.rotation")} · ${k.capital_rotation_rate ?? "—"}`}
          />
          <GaugeCard
            label={t("cockpit.kpi.cash")}
            value={eur(k.cash_total)}
            pill={t("cockpit.pill.active")}
            pillColor="var(--green-text)"
            pillBg="rgba(52,211,153,.12)"
            barPct={a?.cash_pct}
            barGrad="linear-gradient(90deg, #1FA371, #34D399)"
            caption={`${t("cockpit.waterfall.active")} · ${eur(k.cash_active)}`}
          />
          <GaugeCard
            label={t("cockpit.kpi.profit")}
            value={eur(k.realized_profit_net)}
            pill={profitUp ? "▲" : "▼"}
            pillColor={profitUp ? "var(--green-text)" : "var(--red-text)"}
            pillBg={profitUp ? "rgba(52,211,153,.12)" : "rgba(244,88,95,.1)"}
            barPct={profitUp ? 100 : 12}
            barGrad={profitUp ? "linear-gradient(90deg, #1FA371, #34D399)" : "linear-gradient(90deg, #C23A40, #F4585F)"}
            caption={`${t("cockpit.alloc.pending")} · ${data.pending_alerts}`}
          />
        </div>
      </div>

      {/* Trésorerie · palier · allocation */}
      <div className="grid gap-3.5 lg:grid-cols-3">
        <div className="rounded-2xl p-5" style={panel}>
          <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.14em] text-slate-500">
            {t("cockpit.waterfall.title")}
          </div>
          <dl className="text-sm">
            <MonoRow label={t("cockpit.waterfall.total")} value={eur(k.cash_total)} />
            <MonoRow label={t("cockpit.waterfall.locked")} value={eur(k.cash_locked)} />
            <MonoRow label={t("cockpit.waterfall.active")} value={eur(k.cash_active)} />
            <MonoRow label={t("cockpit.waterfall.tax")} value={eur(k.tax_provision)} muted />
          </dl>
        </div>

        <div className="rounded-2xl p-5" style={panel}>
          <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.14em] text-slate-500">
            {t("cockpit.tier")} {tier.current}
            {tier.current_name ? ` — ${tier.current_name}` : ""}
          </div>
          {tier.progress !== null ? (
            <>
              <div className="h-2.5 w-full overflow-hidden rounded" style={{ background: "var(--bar)" }}>
                <div
                  className="h-2.5"
                  style={{
                    width: `${(tier.progress * 100).toFixed(0)}%`,
                    background: "linear-gradient(90deg, #1FA371, #34D399)",
                    transformOrigin: "left",
                    animation: "pa-grow .9s cubic-bezier(.22,1,.36,1) both",
                  }}
                />
              </div>
              <div className="mt-2 font-mono text-xs text-slate-500">
                {eur(tier.capital_min)} → {eur(tier.capital_max)} ({t("cockpit.tier.toward")} {tier.next ?? "—"})
              </div>
            </>
          ) : (
            <div className="text-sm text-slate-400">{t("cockpit.tier.max")}</div>
          )}
          <div className="mt-3 text-sm text-slate-300">
            {t("cockpit.tier.opcapital")} : <b className="font-mono">{eur(k.operational_capital)}</b>
          </div>
        </div>

        <div className="rounded-2xl p-5" style={panel}>
          <div className="mb-3 font-mono text-[11px] uppercase tracking-[0.14em] text-slate-500">
            {t("cockpit.alloc.title")}
          </div>
          {a ? (
            <dl className="text-sm">
              <MonoRow label={t("cockpit.alloc.stock")} value={`${pct(a.stock_pct)} (${a.target_stock_pct ?? "—"})`} />
              <MonoRow label={t("cockpit.alloc.cash")} value={`${pct(a.cash_pct)} (${a.target_cash_pct ?? "—"})`} />
              <MonoRow label={t("cockpit.alloc.pending")} value={data.pending_alerts} />
            </dl>
          ) : (
            <div className="text-sm text-slate-400">{t("cockpit.alloc.empty")}</div>
          )}
        </div>
      </div>

      {/* Top opportunités (movers réels, avec images) */}
      <div>
        <SectionLabel right={<button onClick={() => navigate("/sets")} className="text-[12.5px]" style={{ color: "var(--blue-soft)" }}>{t("cockpit.viewall")}</button>}>
          {t("cockpit.section.opportunities")}
        </SectionLabel>
        {(movers || []).length === 0 ? (
          <div className="mt-3 rounded-2xl p-6 text-center text-sm text-slate-500" style={panel}>{t("cockpit.opps.empty")}</div>
        ) : (
          <div className="mt-3 grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
            {(movers || []).slice(0, 4).map((m) => {
              const up = (m.rise_pct ?? 0) >= 0;
              return (
                <button key={m.product_id} onClick={() => navigate(`/set/${m.set_slug || ""}`)}
                        className="overflow-hidden rounded-2xl text-left transition-transform hover:-translate-y-1" style={{ ...panel }}>
                  <ProductImage src={m.image_url} alt={m.name} seed={m.set_slug} rounded={0} showInitials={false} style={{ width: "100%", height: 120 }} />
                  <div className="p-3.5">
                    <div className="truncate text-[14px] font-bold">{m.name}</div>
                    <div className="mt-0.5 font-mono text-[9.5px] uppercase tracking-[0.12em] text-slate-500">{m.set_slug || "—"}</div>
                    <div className="mt-3 flex items-center justify-between border-t pt-2.5" style={{ borderColor: "var(--line)" }}>
                      <span className="font-mono text-[14px] font-semibold">{eur(m.price)}</span>
                      <span className="rounded-md font-mono text-[11px]" style={{ padding: "2px 7px", color: up ? "var(--green-text)" : "var(--red-text)", background: up ? "rgba(52,211,153,.1)" : "rgba(244,88,95,.1)" }}>
                        {up ? "▲" : "▼"} {pct(m.rise_pct)}
                      </span>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Sets en vogue (sets suivis) */}
      <div>
        <SectionLabel right={<button onClick={() => navigate("/explorer")} className="text-[12.5px]" style={{ color: "var(--blue-soft)" }}>{t("cockpit.viewall")}</button>}>
          {t("cockpit.section.trending")}
        </SectionLabel>
        {(sets || []).length === 0 ? (
          <div className="mt-3 rounded-2xl p-6 text-center text-sm text-slate-500" style={panel}>{t("cockpit.trending.empty")}</div>
        ) : (
          <div className="mt-3 flex gap-3.5 overflow-x-auto pb-2">
            {(sets || []).slice(0, 8).map((s) => {
              const setMovers = (movers || []).filter((m) => m.set_slug === s.set_slug);
              return (
                <button key={s.id} onClick={() => navigate(`/set/${s.set_slug}`)}
                        className="w-[210px] flex-none overflow-hidden rounded-2xl text-left transition-transform hover:-translate-y-1" style={{ ...panel }}>
                  <ProductImage alt={s.name} seed={s.set_slug} rounded={0} style={{ width: "100%", height: 96 }} />
                  <div className="p-3.5">
                    <div className="truncate text-[15px] font-bold">{s.name}</div>
                    <div className="mt-1 font-mono text-[9.5px] uppercase tracking-[0.12em] text-slate-500">{s.set_slug}</div>
                    <div className="mt-3 flex items-center justify-between border-t pt-2.5" style={{ borderColor: "var(--line)" }}>
                      <span className="font-mono text-[12px] text-slate-300">{setMovers.length} {t("explorer.movers")}</span>
                      {s.is_active
                        ? <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ color: "var(--green-text)", background: "rgba(52,211,153,.1)" }}>ON</span>
                        : <span className="rounded-full px-2 py-0.5 text-[11px] text-slate-500" style={{ background: "var(--panel2)" }}>off</span>}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Historique */}
      <div className="rounded-2xl p-5" style={panel}>
        <div className="mb-3 flex items-baseline justify-between">
          <div className="font-mono text-[11px] uppercase tracking-[0.14em] text-slate-500">
            {t("cockpit.history.title")}
          </div>
          <div className="font-mono text-[10px] tracking-[0.1em] text-slate-600">
            {data.history.length} {t("cockpit.history.snapshots")}
          </div>
        </div>
        {data.history.length ? (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data.history}>
              <XAxis dataKey="date" stroke="var(--faint)" fontSize={11} />
              <YAxis stroke="var(--faint)" fontSize={11} />
              <Tooltip contentStyle={{ background: "var(--panel-solid)", border: "1px solid var(--border2)", borderRadius: 10, color: "var(--text)" }} />
              <Line type="monotone" dataKey="total_portfolio_value" stroke="var(--green)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="py-6 text-center text-sm text-slate-500">{t("cockpit.history.empty")}</div>
        )}
      </div>
    </div>
  );
}
