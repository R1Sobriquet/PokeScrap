import { useEffect } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useI18n } from "../i18n.jsx";

// Tiroir de détail latéral (pattern Linear/Stripe) : clic sur une ligne →
// panneau à droite sans quitter la liste. Échap / clic hors panneau ferme.
export default function DetailDrawer({ open, onClose, title, children, width = 400 }) {
  const { t } = useI18n();

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          style={{ position: "fixed", inset: 0, zIndex: 420, background: "rgba(6,4,16,.5)", backdropFilter: "blur(3px)" }}
          onClick={onClose}
        >
          <motion.aside
            role="dialog"
            aria-modal="true"
            aria-label={title}
            initial={{ x: width }} animate={{ x: 0 }} exit={{ x: width }}
            transition={{ type: "spring", stiffness: 380, damping: 34 }}
            onClick={(e) => e.stopPropagation()}
            style={{ position: "absolute", top: 0, right: 0, bottom: 0, width: `min(${width}px, 94vw)`,
                     overflowY: "auto", background: "var(--panel-solid)",
                     borderLeft: "1px solid var(--border2)", boxShadow: "-24px 0 60px var(--shadow)" }}
          >
            <div className="sticky top-0 flex items-center justify-between gap-3 border-b px-5 py-3.5"
                 style={{ borderColor: "var(--line)", background: "var(--panel-solid)" }}>
              <div className="truncate text-[15px] font-extrabold">{title}</div>
              <button onClick={onClose} aria-label={t("common.close")}
                      className="h-8 w-8 flex-none rounded-lg text-slate-400 hover:text-slate-200"
                      style={{ border: "1px solid var(--border2)" }}>✕</button>
            </div>
            <div className="p-5">{children}</div>
          </motion.aside>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
