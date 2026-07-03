import { useNavigate, useParams } from "react-router-dom";
import { usePolling } from "../hooks/usePolling.js";
import { useI18n } from "../i18n.jsx";
import { eur, panel, pct } from "../components/ui.jsx";
import ProductImage from "../components/ProductImage.jsx";


function LockedPanel({ title, tag, tagColor, note, onUpgrade, t }) {
  return (
    <div className="rounded-2xl p-5" style={panel}>
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-slate-500">{title}</span>
        <span className="font-mono text-[9px] uppercase tracking-[0.12em]" style={{ color: tagColor }}>{tag}</span>
      </div>
      <div className="mt-3 flex h-[150px] flex-col items-center justify-center gap-3 rounded-xl" style={{ border: "1px dashed var(--border2)" }}>
        <span className="text-[13px] text-slate-500">{note}</span>
        <button onClick={onUpgrade} className="rounded-lg px-4 py-2 text-[12.5px] font-bold text-ink" style={{ background: "linear-gradient(180deg, #FFD75A, #FFC91F)" }}>
          {t("setd.upgrade")}
        </button>
      </div>
    </div>
  );
}

function MoverRow({ m }) {
  const up = (m.rise_pct ?? 0) >= 0;
  return (
    <div className="flex items-center gap-3 rounded-xl p-3" style={panel}>
      <ProductImage src={m.image_url} alt={m.name} seed={m.set_slug} style={{ width: 38, height: 52 }} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[14px] font-bold">{m.name}</div>
        <div className="mt-0.5 font-mono text-[10px] text-slate-500">{m.volume ?? "—"} ventes</div>
      </div>
      <div className="text-right">
        <div className="font-mono text-[14px] font-bold">{eur(m.price)}</div>
        <div className="font-mono text-[10.5px]" style={{ color: up ? "var(--green-text)" : "var(--red-text)" }}>
          {up ? "▲" : "▼"} {pct(m.rise_pct)}
        </div>
      </div>
    </div>
  );
}

export default function SetDetail() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { t } = useI18n();
  const { data: movers } = usePolling(`/movers?set=${encodeURIComponent(slug)}`);
  const { data: sets } = usePolling("/tracked-sets", { intervalSec: 120 });
  const { data: watch } = usePolling("/watchlist");

  const setMovers = movers || [];
  const meta = (sets || []).find((s) => s.set_slug === slug);
  const name = meta?.name || slug;
  const products = (watch || []).filter((w) => w.product?.set_slug === slug);
  const avg = setMovers.length ? setMovers.reduce((a, m) => a + (m.rise_pct || 0), 0) / setMovers.length : null;
  const up = (avg ?? 0) >= 0;

  return (
    <div className="space-y-6">
      <button onClick={() => navigate("/explorer")} className="inline-flex items-center rounded-lg px-3.5 py-2 text-[13px] font-semibold text-slate-400 hover:text-slate-100"
              style={{ border: "1px solid var(--border2)", background: "var(--panel)" }}>
        {t("setd.back")}
      </button>

      {/* Header */}
      <div className="flex flex-wrap items-center gap-5">
        <ProductImage alt={name} seed={slug} rounded={18} style={{ width: 88, height: 88 }} />
        <div className="min-w-[240px] flex-1">
          <h1 className="text-[32px] font-extrabold tracking-tight">{name}</h1>
          <div className="mt-1.5 font-mono text-[11px] uppercase tracking-[0.13em] text-slate-500">{slug}</div>
        </div>
        {avg != null && (
          <div className="text-right">
            <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-slate-500">{t("explorer.score")}</div>
            <div className="mt-1 font-mono text-[36px] font-bold leading-none" style={{ color: up ? "var(--green-text)" : "var(--red-text)" }}>
              {up ? "▲" : "▼"} {pct(avg)}
            </div>
          </div>
        )}
      </div>

      {/* Movers + products */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div>
          <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-slate-500">{t("setd.movers")}</div>
          <div className="mt-3 flex flex-col gap-2.5">
            {setMovers.length === 0
              ? <div className="rounded-xl p-5 text-center text-sm text-slate-500" style={panel}>{t("setd.movers.empty")}</div>
              : setMovers.slice(0, 6).map((m) => <MoverRow key={m.product_id} m={m} />)}
          </div>
        </div>
        <div>
          <div className="font-mono text-[11px] uppercase tracking-[0.16em] text-slate-500">{t("setd.products")}</div>
          <div className="mt-3 flex flex-col gap-2.5">
            {products.length === 0
              ? <div className="rounded-xl p-5 text-center text-sm text-slate-500" style={panel}>{t("setd.products.empty")}</div>
              : products.map((p) => (
                  <div key={p.product_id} className="flex items-center gap-3 rounded-xl p-3" style={panel}>
                    <ProductImage src={p.product?.image_url} alt={p.product?.name} seed={slug} style={{ width: 38, height: 52 }} />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-[14px] font-bold">{p.product?.name}</div>
                      <div className="mt-0.5 font-mono text-[10px] text-slate-500">{p.tier} · {p.product?.card_number || "—"}</div>
                    </div>
                    <div className="font-mono text-[13px] font-semibold">{eur(p.latest?.price_avg)}</div>
                  </div>
                ))}
          </div>
        </div>
      </div>

      {/* Pop / volume — fonctions premium (verrouillées) */}
      <div className="grid gap-4 lg:grid-cols-2">
        <LockedPanel title={t("setd.pop.title")} tag="PREMIUM" tagColor="var(--yellow-text)"
                     note={t("setd.pop.locked")} onUpgrade={() => navigate("/reglages")} t={t} />
        <LockedPanel title={t("setd.vol.title")} tag="ALPHA" tagColor="var(--violet-text)"
                     note={t("setd.vol.locked")} onUpgrade={() => navigate("/reglages")} t={t} />
      </div>
    </div>
  );
}
