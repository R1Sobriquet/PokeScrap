import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { usePolling } from "../hooks/usePolling.js";

const SEV = {
  critical: { bar: "var(--red)", text: "var(--red-text)" },
  warning: { bar: "var(--yellow)", text: "var(--yellow-text)" },
  info: { bar: "var(--green)", text: "var(--green-text)" },
};
const routeFor = (type = "") =>
  /restock|stock/i.test(type) ? "/restock" : /flip|deal|arb/i.test(type) ? "/flip" : "/cockpit";

// Surveille les alertes en attente et fait apparaître les NOUVELLES en mini
// cartes holo (toasts). Le backlog initial n'est jamais « toasté ».
export default function AlertToaster() {
  const { data } = usePolling("/alerts?status=pending", { intervalSec: 30 });
  const navigate = useNavigate();
  const seen = useRef(null); // null = pas encore initialisé
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    if (!Array.isArray(data)) return;
    if (seen.current === null) {
      seen.current = new Set(data.map((a) => a.id)); // 1er passage : on mémorise sans notifier
      return;
    }
    const fresh = data.filter((a) => !seen.current.has(a.id));
    if (fresh.length === 0) return;
    fresh.forEach((a) => seen.current.add(a.id));
    setToasts((cur) => [...fresh.slice(0, 4).map((a) => ({ ...a, _k: `${a.id}` })), ...cur].slice(0, 4));
  }, [data]);

  const dismiss = (k) => setToasts((cur) => cur.filter((t) => t._k !== k));

  // Auto-dismiss : chaque toast disparaît après ~6,5 s.
  useEffect(() => {
    if (toasts.length === 0) return;
    const timers = toasts.map((t) => setTimeout(() => dismiss(t._k), 6500));
    return () => timers.forEach(clearTimeout);
  }, [toasts]);

  return (
    <div style={{ position: "fixed", right: 18, bottom: 18, zIndex: 400, display: "flex", flexDirection: "column", gap: 10, pointerEvents: "none" }}>
      <AnimatePresence>
        {toasts.map((a) => {
          const sev = SEV[a.severity] || SEV.info;
          return (
            <motion.div
              key={a._k}
              initial={{ opacity: 0, x: 80, scale: 0.9 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 80, scale: 0.9 }}
              transition={{ type: "spring", stiffness: 320, damping: 26 }}
              onClick={() => { navigate(routeFor(a.alert_type)); dismiss(a._k); }}
              style={{
                pointerEvents: "auto", cursor: "pointer", position: "relative", width: 312, overflow: "hidden",
                borderRadius: 14, padding: "12px 14px 12px 18px", background: "var(--panel-solid)",
                border: "1px solid var(--border2)", boxShadow: "0 20px 50px var(--shadow)",
              }}
            >
              <span style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: 4, background: sev.bar }} />
              <span style={{ position: "absolute", inset: 0, pointerEvents: "none", mixBlendMode: "screen", opacity: 0.5,
                background: "linear-gradient(110deg, transparent 35%, rgba(255,255,255,.22) 50%, transparent 65%)",
                backgroundSize: "210% 100%", animation: "pa-holo 3.4s linear infinite" }} />
              <div className="flex items-center justify-between">
                <span className="font-mono text-[9.5px] uppercase tracking-[0.14em]" style={{ color: sev.text }}>
                  {a.alert_type || "alert"}
                </span>
                <button onClick={(e) => { e.stopPropagation(); dismiss(a._k); }}
                        className="font-mono text-[12px] leading-none text-slate-500 hover:text-slate-300">✕</button>
              </div>
              <div className="mt-1 text-[13.5px] font-semibold leading-snug" style={{ color: "var(--text)" }}>{a.title}</div>
            </motion.div>
          );
        })}
      </AnimatePresence>
    </div>
  );
}
