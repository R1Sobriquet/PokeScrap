import { Suspense, lazy, useEffect, useMemo, useState } from "react";
import { useI18n } from "../i18n.jsx";
import { Confetti } from "./motion.jsx";
import PackModal from "./PackModal.jsx"; // repli 2D (CSS) si WebGL indispo

const PackOpen3D = lazy(() => import("./PackOpen3D.jsx"));

function webglOK() {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl") || c.getContext("experimental-webgl")));
  } catch {
    return false;
  }
}

const ACCENTS = ["#5B3FA8", "#2FB6C9", "#F4585F", "#3D7BFF", "#FF8A3D", "#34D399"];
const NAMES = ["Umbreon VMAX", "Charizard ex", "Pikachu V", "Mewtwo GX", "Rayquaza VMAX", "Gengar VMAX", "Lugia V", "Giratina V"];
const TIERS = [
  { tier: "★ GRAIL", color: "#FFD75A" },
  { tier: "◆ RARE", color: "#C9B8FF" },
  { tier: "◆ HOLO", color: "#9BE9F5" },
  { tier: "● COMMON", color: "#A7B0C3" },
];
const rnd = (a) => a[Math.floor(Math.random() * a.length)];

function draw() {
  return Array.from({ length: 5 }, (_, i) => {
    const tr = rnd(TIERS);
    return { id: `${i}-${Math.random().toString(36).slice(2)}`, name: rnd(NAMES),
      tier: tr.tier, tierColor: tr.color, value: `$${(Math.random() * 1400 + 20).toFixed(0)}`, accent: rnd(ACCENTS) };
  });
}

function Pack3DModal({ open, onClose }) {
  const { t } = useI18n();
  const [ripped, setRipped] = useState(false);
  const [cards, setCards] = useState(draw);

  const close = () => { setRipped(false); setCards(draw()); onClose(); };
  const again = () => { setCards(draw()); setRipped(false); };

  // Échap ferme le modal (accessibilité clavier).
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === "Escape") close(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!open) return null;

  return (
    <div role="dialog" aria-modal="true" aria-label={t("pack.cta")}
      style={{ position: "fixed", inset: 0, zIndex: 450, background: "rgba(6,4,16,.86)", backdropFilter: "blur(16px)",
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
      <button onClick={close} style={{ position: "absolute", top: 24, right: 28, width: 38, height: 38, borderRadius: 12,
        border: "1px solid rgba(255,255,255,.2)", background: "rgba(255,255,255,.07)", color: "#F2F5FB", fontSize: 16, cursor: "pointer" }}>✕</button>

      <div style={{ position: "relative", width: "min(900px, 94vw)" }}>
        <Confetti fire={ripped} count={30} />
        <Suspense fallback={<div style={{ height: 460, display: "flex", alignItems: "center", justifyContent: "center", color: "#C9B8FF" }}>3D…</div>}>
          <PackOpen3D cards={cards} ripped={ripped} onRip={() => setRipped(true)} accent={cards[0]?.accent} />
        </Suspense>
      </div>

      {!ripped ? (
        <div className="font-mono" style={{ marginTop: 6, fontSize: 11, letterSpacing: ".2em", color: "#C9B8FF", animation: "pa-pulse 2s infinite" }}>
          {t("pack.clickToRip")}
        </div>
      ) : (
        <div style={{ display: "flex", gap: 12, marginTop: 14 }}>
          <button onClick={again} className="text-ink" style={{ padding: "13px 26px", borderRadius: 12, border: "none",
            background: "linear-gradient(180deg, #FFD75A, #FFC91F)", fontSize: 14.5, fontWeight: 700, cursor: "pointer" }}>
            {t("pack.again")}
          </button>
          <button onClick={close} style={{ padding: "13px 26px", borderRadius: 12, border: "1px solid rgba(255,255,255,.25)",
            background: "rgba(255,255,255,.07)", color: "#F2F5FB", fontSize: 14.5, fontWeight: 600, cursor: "pointer" }}>
            {t("pack.done")}
          </button>
        </div>
      )}
    </div>
  );
}

// Ouvre l'expérience 3D si WebGL est dispo, sinon le modal 2D existant.
export default function PackExperience({ open, onClose }) {
  const ok = useMemo(webglOK, []);
  if (!ok) return <PackModal open={open} onClose={onClose} />;
  return <Pack3DModal open={open} onClose={onClose} />;
}
