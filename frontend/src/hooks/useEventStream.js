import { useEffect } from "react";
import { useAuth } from "../AuthContext.jsx";
import { revalidatePath } from "./usePolling.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Flux SSE backend (/events/stream) : quand le serveur signale un changement
// (nouvelle alerte, restock…), on revalide immédiatement les chemins concernés
// dans le cache partagé — les toasts/ticker deviennent temps réel. Le polling
// existant reste en place comme filet de sécurité : si le flux tombe, rien ne
// casse, on retente avec backoff exponentiel (cap 30 s).
//
// Le JWT passe en query string (EventSource ne pose pas d'en-têtes) — app
// mono-utilisateur locale/Tailscale, jamais exposée publiquement.
export function useEventStream() {
  const { token } = useAuth();

  useEffect(() => {
    if (!token || typeof EventSource === "undefined") return undefined;
    let es = null;
    let timer = null;
    let retry = 1000;
    let closed = false;

    const onPush = (e) => {
      try {
        const d = JSON.parse(e.data);
        (d.paths || []).forEach(revalidatePath);
      } catch {
        /* payload inattendu : le polling couvrira */
      }
    };

    const open = () => {
      if (closed) return;
      es = new EventSource(`${API_URL}/events/stream?token=${encodeURIComponent(token)}`);
      es.addEventListener("alerts", onPush);
      es.addEventListener("offers", onPush);
      es.onopen = () => {
        retry = 1000; // connexion OK → réarme le backoff
      };
      es.onerror = () => {
        es.close();
        if (!closed) {
          timer = setTimeout(open, retry);
          retry = Math.min(retry * 2, 30000);
        }
      };
    };

    open();
    return () => {
      closed = true;
      clearTimeout(timer);
      es?.close();
    };
  }, [token]);
}
