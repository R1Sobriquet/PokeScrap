import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";

// Poll un endpoint GET toutes `intervalSec` secondes (par défaut 30, aligné sur
// dashboard_poll_interval_sec). Renvoie { data, error, loading, reload }.
export function usePolling(path, { intervalSec = 30, enabled = true } = {}) {
  const { token } = useAuth();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const timer = useRef(null);

  const load = useCallback(async () => {
    if (!token || !enabled || !path) return;
    try {
      setData(await api.get(token, path));
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [token, path, enabled]);

  useEffect(() => {
    load();
    if (!enabled) return undefined;
    timer.current = setInterval(load, intervalSec * 1000);
    return () => clearInterval(timer.current);
  }, [load, intervalSec, enabled]);

  return { data, error, loading, reload: load };
}
