// Contexte d'authentification. Le JWT est gardé EN MÉMOIRE uniquement (state
// React) — jamais dans localStorage, conformément à la consigne de sécurité.

import { createContext, useContext, useState } from "react";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [token, setToken] = useState(null);
  const [username, setUsername] = useState(null);

  const value = {
    token,
    username,
    isAuthenticated: Boolean(token),
    signIn: (jwt, user) => {
      setToken(jwt);
      setUsername(user);
    },
    signOut: () => {
      setToken(null);
      setUsername(null);
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
