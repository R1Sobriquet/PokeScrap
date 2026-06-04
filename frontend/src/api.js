// Client API minimal. Le frontend ne parle qu'au backend ; il ne détient
// jamais de clé externe (PokeTrace / PSA / Discord).

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function login(username, password) {
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    throw new Error("Identifiants invalides");
  }
  return res.json(); // { access_token, token_type }
}

export async function fetchMe(token) {
  const res = await fetch(`${API_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    throw new Error("Non authentifié");
  }
  return res.json();
}
