import { usePolling } from "../hooks/usePolling.js";
import { useI18n } from "../i18n.jsx";

const panel = { background: "var(--panel)", border: "1px solid var(--border2)" };

// Score pseudo-déterministe par produit (stable au refresh). PLACEHOLDER : sera
// remplacé par un vrai modèle prédictif (hype / confiance / popularité / ROI).
function hashScore(str, salt, lo, hi) {
  let h = 2166136261;
  for (const ch of `${str}|${salt}`) h = (Math.imul(h ^ ch.charCodeAt(0), 16777619)) >>> 0;
  return lo + (h % (hi - lo + 1));
}

const MONTHS = {
  fr: ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."],
  en: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
};

function parseDate(s) {
  if (!s) return null;
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? null : d;
}

function statusOf(rel, now) {
  const rd = parseDate(rel.release_date);
  const pd = parseDate(rel.preorder_date);
  if (rd && rd < now) return "released";
  if (pd && pd <= now && (!rd || rd >= now)) return "preorder";
  if (rd) return "confirmed";
  return "rumored";
}

const STATUS_STYLE = {
  rumored: { color: "var(--violet-text)", bg: "rgba(155,123,255,.08)" },
  preorder: { color: "var(--blue-soft)", bg: "rgba(61,123,255,.1)" },
  confirmed: { color: "var(--green-text)", bg: "rgba(52,211,153,.1)" },
  released: { color: "var(--muted2)", bg: "var(--panel2)" },
};

function Metric({ label, value, color, barPct, barColor }) {
  return (
    <div>
      <div className="flex justify-between font-mono text-[9.5px] tracking-[0.11em] text-slate-500">
        <span>{label}</span>
        <span style={{ color }}>{value}</span>
      </div>
      <div className="mt-1.5 h-1 overflow-hidden rounded" style={{ background: "var(--bar)" }}>
        <div style={{ width: `${barPct}%`, height: "100%", borderRadius: 2, transformOrigin: "left", animation: "pa-grow .9s cubic-bezier(.22,1,.36,1) both", background: barColor }} />
      </div>
    </div>
  );
}

export default function FutureRadar() {
  const { data: releases } = usePolling("/releases", { intervalSec: 120 });
  const { t, lang } = useI18n();
  const now = new Date();
  const list = releases || [];

  function windowLabel(rel) {
    const d = parseDate(rel.release_date) || parseDate(rel.preorder_date);
    if (!d) return "TBA";
    return `${MONTHS[lang === "en" ? "en" : "fr"][d.getMonth()]} ${d.getFullYear()}`;
  }

  return (
    <div className="space-y-7">
      {/* Header centré */}
      <div className="text-center">
        <div className="inline-flex items-center gap-2 rounded-full px-3 py-1.5" style={{ border: "1px solid rgba(155,123,255,.35)", background: "rgba(155,123,255,.1)" }}>
          <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--violet)", animation: "pa-pulse 2s infinite" }} />
          <span className="font-mono text-[10.5px] tracking-[0.16em]" style={{ color: "var(--violet-text)" }}>{t("future.badge")}</span>
        </div>
        <h1 className="mt-4 text-[40px] font-extrabold tracking-tight">{t("future.title")}</h1>
        <p className="mx-auto mt-3 max-w-[560px] text-[15.5px] leading-relaxed text-slate-500">{t("future.subtitle")}</p>
      </div>

      {list.length === 0 ? (
        <div className="rounded-2xl p-12 text-center text-sm text-slate-500" style={panel}>{t("future.empty")}</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {list.map((rel, i) => {
            const status = statusOf(rel, now);
            const ss = STATUS_STYLE[status];
            const hype = hashScore(rel.product_name, "hype", 52, 97);
            const conf = hashScore(rel.product_name, "conf", 48, 95);
            const pop = hashScore(rel.product_name, "pop", 45, 96);
            const roi = hashScore(rel.product_name, "roi", 40, 220);
            return (
              <div key={rel.id ?? i} className="overflow-hidden rounded-2xl p-6 transition-transform hover:-translate-y-1" style={panel}>
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] tracking-[0.15em] text-slate-500">№ {String(i + 1).padStart(2, "0")}</span>
                  <span className="font-mono text-[9.5px] tracking-[0.12em]" style={{ padding: "4px 10px", borderRadius: 6, transform: "rotate(2deg)", border: `1px dashed ${ss.color}`, color: ss.color, background: ss.bg }}>
                    {t(`future.status.${status}`)}
                  </span>
                </div>
                <div className="mt-3.5 text-[25px] font-extrabold tracking-tight">{rel.product_name}</div>
                <div className="mt-1.5 font-mono text-[10.5px] tracking-[0.13em] text-slate-500">
                  {rel.set_name ? `${rel.set_name} · ` : ""}{rel.product_type || "—"} · {t("future.expected")} {windowLabel(rel)}
                </div>

                <div className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3.5 border-t pt-4" style={{ borderColor: "var(--line)" }}>
                  <Metric label={t("future.metric.hype")} value={hype} color="var(--yellow-text)" barPct={hype} barColor="#FFCB2E" />
                  <Metric label={t("future.metric.conf")} value={conf} color="var(--blue-soft)" barPct={conf} barColor="#3D7BFF" />
                  <Metric label={t("future.metric.pop")} value={pop} color="var(--violet-text)" barPct={pop} barColor="#9B7BFF" />
                  <div>
                    <div className="font-mono text-[9.5px] tracking-[0.11em] text-slate-500">{t("future.metric.roi")}</div>
                    <div className="font-mono text-[21px] font-bold leading-none" style={{ color: "var(--gold)", marginTop: 2 }}>+{roi}%</div>
                  </div>
                </div>

                {rel.source_note && (
                  <div className="mt-4 pl-3 text-[13px] leading-relaxed text-slate-400" style={{ borderLeft: "2px solid rgba(155,123,255,.4)" }}>
                    {rel.source_note}
                  </div>
                )}
                <div className="mt-3 font-mono text-[9px] uppercase tracking-[0.12em] text-slate-600">{t("future.provisional")}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
