// Client API. Le frontend ne parle qu'au backend ; il ne détient jamais de clé
// externe et ne calcule aucune décision — il lit et déclenche des actions.
//
// Auth v2 : l'access token (15 min) vit EN MÉMOIRE ; le refresh vit dans un
// cookie httpOnly posé par le backend (path=/auth) → `credentials: "include"`
// sur les routes /auth. Sur un 401 API, on tente UNE rotation silencieuse puis
// on rejoue la requête ; sinon la session est perdue (AuthContext notifié).

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function postJson(path, body) {
  const res = await fetch(`${API_URL}${path}`, {
    method: "POST",
    credentials: "include", // cookie refresh httpOnly
    headers: body ? { "Content-Type": "application/json" } : {},
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  return res;
}

async function detailOf(res, fallback) {
  try {
    return (await res.json()).detail || fallback;
  } catch {
    return fallback;
  }
}

export async function login(username, password) {
  const res = await postJson("/auth/login", { username, password });
  if (!res.ok) throw new Error(await detailOf(res, "Identifiants invalides"));
  return res.json();
}

export async function registerAccount({ email, username, password }) {
  const res = await postJson("/auth/register", { email, username, password });
  if (!res.ok) throw new Error(await detailOf(res, "Inscription impossible"));
  return res.json();
}

export async function verifyEmail(token) {
  const res = await postJson("/auth/verify", { token });
  if (!res.ok) throw new Error(await detailOf(res, "Jeton invalide ou expiré"));
  return res.json();
}

export async function forgotPassword(email) {
  const res = await postJson("/auth/forgot", { email });
  if (!res.ok) throw new Error(await detailOf(res, "Demande impossible"));
  return res.json();
}

export async function resetPassword(token, password) {
  const res = await postJson("/auth/reset", { token, password });
  if (!res.ok) throw new Error(await detailOf(res, "Jeton invalide ou expiré"));
  return res.json();
}

// Rotation silencieuse : nouvel access si le cookie refresh est valide, sinon null.
export async function refreshSession() {
  try {
    const res = await postJson("/auth/refresh");
    if (!res.ok) return null;
    return (await res.json()).access_token || null;
  } catch {
    return null;
  }
}

export async function logoutSession() {
  try {
    await postJson("/auth/logout");
  } catch {
    /* réseau KO : le cookie expirera tout seul */
  }
}

export async function fetchMe(token) {
  const res = await fetch(`${API_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Non authentifié");
  return res.json();
}

// Liaison avec AuthContext (le module ne connaît pas React) : informé d'un
// access rafraîchi en cours de route, ou d'une session définitivement perdue.
let _onTokenRefreshed = null;
let _onSessionLost = null;
export function bindSession({ onTokenRefreshed, onSessionLost } = {}) {
  _onTokenRefreshed = onTokenRefreshed || null;
  _onSessionLost = onSessionLost || null;
}

// Wrapper générique avec token JWT (+ retry unique après rotation sur 401).
export async function apiFetch(token, path, { method = "GET", body } = {}, _retried = false) {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (res.status === 401 && !_retried) {
    const fresh = await refreshSession();
    if (fresh) {
      _onTokenRefreshed?.(fresh);
      return apiFetch(fresh, path, { method, body }, true);
    }
    _onSessionLost?.();
  }
  if (!res.ok) throw new Error(`API ${res.status} sur ${path}`);
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

export const api = {
  get: (token, path) => apiFetch(token, path),
  put: (token, path, body) => apiFetch(token, path, { method: "PUT", body }),
  post: (token, path, body) => apiFetch(token, path, { method: "POST", body }),
  del: (token, path) => apiFetch(token, path, { method: "DELETE" }),
};

export const exportUrl = (path) => `${API_URL}${path}`;
