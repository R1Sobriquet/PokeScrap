import { useMemo, useState } from "react";
import { useI18n } from "../i18n.jsx";

// Pur cosmétique : ouverture de booster simulée (aucune donnée réelle).
const ARTS = [
  "linear-gradient(155deg, #1A1030, #5B3FA8 56%, #C9B8FF)",
  "linear-gradient(155deg, #0A3A4A, #2FB6C9 60%, #CFF6FF)",
  "linear-gradient(155deg, #7A1220, #F4585F 60%, #FFC2A8)",
  "linear-gradient(155deg, #123B7A, #3D7BFF 60%, #8FD0FF)",
  "linear-gradient(155deg, #6E2A08, #FF8A3D 58%, #FFE0B8)",
  "linear-gradient(155deg, #0E4D43, #34D399 60%, #C7F9E5)",
];
const NAMES = ["Umbreon VMAX", "Charizard ex", "Pikachu V", "Mewtwo GX", "Rayquaza VMAX", "Gengar VMAX", "Lugia V", "Giratina V"];
const TIERS = [
  { tier: "★ GRAIL", color: "#FFD75A" },
  { tier: "◆ RARE", color: "#C9B8FF" },
  { tier: "◆ HOLO", color: "#9BE9F5" },
  { tier: "● COMMON", color: "#A7B0C3" },
];
const CONFETTI = ["#FFD75A", "#9B7BFF", "#34D399", "#3D7BFF", "#F4585F", "#2FB6C9"];

function rnd(arr) {
  return arr[Math.floor(Math.random() * arr.length)];
}

function drawCards() {
  return Array.from({ length: 5 }, (_, i) => {
    const t = rnd(TIERS);
    return {
      id: i,
      name: rnd(NAMES),
      art: ARTS[(Math.floor(Math.random() * ARTS.length) + i) % ARTS.length],
      tier: t.tier,
      tierColor: t.color,
      value: `$${(Math.random() * 1400 + 20).toFixed(0)}`,
      rot: `${(Math.random() * 6 - 3).toFixed(1)}deg`,
      glow: t.tier.startsWith("★") ? "0 0 40px rgba(255,215,90,.5), 0 0 0 1px rgba(255,255,255,.2)" : "0 16px 36px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.15)",
      delay: `${(i * 0.09).toFixed(2)}s`,
    };
  });
}

export default function PackModal({ open, onClose }) {
  const { t } = useI18n();
  const [ripped, setRipped] = useState(false);
  const cards = useMemo(() => (ripped ? drawCards() : []), [ripped]);
  const confetti = useMemo(
    () =>
      Array.from({ length: 14 }, () => ({
        left: `${Math.random() * 100}%`,
        w: `${6 + Math.random() * 6}px`,
        h: `${8 + Math.random() * 8}px`,
        bg: rnd(CONFETTI),
        dur: `${1.4 + Math.random() * 1.4}s`,
        delay: `${Math.random() * 0.5}s`,
      })),
    [ripped]
  );

  if (!open) return null;
  const close = () => {
    setRipped(false);
    onClose();
  };

  return (
    <div role="dialog" aria-modal="true" style={{ position: "fixed", inset: 0, zIndex: 450, background: "rgba(6,4,16,.85)", backdropFilter: "blur(16px)", display: "flex", alignItems: "center", justifyContent: "center" }}>
      <button onClick={close} style={{ position: "absolute", top: 24, right: 28, width: 38, height: 38, borderRadius: 12, border: "1px solid rgba(255,255,255,.2)", background: "rgba(255,255,255,.07)", color: "#F2F5FB", fontSize: 16, cursor: "pointer" }}>✕</button>

      {!ripped ? (
        <div onClick={() => setRipped(true)} style={{ cursor: "pointer", textAlign: "center", animation: "pa-floaty 4s ease-in-out infinite" }}>
          <div style={{ width: 210, height: 330, margin: "0 auto", borderRadius: 14, position: "relative", overflow: "hidden", background: "linear-gradient(160deg, #16306E, #3D7BFF 45%, #9B7BFF 75%, #FFCB2E 130%)", boxShadow: "0 30px 80px rgba(61,123,255,.35), inset 0 0 0 1px rgba(255,255,255,.25)" }}>
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 30, background: "repeating-linear-gradient(90deg, rgba(255,255,255,.3) 0 5px, rgba(255,255,255,.05) 5px 10px)", borderBottom: "2px dashed rgba(255,255,255,.5)" }} />
            <div style={{ position: "absolute", inset: 0, background: "linear-gradient(110deg, transparent 30%, rgba(255,255,255,.22) 48%, transparent 62%)", backgroundSize: "200% 100%", animation: "pa-holo 3.2s linear infinite" }} />
            <div style={{ position: "absolute", left: 0, right: 0, top: "44%", transform: "translateY(-50%)", textAlign: "center" }}>
              <div style={{ fontSize: 24, fontWeight: 800, color: "#FFFFFF", letterSpacing: "-0.02em", textShadow: "0 2px 16px rgba(0,0,0,.4)" }}>
                Poké<span style={{ color: "#FFD75A" }}>Alpha</span>
              </div>
              <div className="font-mono" style={{ fontSize: 8.5, letterSpacing: ".22em", color: "rgba(255,255,255,.85)", marginTop: 6 }}>{t("pack.simulated")}</div>
            </div>
            <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, height: 26, background: "repeating-linear-gradient(90deg, rgba(255,255,255,.3) 0 5px, rgba(255,255,255,.05) 5px 10px)", borderTop: "2px dashed rgba(255,255,255,.4)" }} />
          </div>
          <div className="font-mono" style={{ marginTop: 26, fontSize: 11, letterSpacing: ".2em", color: "#C9B8FF", animation: "pa-pulse 2s infinite" }}>{t("pack.clickToRip")}</div>
        </div>
      ) : (
        <div style={{ position: "relative", width: "min(1100px, 94vw)", textAlign: "center" }}>
          <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
            {confetti.map((cf, i) => (
              <span key={i} style={{ position: "absolute", top: -10, left: cf.left, width: cf.w, height: cf.h, background: cf.bg, borderRadius: 2, animation: `pa-confetti ${cf.dur} ease-in ${cf.delay} both` }} />
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: 18, flexWrap: "wrap" }}>
            {cards.map((c) => (
              <div key={c.id} style={{ width: 158, animation: `pa-cardup .7s cubic-bezier(.2,1.25,.3,1) ${c.delay} both` }}>
                <div style={{ height: 218, borderRadius: 12, position: "relative", overflow: "hidden", transform: `rotate(${c.rot})`, background: c.art, boxShadow: c.glow }}>
                  <div style={{ position: "absolute", inset: 0, background: "linear-gradient(110deg, transparent 35%, rgba(255,255,255,.2) 50%, transparent 65%)", backgroundSize: "200% 100%", animation: "pa-holo 3.6s linear infinite" }} />
                  <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, padding: "10px 12px", background: "linear-gradient(transparent, rgba(6,6,14,.85) 38%)" }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: "#FFFFFF", lineHeight: 1.2 }}>{c.name}</div>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 5 }}>
                      <span className="font-mono" style={{ fontSize: 7.5, letterSpacing: ".1em", color: c.tierColor }}>{c.tier}</span>
                      <span className="font-mono" style={{ fontSize: 11, fontWeight: 700, color: "#FFFFFF" }}>{c.value}</span>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", justifyContent: "center", gap: 12, marginTop: 36 }}>
            <button onClick={() => setRipped(false)} className="text-ink" style={{ padding: "13px 26px", borderRadius: 12, border: "none", background: "linear-gradient(180deg, #FFD75A, #FFC91F)", fontSize: 14.5, fontWeight: 700, cursor: "pointer" }}>
              {t("pack.again")}
            </button>
            <button onClick={close} style={{ padding: "13px 26px", borderRadius: 12, border: "1px solid rgba(255,255,255,.25)", background: "rgba(255,255,255,.07)", color: "#F2F5FB", fontSize: 14.5, fontWeight: 600, cursor: "pointer" }}>
              {t("pack.done")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
