import { useEffect } from "react";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { revalidatePath } from "./usePolling.js";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Flux SSE backend (/events/stream) : quand le serveur signale un changement
// (nouvelle alerte, restock…), on revalide immédiatement les chemins concernés
// dans le cache partagé — les toasts/ticker deviennent temps réel. Le polling
// existant reste en place comme filet de sécurité : si le flux tombe, rien ne
// casse, on retente avec backoff exponentiel (cap 30 s).
//
// EventSource ne pose pas d'en-têtes : on échange le Bearer contre un TICKET
// court (60 s, portée sse) juste avant chaque (re)connexion — l'access token
// complet n'apparaît jamais dans une URL.
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

    const scheduleRetry = () => {
      if (closed) return;
      timer = setTimeout(open, retry);
      retry = Math.min(retry * 2, 30000);
    };

    const open = async () => {
      if (closed) return;
      let ticket = null;
      try {
        ticket = (await api.get(token, "/events/ticket"))?.ticket;
      } catch {
        /* backend indisponible : on retentera */
      }
      if (!ticket) {
        scheduleRetry();
        return;
      }
      if (closed) return;
      es = new EventSource(`${API_URL}/events/stream?token=${encodeURIComponent(ticket)}`);
      es.addEventListener("alerts", onPush);
      es.addEventListener("offers", onPush);
      es.onopen = () => {
        retry = 1000; // connexion OK → réarme le backoff
      };
      es.onerror = () => {
        es.close();
        scheduleRetry();
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
