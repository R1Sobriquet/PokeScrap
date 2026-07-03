import { useState } from "react";
import { ResponsiveContainer, Treemap } from "recharts";
import { usePolling } from "../hooks/usePolling.js";
import { useI18n } from "../i18n.jsx";
import { PageHeader, SortHeader, Stat, eur, panel, useSortable } from "../components/ui.jsx";
import ProductImage from "../components/ProductImage.jsx";
import TiltCard from "../components/TiltCard.jsx";
import DetailDrawer from "../components/DetailDrawer.jsx";

const TONE_FILL = { buy: "#1E7A4D", fair: "#2E5FD6", pass: "#7A1220" };

function MoneyCell({ x, y, width, height, name, tone, upside }) {
  if (width < 4 || height < 4) return null;
  return (
    <g>
      <rect x={x} y={y} width={width} height={height} rx={6}
        style={{ fill: TONE_FILL[tone] || "#2E5FD6", stroke: "var(--bg)", strokeWidth: 2, opacity: 0.92 }} />
      {width > 64 && height > 30 && (
        <>
          <text x={x + 8} y={y + 18} fill="#fff" fontSize={11} fontWeight="700" style={{ pointerEvents: "none" }}>
            {(name || "").slice(0, Math.floor(width / 7))}
          </text>
          <text x={x + 8} y={y + 34} fill="rgba(255,255,255,.85)" fontSize={10} fontFamily="JetBrains Mono" style={{ pointerEvents: "none" }}>
            {upside >= 0 ? "+" : ""}{upside}%
          </text>
        </>
      )}
    </g>
  );
}

function MoneyMap({ opps, t }) {
  const data = (opps || [])
    .map((o) => ({ name: o.title || o.product_name || "—", tone: o.verdict_tone,
      upside: o.net_upside_pct ?? 0, size: Math.max(1, o.est_profit ?? o.net_upside_pct ?? 1) }))
    .filter((d) => d.size > 0);
  if (data.length === 0) return null;
  return (
    <div className="overflow-hidden rounded-2xl p-4" style={{ background: "var(--panel)", border: "1px solid var(--border)" }}>
      <div className="mb-2 font-mono text-[11px] uppercase tracking-[0.16em] text-slate-500">{t("flip.map")}</div>
      <ResponsiveContainer width="100%" height={220}>
        <Treemap data={data} dataKey="size" stroke="var(--bg)" isAnimationActive
          content={<MoneyCell />} />
      </ResponsiveContainer>
    </div>
  );
}

const GRID = "32px minmax(0,1fr) 92px 116px 74px 78px 96px 86px 108px";

const STATE = {
  in_stock: { color: "var(--green-text)", bg: "rgba(52,211,153,.12)" },
  preorder: { color: "var(--yellow-text)", bg: "rgba(255,203,46,.12)" },
  out_of_stock: { color: "var(--red-text)", bg: "rgba(244,88,95,.1)" },
  unknown: { color: "var(--muted2)", bg: "var(--panel2)" },
};
const TONE = {
  buy: { color: "var(--green-text)", bg: "rgba(52,211,153,.12)" },
  fair: { color: "var(--blue-soft)", bg: "rgba(61,123,255,.1)" },
  pass: { color: "var(--red-text)", bg: "rgba(244,88,95,.1)" },
};

function host(url) {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return "—";
  }
}

// Accesseurs de tri (niveau module → identité stable pour useSortable).
const SORTS = {
  product: (o) => (o.title || o.product_name || "").toLowerCase(),
  retailer: (o) => (o.retailer || "").toLowerCase(),
  state: (o) => o.stock_state || "",
  price: (o) => (o.retail_price != null ? Number(o.retail_price) : null),
  market: (o) => (o.market_value != null ? Number(o.market_value) : null),
  upside: (o) => (o.net_upside_pct != null ? Number(o.net_upside_pct) : null),
  profit: (o) => (o.est_profit != null ? Number(o.est_profit) : null),
};

export default function FlipRadar() {
  const { t } = useI18n();
  const { data } = usePolling("/retail/opportunities", { intervalSec: 60 });
  const list = data || [];
  const { sorted, sort, toggle } = useSortable(list, SORTS);
  const [selected, setSelected] = useState(null); // deal ouvert dans le tiroir

  const openRow = (o) => setSelected(o);

  return (
    <div className="space-y-5">
      <PageHeader title={t("flip.title")} subtitle={t("flip.subtitle")} badge="POKÉSTOCK FR · FLIP" />

      <MoneyMap opps={list} t={t} />

      <div className="overflow-hidden rounded-2xl" style={panel}>
        <div
          className="grid items-center gap-2.5 border-b px-4 py-2.5 font-mono text-[9px] uppercase tracking-[0.12em] text-slate-500"
          style={{ borderColor: "var(--line)", gridTemplateColumns: GRID }}
        >
          <div>#</div>
          <SortHeader label={t("restock.col.product")} k="product" sort={sort} onToggle={toggle} />
          <SortHeader label={t("restock.col.retailer")} k="retailer" sort={sort} onToggle={toggle} />
          <SortHeader label={t("restock.col.state")} k="state" sort={sort} onToggle={toggle} />
          <SortHeader label={t("restock.col.price")} k="price" sort={sort} onToggle={toggle} align="right" />
          <SortHeader label={t("restock.col.market")} k="market" sort={sort} onToggle={toggle} align="right" />
          <SortHeader label={t("flip.col.upside")} k="upside" sort={sort} onToggle={toggle} align="right" />
          <SortHeader label={t("flip.col.profit")} k="profit" sort={sort} onToggle={toggle} align="right" />
          <div>{t("restock.col.flip")}</div>
        </div>

        {sorted.length === 0 ? (
          <div className="px-4 py-12 text-center text-sm text-slate-500">{t("flip.empty")}</div>
        ) : (
          sorted.map((o, i) => {
            const st = STATE[o.stock_state] || STATE.unknown;
            const ft = TONE[o.verdict_tone] || TONE.fair;
            const up = (o.net_upside_pct ?? 0) >= 0;
            return (
              <div
                key={o.offer_id}
                className="grid cursor-pointer items-center gap-2.5 border-b px-4 py-3 hover:bg-slate-800/30"
                style={{ borderColor: "var(--line)", gridTemplateColumns: GRID }}
                onClick={() => openRow(o)}
                onKeyDown={(e) => { if (e.key === "Enter") openRow(o); }}
                role="button"
                tabIndex={0}
                aria-label={`${o.title || o.product_name} — ${t("flip.drawer.open")}`}
              >
                <div className="font-mono text-[12px] text-slate-500">{i + 1}</div>
                <div className="flex min-w-0 items-center gap-2.5">
                  <TiltCard max={16} radius={6} className="flex-none" style={{ width: 30, height: 42 }}>
                    <ProductImage src={o.image_url} alt={o.title || o.product_name} seed={o.retailer} style={{ width: 30, height: 42 }} />
                  </TiltCard>
                  <div className="min-w-0">
                    <div className="truncate text-[13.5px] font-semibold">{o.title || o.product_name || o.url}</div>
                    <a href={o.url} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}
                       className="font-mono text-[10px]" style={{ color: "var(--blue-soft)" }}>
                      {host(o.url)}
                    </a>
                  </div>
                </div>
                <div className="font-mono text-[11.5px] text-slate-400">{o.retailer}</div>
                <div>
                  <span className="inline-flex items-center rounded-full px-2 py-1 text-[11px] font-semibold" style={{ color: st.color, background: st.bg }}>
                    {t(`restock.state.${o.stock_state}`) || t("restock.state.unknown")}
                  </span>
                </div>
                <div className="text-right font-mono text-[13px] font-semibold">{eur(o.retail_price)}</div>
                <div className="text-right font-mono text-[12px] text-slate-400">{eur(o.market_value)}</div>
                <div className="text-right font-mono text-[13px] font-bold" style={{ color: up ? "var(--green-text)" : "var(--red-text)" }}>
                  {up ? "+" : ""}{o.net_upside_pct}%
                </div>
                <div className="text-right font-mono text-[12.5px]" style={{ color: "var(--gold)" }}>{eur(o.est_profit)}</div>
                <div>
                  <span className="inline-flex rounded-md px-2 py-1 font-mono text-[10.5px] font-bold" style={{ color: ft.color, background: ft.bg }}>
                    {o.verdict}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
      <p className="font-mono text-[10.5px] leading-relaxed text-slate-600">{t("flip.foot")}</p>

      {/* Tiroir de détail : clic sur une ligne → fiche complète sans quitter la liste */}
      <DetailDrawer open={Boolean(selected)} onClose={() => setSelected(null)}
                    title={selected ? (selected.title || selected.product_name || "—") : ""}>
        {selected && (() => {
          const st = STATE[selected.stock_state] || STATE.unknown;
          const ft = TONE[selected.verdict_tone] || TONE.fair;
          const up = (selected.net_upside_pct ?? 0) >= 0;
          return (
            <div className="space-y-5">
              <div className="overflow-hidden rounded-xl" style={{ border: "1px solid var(--border2)" }}>
                <ProductImage src={selected.image_url} alt={selected.title || selected.product_name}
                              seed={selected.retailer} rounded={0} style={{ width: "100%", height: 180 }} />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold"
                      style={{ color: st.color, background: st.bg }}>
                  {t(`restock.state.${selected.stock_state}`) || t("restock.state.unknown")}
                </span>
                <span className="inline-flex rounded-md px-2.5 py-1 font-mono text-[11px] font-bold"
                      style={{ color: ft.color, background: ft.bg }}>
                  {selected.verdict}
                </span>
                <span className="font-mono text-[11px] text-slate-500">{selected.retailer} · {host(selected.url)}</span>
              </div>
              <div className="grid grid-cols-2 gap-4 rounded-xl p-4" style={panel}>
                <Stat lg label="MSRP" value={eur(selected.retail_price)} />
                <Stat lg label={t("restock.col.market")} value={eur(selected.market_value)} />
                <Stat lg label={t("flip.col.upside")}
                      value={`${up ? "+" : ""}${selected.net_upside_pct}%`}
                      color={up ? "var(--green-text)" : "var(--red-text)"} />
                <Stat lg label={t("flip.col.profit")} value={eur(selected.est_profit)} color="var(--gold)" />
              </div>
              <div className="flex flex-wrap gap-2.5">
                <a href={selected.url} target="_blank" rel="noreferrer"
                   className="rounded-xl px-4 py-2.5 text-sm font-bold text-ink"
                   style={{ background: "linear-gradient(180deg, #FFD75A, #FFC91F)" }}>
                  {t("cockpit.deal.grab")}
                </a>
                <button onClick={() => setSelected(null)} className="rounded-xl px-4 py-2.5 text-sm font-semibold"
                        style={{ border: "1px solid var(--border2)", background: "var(--panel2)", color: "var(--text2)" }}>
                  {t("common.close")}
                </button>
              </div>
            </div>
          );
        })()}
      </DetailDrawer>
    </div>
  );
}
