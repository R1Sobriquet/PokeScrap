import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext.jsx";

// Redirige vers /login si aucun JWT n'est présent en mémoire.
export default function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
}
