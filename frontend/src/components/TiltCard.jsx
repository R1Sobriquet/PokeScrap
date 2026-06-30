import { useRef, useState } from "react";

const reduceMotion = () => {
  try {
    return typeof window !== "undefined" && window.matchMedia
      && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
};

// Tilt 3D léger + reflet holo qui suit le curseur. Pur CSS/DOM (sûr en jsdom).
export default function TiltCard({
  children, max = 12, scale = 1.04, glare = true, className, style, radius = 16,
}) {
  const ref = useRef(null);
  const raf = useRef(0);
  const [t, setT] = useState({ rx: 0, ry: 0, gx: 50, gy: 50, on: false });
  const calm = reduceMotion();

  const move = (e) => {
    if (calm || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const px = (e.clientX - r.left) / r.width - 0.5;
    const py = (e.clientY - r.top) / r.height - 0.5;
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(() =>
      setT({ rx: -py * max * 2, ry: px * max * 2, gx: (px + 0.5) * 100, gy: (py + 0.5) * 100, on: true })
    );
  };
  const leave = () => {
    cancelAnimationFrame(raf.current);
    setT({ rx: 0, ry: 0, gx: 50, gy: 50, on: false });
  };

  return (
    <div className={className} style={{ ...style, perspective: 700 }} onMouseMove={move} onMouseLeave={leave}>
      <div
        style={{
          position: "relative", height: "100%", borderRadius: radius,
          transform: `rotateX(${t.rx}deg) rotateY(${t.ry}deg) scale(${t.on ? scale : 1})`,
          transition: t.on ? "transform .08s ease-out" : "transform .5s cubic-bezier(.22,1,.36,1)",
          transformStyle: "preserve-3d", willChange: "transform",
          boxShadow: t.on ? "0 26px 50px rgba(0,0,0,.45)" : "none",
        }}
      >
        {children}
        {glare && (
          <div
            style={{
              position: "absolute", inset: 0, borderRadius: radius, pointerEvents: "none",
              mixBlendMode: "screen", opacity: t.on ? 0.5 : 0, transition: "opacity .3s",
              background: `radial-gradient(120px 120px at ${t.gx}% ${t.gy}%, rgba(255,255,255,.85), rgba(155,123,255,.35) 35%, transparent 70%)`,
            }}
          />
        )}
      </div>
    </div>
  );
}
