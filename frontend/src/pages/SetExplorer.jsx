import { useNavigate } from "react-router-dom";
import { usePolling } from "../hooks/usePolling.js";
import { useI18n } from "../i18n.jsx";
import { PageHeader, pct } from "../components/ui.jsx";
import ProductImage from "../components/ProductImage.jsx";

const panel = { background: "var(--panel)", border: "1px solid var(--border)" };

export default function SetExplorer() {
  const navigate = useNavigate();
  const { t } = useI18n();
  const { data: sets } = usePolling("/tracked-sets", { intervalSec: 120 });
  const { data: movers } = usePolling("/movers");
  const list = sets || [];
  const allMovers = movers || [];

  return (
    <div className="space-y-6">
      <PageHeader title={t("explorer.title")} subtitle={t("explorer.subtitle")} />

      {list.length === 0 ? (
        <div className="rounded-2xl p-10 text-center text-sm text-slate-500" style={panel}>{t("explorer.empty")}</div>
      ) : (
        <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 lg:grid-cols-4">
          {list.map((s) => {
            const sm = allMovers.filter((m) => m.set_slug === s.set_slug);
            const avg = sm.length ? sm.reduce((a, m) => a + (m.rise_pct || 0), 0) / sm.length : null;
            const up = (avg ?? 0) >= 0;
            return (
              <button key={s.id} onClick={() => navigate(`/set/${s.set_slug}`)}
                      className="overflow-hidden rounded-2xl text-left transition-transform hover:-translate-y-1" style={{ ...panel }}>
                <ProductImage alt={s.name} seed={s.set_slug} rounded={0} style={{ width: "100%", height: 118 }} />
                <div className="p-4">
                  <div className="truncate text-[15px] font-bold">{s.name}</div>
                  <div className="mt-1 font-mono text-[9.5px] uppercase tracking-[0.12em] text-slate-500">{s.set_slug}</div>
                  <div className="mt-3 flex items-end justify-between">
                    <div>
                      <div className="font-mono text-[22px] font-bold leading-none">{sm.length}</div>
                      <div className="mt-1 font-mono text-[8.5px] uppercase tracking-[0.13em] text-slate-500">{t("explorer.movers")}</div>
                    </div>
                    {avg != null && (
                      <span className="font-mono text-[12px]" style={{ color: up ? "var(--green-text)" : "var(--red-text)" }}>
                        {up ? "▲" : "▼"} {pct(avg)}
                      </span>
                    )}
                  </div>
                  <div className="mt-3 flex items-center justify-between border-t pt-2.5" style={{ borderColor: "var(--line)" }}>
                    {s.is_active
                      ? <span className="rounded-full px-2 py-0.5 text-[11px] font-semibold" style={{ color: "var(--green-text)", background: "rgba(52,211,153,.1)" }}>ON</span>
                      : <span className="rounded-full px-2 py-0.5 text-[11px] text-slate-500" style={{ background: "var(--panel2)" }}>off</span>}
                    <span className="font-mono text-[11px] text-slate-500">{t("explorer.score")}</span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
