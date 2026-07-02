// Visite guidée (driver.js) — onboarding interactif des nouveaux utilisateurs.
//
// - Les étapes ciblent des ancres `[data-tour="…"]` posées dans Layout/Cockpit ;
//   toute ancre absente du DOM est filtrée (le tour marche depuis n'importe où).
// - Persistance : localStorage `pa-tour-v1` ("done" | "skipped") — jamais rejoué
//   automatiquement ; relançable via le bouton ? du header ou ⌘K.
// - Skip : bouton ✕ et touche Échap (natifs driver.js) → marqué "skipped".
import { driver } from "driver.js";
import "driver.js/dist/driver.css";

const STORAGE_KEY = "pa-tour-v1";

export function tourDone() {
  try {
    return Boolean(localStorage.getItem(STORAGE_KEY));
  } catch {
    return true; // stockage indisponible → ne jamais harceler l'utilisateur
  }
}

export function markTourDone(how = "done") {
  try {
    localStorage.setItem(STORAGE_KEY, how);
  } catch {
    /* stockage indisponible : tant pis, le tour pourra se re-proposer */
  }
}

// Ordre du récit : d'abord "où est l'argent" (KPIs, deal), puis la navigation,
// puis les outils du chrome (alertes, ⌘K, pack, thèmes).
const STEP_DEFS = [
  { sel: '[data-tour="kpis"]', key: "kpis", side: "bottom" },
  { sel: '[data-tour="deal"]', key: "deal", side: "top" },
  { sel: '[data-tour="sidebar"]', key: "sidebar", side: "right" },
  { sel: '[data-tour="ticker"]', key: "ticker", side: "bottom" },
  { sel: '[data-tour="alerts"]', key: "alerts", side: "bottom" },
  { sel: '[data-tour="palette"]', key: "palette", side: "bottom" },
  { sel: '[data-tour="pack"]', key: "pack", side: "bottom" },
  { sel: '[data-tour="theme"]', key: "theme", side: "bottom" },
];

let active = null; // une seule instance à la fois

export function startTour(t, { onDone } = {}) {
  if (active) return active;
  const steps = STEP_DEFS.filter((s) => document.querySelector(s.sel)).map((s) => ({
    element: s.sel,
    popover: {
      title: t(`tour.${s.key}.title`),
      description: t(`tour.${s.key}.desc`),
      side: s.side,
      align: "start",
    },
  }));
  if (steps.length === 0) return null;

  const reduceMotion = typeof window !== "undefined"
    && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  const d = driver({
    steps,
    showProgress: true,
    progressText: "{{current}} / {{total}}",
    animate: !reduceMotion,
    overlayOpacity: 0.72,
    stagePadding: 6,
    stageRadius: 12,
    popoverClass: "pa-tour",
    nextBtnText: t("tour.next"),
    prevBtnText: t("tour.prev"),
    doneBtnText: t("tour.finish"),
    onDestroyed: (_el, _step, { state } = {}) => {
      const finished = state?.activeIndex === steps.length - 1;
      markTourDone(finished ? "done" : "skipped");
      active = null;
      onDone?.();
    },
  });
  active = d;
  d.drive();
  return d;
}
