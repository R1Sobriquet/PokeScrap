import { useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { useI18n } from "../i18n.jsx";
import { eur } from "../components/ui.jsx";

const TONE = {
  buy: { color: "var(--green-text)", bg: "rgba(52,211,153,.08)", border: "rgba(52,211,153,.4)", glow: "rgba(52,211,153,.25)", icon: "▲" },
  fair: { color: "var(--blue-soft)", bg: "rgba(61,123,255,.07)", border: "rgba(61,123,255,.35)", glow: "rgba(61,123,255,.18)", icon: "◆" },
  warn: { color: "var(--yellow-text)", bg: "rgba(255,203,46,.07)", border: "rgba(255,203,46,.4)", glow: "rgba(255,203,46,.2)", icon: "▲" },
  pass: { color: "var(--red-text)", bg: "rgba(244,88,95,.07)", border: "rgba(244,88,95,.4)", glow: "rgba(244,88,95,.2)", icon: "▼" },
};

function Cell({ label, value, color }) {
  return (
    <div style={{ background: "var(--panel-solid)", padding: "18px 22px" }}>
      <div className="font-mono text-[9.5px] tracking-[0.13em] text-slate-500">{label}</div>
      <div className="mt-1.5 font-mono text-[26px] font-bold" style={color ? { color } : undefined}>{value}</div>
    </div>
  );
}

export default function DealAnalyzer() {
  const { token } = useAuth();
  const { t } = useI18n();
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [deal, setDeal] = useState(null);
  const [err, setErr] = useState(null);

  async function analyze(e) {
    e?.preventDefault();
    setErr(null);
    setDeal(null);
    if (!url.trim().startsWith("http")) return setErr(t("analyzer.invalid"));
    setBusy(true);
    try {
      const res = await api.post(token, "/retail/analyze", { url: url.trim() });
      setDeal(res);
    } catch (e2) {
      setErr(e2.message.includes("400") ? t("analyzer.invalid") : t("analyzer.err"));
    } finally {
      setBusy(false);
    }
  }

  const tone = deal ? TONE[deal.verdict_tone] || TONE.fair : null;
  const discount = deal?.discount_pct;
  const discountColor =
    discount == null ? "var(--muted2)" : discount >= 0 ? "var(--green-text)" : "var(--red-text)";
  const noteKey = deal
    ? deal.verdict === "NO COMP"
      ? "analyzer.note.nocomp"
      : `analyzer.note.${deal.verdict_tone}`
    : null;

  return (
    <div className="mx-auto max-w-[780px] space-y-7">
      <div className="text-center">
        <h1 className="text-[36px] font-extrabold tracking-tight">{t("analyzer.title")}</h1>
        <p className="mx-auto mt-3 max-w-[520px] text-[15.5px] leading-relaxed text-slate-500">{t("analyzer.subtitle")}</p>
      </div>

      <form onSubmit={analyze} className="flex gap-2.5">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={t("analyzer.placeholder")}
          className="min-w-0 flex-1 rounded-2xl border px-4 py-3.5 font-mono text-[13px] text-slate-100 outline-none"
          style={{ borderColor: "var(--border2)", background: "var(--panel)" }}
        />
        <button
          type="submit"
          disabled={busy}
          className="flex-none rounded-2xl px-6 py-3.5 text-[15px] font-bold text-ink disabled:opacity-60"
          style={{ background: "linear-gradient(180deg, #A98BFF, #8F6BFF)", boxShadow: "0 8px 26px rgba(143,107,255,.35)" }}
        >
          {t("analyzer.btn")}
        </button>
      </form>
      {err && <p className="font-mono text-[12px] text-critical">{err}</p>}

      {busy && (
        <div className="rounded-2xl p-7 text-center" style={{ border: "1px solid rgba(155,123,255,.35)", background: "rgba(155,123,255,.07)" }}>
          <div className="inline-flex items-center gap-2.5">
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--violet)", boxShadow: "0 0 14px var(--violet)", animation: "pa-pulse 1s infinite" }} />
            <span className="font-mono text-[12px] tracking-[0.1em]" style={{ color: "var(--violet-text)" }}>{t("analyzer.analyzing")}</span>
          </div>
          <div className="mx-auto mt-4 h-1 max-w-[420px] overflow-hidden rounded" style={{ background: "var(--conf-track)" }}>
            <div style={{ height: "100%", background: "linear-gradient(90deg, transparent, #9B7BFF, #FFCB2E, transparent)", backgroundSize: "200% 100%", animation: "pa-holo 1.4s linear infinite" }} />
          </div>
        </div>
      )}

      {deal && deal.status === "ok" && (
        <div className="overflow-hidden rounded-2xl" style={{ border: "1px solid var(--border2)", background: "var(--panel-solid)", boxShadow: "0 24px 70px var(--shadow)" }}>
          <div className="flex items-center justify-between gap-3 border-b px-6 py-4" style={{ borderColor: "var(--line)" }}>
            <div className="flex min-w-0 items-center gap-3">
              <span className="flex-none rounded-md font-mono text-[10px] tracking-[0.12em]" style={{ padding: "4px 10px", color: "var(--blue-soft)", background: "rgba(61,123,255,.12)", border: "1px solid rgba(61,123,255,.3)" }}>
                {deal.source}
              </span>
              <span className="truncate text-[16px] font-bold">{deal.product}</span>
            </div>
            <span className="flex-none rounded-full px-2.5 py-1 font-mono text-[10px] font-semibold" style={{ color: "var(--muted2)", background: "var(--panel2)" }}>
              {t(`restock.state.${deal.stock_state}`) || deal.stock_state}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-px" style={{ background: "var(--line)" }}>
            <Cell label={t("analyzer.listed")} value={eur(deal.listed_price)} />
            <Cell label={t("analyzer.market")} value={deal.market_value_eur != null ? eur(deal.market_value_eur) : "—"} color="var(--muted2)" />
            <Cell
              label={t("analyzer.vsmarket")}
              value={discount == null ? "—" : `${discount > 0 ? "−" : "+"}${Math.abs(discount)}%`}
              color={discountColor}
            />
          </div>

          {deal.matched_name && (
            <div className="border-t px-6 py-3 font-mono text-[11px] text-slate-500" style={{ borderColor: "var(--line)" }}>
              {t("analyzer.matched")} · <span className="text-slate-300">{deal.matched_name}</span>
            </div>
          )}

          <div className="m-6 rounded-2xl p-6 text-center" style={{ background: tone.bg, border: `1px solid ${tone.border}`, boxShadow: `0 0 50px ${tone.glow}` }}>
            <div className="text-[30px] font-extrabold tracking-wide" style={{ color: tone.color }}>
              {tone.icon} {deal.verdict}
            </div>
            <div className="mt-2 text-sm text-slate-400">{noteKey && t(noteKey)}</div>
          </div>
        </div>
      )}

      {deal && deal.status !== "ok" && (
        <div className="rounded-2xl p-6 text-center text-sm text-slate-400" style={{ border: "1px solid var(--border2)", background: "var(--panel)" }}>
          {deal.message || t("analyzer.err")}
        </div>
      )}
    </div>
  );
}
