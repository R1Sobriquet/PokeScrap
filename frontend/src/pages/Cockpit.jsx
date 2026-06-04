import { useAuth } from "../AuthContext.jsx";

// Page protégée — vide au Jalon 1.
export default function Cockpit() {
  const { username, signOut } = useAuth();
  return (
    <div style={{ maxWidth: 720, margin: "60px auto", fontFamily: "sans-serif" }}>
      <header style={{ display: "flex", justifyContent: "space-between" }}>
        <h1>Cockpit</h1>
        <div>
          <span style={{ marginRight: 12 }}>{username}</span>
          <button onClick={signOut}>Déconnexion</button>
        </div>
      </header>
      <p style={{ marginTop: 48, fontSize: 24, color: "#888" }}>À venir</p>
    </div>
  );
}
