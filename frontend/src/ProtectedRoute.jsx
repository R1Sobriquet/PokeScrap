import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";

// Redirige vers /login si aucun JWT n'est présent en mémoire. Pendant le
// « silent refresh » du boot (cookie httpOnly → access), on n'affiche rien
// plutôt que de rediriger à tort un utilisateur dont la session va revenir.
export default function ProtectedRoute({ children }) {
  const { isAuthenticated, booting } = useAuth();
  if (booting) return null;
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
