import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./AuthContext.jsx";
import ProtectedRoute from "./ProtectedRoute.jsx";
import Layout from "./components/Layout.jsx";
import Login from "./pages/Login.jsx";
import Cockpit from "./pages/Cockpit.jsx";
import Opportunities from "./pages/Opportunities.jsx";
import Portfolio from "./pages/Portfolio.jsx";
import Watchlist from "./pages/Watchlist.jsx";
import Sets from "./pages/Sets.jsx";
import Lots from "./pages/Lots.jsx";
import Ledger from "./pages/Ledger.jsx";
import Grading from "./pages/Grading.jsx";
import Settings from "./pages/Settings.jsx";

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route
            element={
              <ProtectedRoute>
                <Layout />
              </ProtectedRoute>
            }
          >
            <Route path="/cockpit" element={<Cockpit />} />
            <Route path="/opportunites" element={<Opportunities />} />
            <Route path="/portefeuille" element={<Portfolio />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/sets" element={<Sets />} />
            <Route path="/lots" element={<Lots />} />
            <Route path="/ledger" element={<Ledger />} />
            <Route path="/grading" element={<Grading />} />
            <Route path="/reglages" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/cockpit" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
