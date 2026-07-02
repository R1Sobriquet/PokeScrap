import { useEffect } from "react";
import { startTour, tourDone } from "./tour.js";

// Déclenche le tour UNE fois, à la première visite du Cockpit avec données
// chargées (les ancres existent alors). Jamais sur mobile étroit (le layout y
// diffère) ni si l'utilisateur l'a déjà terminé/passé.
export function useAutoTour(t, ready) {
  useEffect(() => {
    if (!ready || tourDone()) return undefined;
    if (typeof window !== "undefined" && window.innerWidth < 768) return undefined;
    const id = setTimeout(() => startTour(t), 700); // laisse la page se poser
    return () => clearTimeout(id);
  }, [ready, t]);
}
