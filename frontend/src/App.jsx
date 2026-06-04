import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./AuthContext.jsx";
import ProtectedRoute from "./ProtectedRoute.jsx";
import Login from "./pages/Login.jsx";
import Cockpit from "./pages/Cockpit.jsx";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            path="/cockpit"
            element={
              <ProtectedRoute>
                <Cockpit />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<Navigate to="/cockpit" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
