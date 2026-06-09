// Client API. Le frontend ne parle qu'au backend ; il ne détient jamais de clé
// externe et ne calcule aucune décision — il lit et déclenche des actions.

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function login(username, password) {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) throw new Error("Identifiants invalides");
  return res.json();
}

export async function fetchMe(token) {
  const res = await fetch(`${API_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error("Non authentifié");
  return res.json();
}

// Wrapper générique avec token JWT.
export async function apiFetch(token, path, { method = "GET", body } = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
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
