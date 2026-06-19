import { usePolling } from "../hooks/usePolling.js";
import { useI18n } from "../i18n.jsx";
import { PageHeader, eur } from "../components/ui.jsx";
import ProductImage from "../components/ProductImage.jsx";

const panel = { background: "var(--panel)", border: "1px solid var(--border)" };
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

export default function FlipRadar() {
  const { t } = useI18n();
  const { data } = usePolling("/retail/opportunities", { intervalSec: 60 });
  const list = data || [];

  return (
    <div className="space-y-5">
      <PageHeader title={t("flip.title")} subtitle={t("flip.subtitle")} badge="POKÉSTOCK FR · FLIP" />

      <div className="overflow-hidden rounded-2xl" style={panel}>
        <div
          className="grid items-center gap-2.5 border-b px-4 py-2.5 font-mono text-[9px] uppercase tracking-[0.12em] text-slate-500"
          style={{ borderColor: "var(--line)", gridTemplateColumns: GRID }}
        >
          <div>#</div>
          <div>{t("restock.col.product")}</div>
          <div>{t("restock.col.retailer")}</div>
          <div>{t("restock.col.state")}</div>
          <div className="text-right">{t("restock.col.price")}</div>
          <div className="text-right">{t("restock.col.market")}</div>
          <div className="text-right">{t("flip.col.upside")}</div>
          <div className="text-right">{t("flip.col.profit")}</div>
          <div>{t("restock.col.flip")}</div>
        </div>

        {list.length === 0 ? (
          <div className="px-4 py-12 text-center text-sm text-slate-500">{t("flip.empty")}</div>
        ) : (
          list.map((o, i) => {
            const st = STATE[o.stock_state] || STATE.unknown;
            const ft = TONE[o.verdict_tone] || TONE.fair;
            const up = (o.net_upside_pct ?? 0) >= 0;
            return (
              <div
                key={o.offer_id}
                className="grid items-center gap-2.5 border-b px-4 py-3"
                style={{ borderColor: "var(--line)", gridTemplateColumns: GRID }}
              >
                <div className="font-mono text-[12px] text-slate-500">{i + 1}</div>
                <div className="flex min-w-0 items-center gap-2.5">
                  <ProductImage src={o.image_url} alt={o.title || o.product_name} seed={o.retailer} style={{ width: 30, height: 42 }} />
                  <div className="min-w-0">
                    <div className="truncate text-[13.5px] font-semibold">{o.title || o.product_name || o.url}</div>
                    <a href={o.url} target="_blank" rel="noreferrer" className="font-mono text-[10px]" style={{ color: "var(--blue-soft)" }}>
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
    </div>
  );
}
