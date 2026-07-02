import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../AuthContext.jsx";

// Poll un endpoint GET toutes `intervalSec` secondes. Renvoie
// { data, error, loading, reload } — API inchangée.
//
// v2 : cache PARTAGÉ par chemin (stale-while-revalidate). Plusieurs composants
// montés sur le même endpoint (ex. Ticker + Cockpit sur /movers, AlertsMenu +
// AlertToaster sur /alerts) partagent UNE requête et UN timer, calé sur le plus
// petit intervalle demandé. Un composant qui monte sur un chemin déjà en cache
// affiche la valeur immédiatement (zéro flash de chargement) puis revalide.

const store = new Map(); // path -> entrée partagée

function entryFor(path) {
  let e = store.get(path);
  if (!e) {
    e = { data: null, error: null, loading: true, subs: new Set(), timer: null,
          interval: Infinity, inflight: null, token: null };
    store.set(path, e);
  }
  return e;
}

function emit(e) {
  for (const cb of e.subs) cb();
}

function revalidate(path, token) {
  const e = entryFor(path);
  if (e.inflight) return e.inflight; // dédup : une seule requête en vol par chemin
  e.token = token;
  e.inflight = api
    .get(token, path)
    .then((data) => {
      e.data = data;
      e.error = null;
    })
    .catch((err) => {
      e.error = err.message;
    })
    .finally(() => {
      e.loading = false;
      e.inflight = null;
      emit(e);
    });
  return e.inflight;
}

function schedule(path) {
  const e = entryFor(path);
  clearInterval(e.timer);
  if (!Number.isFinite(e.interval) || e.subs.size === 0) return;
  e.timer = setInterval(() => revalidate(path, e.token), e.interval * 1000);
}

// À appeler au logout : les données appartiennent à la session.
export function invalidatePollingCache() {
  for (const e of store.values()) clearInterval(e.timer);
  store.clear();
}

export function usePolling(path, { intervalSec = 30, enabled = true } = {}) {
  const { token } = useAuth();
  const intervalRef = useRef(intervalSec);
  intervalRef.current = intervalSec;
  const [, force] = useState(0); // re-render local quand l'entrée partagée change

  const active = Boolean(token && enabled && path);

  useEffect(() => {
    if (!active) return undefined;
    const e = entryFor(path);
    if (e.token && e.token !== token) {
      // Nouveau token (re-login) : le cache appartenait à l'ancienne session.
      e.data = null;
      e.error = null;
      e.loading = true;
    }
    const cb = () => force((n) => n + 1);
    e.subs.add(cb);
    // Cadence effective du chemin = le plus court intervalle demandé.
    e.interval = Math.min(e.interval, intervalRef.current);
    revalidate(path, token); // frais → charge ; en cache → stale-while-revalidate
    schedule(path);
    return () => {
      e.subs.delete(cb);
      if (e.subs.size === 0) {
        clearInterval(e.timer);
        e.timer = null;
        e.interval = Infinity; // le prochain abonné redéfinira la cadence
      }
    };
  }, [path, token, active]);

  const reload = useCallback(
    () => (active ? revalidate(path, token) : Promise.resolve()),
    [path, token, active]
  );

  if (!active) return { data: null, error: null, loading: true, reload };
  const e = entryFor(path);
  return { data: e.data, error: e.error, loading: e.loading, reload };
}
