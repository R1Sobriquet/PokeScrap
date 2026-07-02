import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useI18n } from "../i18n.jsx";

// Palette de commandes ⌘K / Ctrl+K. `commands` : [{ id, label, hint, run }].
// S'ouvre aussi via l'évènement window "pa:palette" (bouton du header).
export default function CommandPalette({ commands }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [idx, setIdx] = useState(0);
  const inputRef = useRef(null);

  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    };
    const onEvt = () => setOpen(true);
    window.addEventListener("keydown", onKey);
    window.addEventListener("pa:palette", onEvt);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pa:palette", onEvt);
    };
  }, []);

  useEffect(() => {
    if (open) {
      setQ("");
      setIdx(0);
      const id = setTimeout(() => inputRef.current?.focus(), 10);
      return () => clearTimeout(id);
    }
  }, [open]);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return commands;
    return commands.filter((c) => `${c.label} ${c.hint || ""}`.toLowerCase().includes(s));
  }, [commands, q]);

  const run = (c) => {
    if (!c) return;
    setOpen(false);
    c.run();
  };
  const onInputKey = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setIdx((i) => Math.min(i + 1, filtered.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); run(filtered[Math.min(idx, filtered.length - 1)]); }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={() => setOpen(false)}
          style={{ position: "fixed", inset: 0, zIndex: 500, background: "rgba(6,4,16,.6)", backdropFilter: "blur(8px)",
            display: "flex", alignItems: "flex-start", justifyContent: "center", paddingTop: "12vh" }}
        >
          <motion.div
            initial={{ y: -18, scale: 0.97, opacity: 0 }} animate={{ y: 0, scale: 1, opacity: 1 }} exit={{ y: -10, opacity: 0 }}
            transition={{ type: "spring", stiffness: 360, damping: 28 }}
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label={t("palette.placeholder")}
            style={{ width: "min(620px, 92vw)", overflow: "hidden", borderRadius: 16,
              background: "var(--panel-solid)", border: "1px solid var(--border2)", boxShadow: "0 40px 100px var(--shadow)" }}
          >
            <input
              ref={inputRef} value={q}
              onChange={(e) => { setQ(e.target.value); setIdx(0); }}
              onKeyDown={onInputKey}
              placeholder={t("palette.placeholder")}
              className="w-full bg-transparent px-5 py-4 text-[15px] outline-none"
              style={{ color: "var(--text)", borderBottom: "1px solid var(--line)" }}
            />
            <div style={{ maxHeight: "46vh", overflowY: "auto" }}>
              {filtered.length === 0 ? (
                <div className="px-5 py-8 text-center text-sm text-slate-500">{t("palette.empty")}</div>
              ) : (
                filtered.map((c, i) => (
                  <button
                    key={c.id}
                    onMouseEnter={() => setIdx(i)}
                    onClick={() => run(c)}
                    className="flex w-full items-center justify-between gap-3 px-5 py-2.5 text-left"
                    style={{ background: i === idx ? "var(--tab-active-bg)" : "transparent" }}
                  >
                    <span className="text-[14px]" style={{ color: "var(--text)" }}>{c.label}</span>
                    <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-slate-500">{c.hint}</span>
                  </button>
                ))
              )}
            </div>
            <div className="flex items-center gap-3 border-t px-5 py-2 font-mono text-[10px] text-slate-500" style={{ borderColor: "var(--line)" }}>
              <span>↑↓ {t("palette.nav")}</span><span>↵ {t("palette.open")}</span><span>esc {t("palette.close")}</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
