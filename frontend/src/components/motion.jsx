import { useEffect, useRef, useState } from "react";
import { animate, motion } from "framer-motion";

// Compteur animé : la valeur numérique « roule » jusqu'à la cible.
export function CountUp({ value, format = (v) => v.toFixed(0), duration = 1.1, className, style }) {
  // Initialise sur la cible : le rendu synchrone (et les tests jsdom, où rAF
  // n'avance pas) montre déjà la valeur finale ; l'anim joue ensuite au navigateur.
  const [display, setDisplay] = useState(Number(value) || 0);
  const prev = useRef(0);
  useEffect(() => {
    const target = Number(value) || 0;
    const controls = animate(prev.current, target, {
      duration, ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setDisplay(v),
    });
    prev.current = target;
    return () => controls.stop();
  }, [value, duration]);
  return <span className={className} style={style}>{format(display)}</span>;
}

const CONFETTI = ["#FFD75A", "#9B7BFF", "#34D399", "#3D7BFF", "#F4585F", "#2FB6C9"];

// Salve de confettis (déclenchée sur un STRONG BUY, etc.).
export function Confetti({ fire, count = 26 }) {
  const pieces = useRef(
    Array.from({ length: count }, (_, i) => ({
      id: i, x: (Math.random() - 0.5) * 360, y: 140 + Math.random() * 220,
      rot: Math.random() * 720 - 360, color: CONFETTI[i % CONFETTI.length],
      delay: Math.random() * 0.12, size: 6 + Math.random() * 6,
    }))
  );
  if (!fire) return null;
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none", zIndex: 5 }}>
      {pieces.current.map((p) => (
        <motion.span key={p.id}
          initial={{ opacity: 1, x: 0, y: 0, rotate: 0 }}
          animate={{ opacity: 0, x: p.x, y: p.y, rotate: p.rot }}
          transition={{ duration: 1.5 + Math.random(), ease: "easeIn", delay: p.delay }}
          style={{ position: "absolute", left: "50%", top: "28%", width: p.size, height: p.size * 1.4,
            background: p.color, borderRadius: 2 }} />
      ))}
    </div>
  );
}
