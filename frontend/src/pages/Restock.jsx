import { useState } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { useI18n } from "../i18n.jsx";
import { SortHeader, eur, panel, useSortable } from "../components/ui.jsx";
import ProductImage from "../components/ProductImage.jsx";


const STATE = {
  in_stock: { color: "var(--green-text)", bg: "rgba(52,211,153,.12)" },
  preorder: { color: "var(--yellow-text)", bg: "rgba(255,203,46,.12)" },
  out_of_stock: { color: "var(--red-text)", bg: "rgba(244,88,95,.1)" },
  unknown: { color: "var(--muted2)", bg: "var(--panel2)" },
};

const FLIP_TONE = {
  buy: { color: "var(--green-text)", bg: "rgba(52,211,153,.12)" },
  fair: { color: "var(--blue-soft)", bg: "rgba(61,123,255,.1)" },
  pass: { color: "var(--red-text)", bg: "rgba(244,88,95,.1)" },
};

// Accesseurs de tri (niveau module → identité stable pour useSortable).
const SORTS = {
  product: (o) => (o.title || o.url || "").toLowerCase(),
  retailer: (o) => (o.retailer || "").toLowerCase(),
  state: (o) => o.stock_state || "",
  price: (o) => (o.price != null ? Number(o.price) : null),
  market: (o) => (o.market_value != null ? Number(o.market_value) : null),
  changed: (o) => o.last_changed_at || o.last_checked_at || "",
};

const GRID = "minmax(0,1fr) 88px 116px 72px 78px 112px 60px";

function host(url) {
  try {
    return new URL(url).host.replace(/^www\./, "");
  } catch {
    return "—";
  }
}

function KpiCard({ label, value, pillColor, pillBg, barPct, barGrad, sub }) {
  return (
    <div className="rounded-2xl p-5" style={panel}>
      <div className="flex items-center justify-between">
        <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-slate-500">{label}</div>
        {pillColor && <span style={{ width: 8, height: 8, borderRadius: "50%", background: pillColor }} />}
      </div>
      <div className="mt-3 font-mono text-[32px] font-bold leading-none">{value}</div>
      <div className="mt-3 h-1 overflow-hidden rounded" style={{ background: "var(--bar)" }}>
        <div style={{ width: `${Math.max(0, Math.min(100, barPct || 0))}%`, height: "100%", borderRadius: 2, transformOrigin: "left", animation: "pa-grow .9s cubic-bezier(.22,1,.36,1) both", background: barGrad }} />
      </div>
      {sub && <div className="mt-2.5 text-[12.5px] text-slate-500">{sub}</div>}
    </div>
  );
}

export default function Restock() {
  const { token } = useAuth();
  const { t } = useI18n();
  const { data: offers, reload } = usePolling("/retail/offers?watched=true", { intervalSec: 30 });
  const [url, setUrl] = useState("");
  const [msg, setMsg] = useState(null);

  const list = offers || [];
  const { sorted, sort, toggle } = useSortable(list, SORTS);
  const count = (s) => list.filter((o) => o.stock_state === s).length;
  const inStock = count("in_stock");
  const preorder = count("preorder");
  const out = list.length - inStock - preorder;

  async function addByUrl(e) {
    e.preventDefault();
    setMsg(null);
    if (!url.trim().startsWith("http")) return setMsg(t("restock.add.invalid"));
    try {
      const res = await api.post(token, "/retail/offers", { url: url.trim() });
      setMsg(res.note || t("restock.add.ok"));
      setUrl("");
      reload();
    } catch (e2) {
      setMsg(e2.message.includes("400") ? t("restock.add.notfound") : `Erreur : ${e2.message}`);
    }
  }

  async function unwatch(o) {
    await api.put(token, `/retail/offers/${o.id}`, { is_watched: false });
    reload();
  }

  const TIERS = ["hot", "normal", "cold"];
  async function cycleTier(o) {
    const next = TIERS[(TIERS.indexOf(o.watch_tier || "normal") + 1) % 3];
    await api.put(token, `/retail/offers/${o.id}`, { watch_tier: next });
    reload();
  }
  async function recheck(o) {
    setMsg(null);
    try {
      const r = await api.post(token, `/retail/offers/${o.id}/recheck`);
      setMsg(`Re-check ${o.title || o.id} : ${r.status}${r.transition ? " · restock !" : ""}`);
      reload();
    } catch (e2) {
      setMsg(`Erreur : ${e2.message}`);
    }
  }

  const TIER_TONE = {
    hot: { color: "var(--red-text)", bg: "rgba(244,88,95,.14)" },
    normal: { color: "var(--blue-soft)", bg: "rgba(61,123,255,.1)" },
    cold: { color: "var(--muted2)", bg: "var(--panel2)" },
  };

  return (
    <div className="space-y-7">
      {/* Header */}
      <div>
        <div className="mb-3 inline-flex items-center gap-2 rounded-full px-3 py-1" style={{ border: "1px solid var(--border2)", background: "var(--panel2)" }}>
          <span className="font-mono text-[9.5px] tracking-[0.14em] text-slate-500">POKÉSTOCK FR</span>
          <span style={{ width: 4, height: 4, borderRadius: "50%", background: "var(--faint)" }} />
          <span className="font-mono text-[9.5px] tracking-[0.12em]" style={{ color: "var(--green-text)" }}>
            {t("restock.retailers")}
          </span>
        </div>
        <h1 className="text-[30px] font-extrabold tracking-tight">{t("restock.title")}</h1>
        <p className="mt-1.5 max-w-[560px] text-sm text-slate-500">{t("restock.subtitle")}</p>
      </div>

      {/* Surveillance overview */}
      <div>
        <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-slate-500">{t("restock.section.overview")}</div>
        <div className="mt-3 grid grid-cols-2 gap-3.5 lg:grid-cols-4">
          <KpiCard label={t("restock.kpi.watched")} value={list.length} pillColor="var(--blue-soft)" barPct={100} barGrad="linear-gradient(90deg, #2E5FD6, #3D7BFF)" />
          <KpiCard label={t("restock.kpi.instock")} value={inStock} pillColor="var(--green-text)" barPct={list.length ? (inStock / list.length) * 100 : 0} barGrad="linear-gradient(90deg, #1FA371, #34D399)" />
          <KpiCard label={t("restock.kpi.preorder")} value={preorder} pillColor="var(--yellow-text)" barPct={list.length ? (preorder / list.length) * 100 : 0} barGrad="linear-gradient(90deg, #D6A21F, #FFCB2E)" />
          <KpiCard label={t("restock.kpi.out")} value={out} pillColor="var(--red-text)" barPct={list.length ? (out / list.length) * 100 : 0} barGrad="linear-gradient(90deg, #C23A40, #F4585F)" />
        </div>
      </div>

      {/* Watched offers */}
      <div className="overflow-hidden rounded-2xl" style={panel}>
        <div className="border-b p-4" style={{ borderColor: "var(--line)" }}>
          <div className="text-[15px] font-bold">{t("restock.offers.title")}</div>
          <form onSubmit={addByUrl} className="mt-3 flex gap-2">
            <input
              className="min-w-0 flex-1 rounded-lg border px-3 py-2.5 text-sm text-slate-100"
              style={{ borderColor: "var(--border2)", background: "var(--panel2)" }}
              placeholder={t("restock.add.placeholder")}
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
            <button
              type="submit"
              className="flex-none rounded-lg px-4 py-2.5 text-sm font-bold text-white"
              style={{ background: "linear-gradient(180deg, #4D87FF, #3D7BFF)" }}
            >
              {t("restock.add.submit")}
            </button>
          </form>
          {msg && <div className="mt-2 font-mono text-[11px] text-slate-400">{msg}</div>}
        </div>

        {/* column header */}
        <div
          className="grid items-center gap-2.5 border-b px-4 py-2.5 font-mono text-[9px] uppercase tracking-[0.12em] text-slate-500"
          style={{ borderColor: "var(--line)", gridTemplateColumns: GRID }}
        >
          <SortHeader label={t("restock.col.product")} k="product" sort={sort} onToggle={toggle} />
          <SortHeader label={t("restock.col.retailer")} k="retailer" sort={sort} onToggle={toggle} />
          <SortHeader label={t("restock.col.state")} k="state" sort={sort} onToggle={toggle} />
          <SortHeader label={t("restock.col.price")} k="price" sort={sort} onToggle={toggle} align="right" />
          <SortHeader label={t("restock.col.market")} k="market" sort={sort} onToggle={toggle} align="right" />
          <div>{t("restock.col.flip")}</div>
          <SortHeader label={t("restock.col.changed")} k="changed" sort={sort} onToggle={toggle} align="right" />
        </div>

        {sorted.length === 0 ? (
          <div className="px-4 py-10 text-center text-sm text-slate-500">{t("restock.empty")}</div>
        ) : (
          sorted.map((o) => {
            const st = STATE[o.stock_state] || STATE.unknown;
            const ft = FLIP_TONE[o.verdict_tone];
            return (
              <div
                key={o.id}
                className="grid items-center gap-2.5 border-b px-4 py-3.5"
                style={{ borderColor: "var(--line)", gridTemplateColumns: GRID }}
              >
                <div className="flex min-w-0 items-center gap-2.5">
                  <ProductImage src={o.image_url} alt={o.title || o.url} seed={o.retailer}
                                style={{ width: 34, height: 46 }} />
                  <div className="min-w-0">
                    <div className="truncate text-sm font-semibold">{o.title || o.url}</div>
                    <div className="mt-0.5 flex items-center gap-2">
                      <a href={o.url} target="_blank" rel="noreferrer" className="font-mono text-[10px]" style={{ color: "var(--blue-soft)" }}>
                        {host(o.url)}
                      </a>
                      <button onClick={() => cycleTier(o)} title="Cliquer pour changer le tier de surveillance"
                              className="rounded font-mono text-[9px] font-bold uppercase" style={{ padding: "1px 5px", ...(TIER_TONE[o.watch_tier || "normal"]) }}>
                        {o.watch_tier || "normal"}
                      </button>
                      <button onClick={() => recheck(o)} title="Re-check immédiat" className="border-none bg-transparent p-0 font-mono text-[11px] text-slate-500 hover:text-info">↻</button>
                      <button onClick={() => unwatch(o)} className="border-none bg-transparent p-0 font-mono text-[10px] text-slate-600 hover:text-critical">
                        {t("restock.remove")}
                      </button>
                    </div>
                  </div>
                </div>
                <div className="font-mono text-[11.5px] text-slate-400">{o.retailer}</div>
                <div>
                  <span className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-semibold" style={{ color: st.color, background: st.bg }}>
                    {t(`restock.state.${o.stock_state}`) || t("restock.state.unknown")}
                  </span>
                </div>
                <div className="text-right font-mono text-[13px] font-semibold">{eur(o.price)}</div>
                <div className="text-right font-mono text-[12px] text-slate-400">
                  {o.market_value != null ? eur(o.market_value) : "—"}
                </div>
                <div>
                  {o.verdict ? (
                    <span className="inline-flex items-center gap-1 rounded-md px-2 py-1 font-mono text-[10.5px] font-bold" style={{ color: ft?.color, background: ft?.bg }}>
                      {o.verdict}
                      {o.upside_pct != null && (
                        <span className="font-normal">{o.upside_pct >= 0 ? "+" : ""}{o.upside_pct}%</span>
                      )}
                    </span>
                  ) : (
                    <span className="font-mono text-[10px] text-slate-600">— non lié</span>
                  )}
                </div>
                <div className="text-right font-mono text-[10.5px] text-slate-600">
                  {(o.last_changed_at || o.last_checked_at || "").replace("T", " ").slice(5, 16) || "—"}
                </div>
              </div>
            );
          })
        )}
      </div>
      <p className="font-mono text-[10.5px] leading-relaxed text-slate-600">{t("restock.foot")}</p>
    </div>
  );
}
