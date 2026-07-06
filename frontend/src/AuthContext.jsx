// Contexte d'authentification v2. L'access token (15 min) est gardé EN MÉMOIRE
// uniquement — jamais dans localStorage. La persistance de session vient du
// cookie refresh httpOnly : au montage, un « silent refresh » restaure l'access
// (un F5 ne déconnecte plus). `booting` couvre cette fenêtre de restauration.

import { createContext, useContext, useEffect, useState } from "react";
import { bindSession, fetchMe, logoutSession, refreshSession } from "./api.js";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [me, setMe] = useState(null); // { id, username, email, role, plan }
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    // api.js nous notifie d'un access tourné en cours de route (401→refresh)
    // ou d'une session définitivement perdue.
    bindSession({
      onTokenRefreshed: (fresh) => setToken(fresh),
      onSessionLost: () => {
        setToken(null);
        setMe(null);
      },
    });
    let alive = true;
    (async () => {
      const fresh = await refreshSession();
      if (alive && fresh) {
        setToken(fresh);
        try {
          setMe(await fetchMe(fresh));
        } catch {
          /* profil best-effort : l'access reste utilisable */
        }
      }
      if (alive) setBooting(false);
    })();
    return () => {
      alive = false;
      bindSession({});
    };
  }, []);

  const value = {
    token,
    username: me?.username ?? null,
    role: me?.role ?? "user",
    plan: me?.plan ?? null,
    booting,
    isAuthenticated: Boolean(token),
    signIn: (jwt, profile) => {
      setToken(jwt);
      // compat : certains appelants passent juste le username (string)
      setMe(typeof profile === "string" ? { username: profile, role: "user" } : profile);
    },
    signOut: () => {
      logoutSession(); // révoque le refresh côté serveur (best-effort)
      setToken(null);
      setMe(null);
    },
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth doit être utilisé dans <AuthProvider>");
  }
  return ctx;
}
