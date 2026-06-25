import { Suspense, lazy, useMemo } from "react";

// Le moteur 3D (three/r3f) n'est chargé que si WebGL est dispo → jsdom/tests et
// appareils sans WebGL tombent proprement sur un rendu CSS (pas de Canvas monté).
const HoloCard3D = lazy(() => import("./HoloCard3D.jsx"));

function webglOK() {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl") || c.getContext("experimental-webgl")));
  } catch {
    return false;
  }
}

// Repli CSS : carte holo en dégradé + sheen animé (réutilise les keyframes pa-holo).
function HoloCardCss({ accent = "#5B3FA8", title, sub, price, verdict, height = 340 }) {
  return (
    <div style={{ height, display: "flex", alignItems: "center", justifyContent: "center" }}>
      <div style={{ position: "relative", width: 200, height: 280, borderRadius: 16, overflow: "hidden",
        background: `linear-gradient(155deg, #140C28, ${accent} 56%, #E6DBFF)`,
        boxShadow: "0 30px 70px rgba(0,0,0,.55), 0 0 0 1px rgba(255,255,255,.2)",
        animation: "pa-floaty 4s ease-in-out infinite" }}>
        <div style={{ position: "absolute", inset: 7, borderRadius: 11, border: "1px solid rgba(255,255,255,.28)" }} />
        <div style={{ position: "absolute", left: 12, right: 12, top: 12, fontSize: 15, fontWeight: 800, color: "#fff", textShadow: "0 1px 4px rgba(0,0,0,.5)" }}>{title}</div>
        <div style={{ position: "absolute", left: 12, right: 12, top: 38, height: 132, borderRadius: 8, border: "1px solid rgba(255,255,255,.26)", background: "rgba(0,0,0,.18)" }} />
        {verdict && <div className="font-mono" style={{ position: "absolute", left: 12, bottom: 44, fontSize: 11, color: "#FFE9A8", fontWeight: 700 }}>★ {verdict}</div>}
        <div className="font-mono" style={{ position: "absolute", left: 12, right: 12, bottom: 12, display: "flex", justifyContent: "space-between", color: "#fff", fontWeight: 700 }}>
          <span>{price}</span><span style={{ fontSize: 10, opacity: 0.8 }}>{sub}</span>
        </div>
        <div style={{ position: "absolute", inset: 0, pointerEvents: "none", mixBlendMode: "screen", opacity: 0.7,
          background: "linear-gradient(110deg, transparent 35%, rgba(255,255,255,.4) 50%, transparent 65%)",
          backgroundSize: "210% 100%", animation: "pa-holo 3.6s linear infinite" }} />
      </div>
    </div>
  );
}

export default function HoloCard(props) {
  const ok = useMemo(webglOK, []);
  if (!ok) return <HoloCardCss {...props} />;
  return (
    <Suspense fallback={<HoloCardCss {...props} />}>
      <HoloCard3D {...props} />
    </Suspense>
  );
}
