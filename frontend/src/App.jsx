import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./AuthContext.jsx";
import { ThemeProvider } from "./ThemeContext.jsx";
import { I18nProvider } from "./i18n.jsx";
import ProtectedRoute from "./ProtectedRoute.jsx";
import Layout from "./components/Layout.jsx";
import Landing from "./pages/Landing.jsx";
import Login from "./pages/Login.jsx";
import Cockpit from "./pages/Cockpit.jsx";
import Opportunities from "./pages/Opportunities.jsx";
import Portfolio from "./pages/Portfolio.jsx";
import Watchlist from "./pages/Watchlist.jsx";
import Sets from "./pages/Sets.jsx";
import Lots from "./pages/Lots.jsx";
import Ledger from "./pages/Ledger.jsx";
import Grading from "./pages/Grading.jsx";
import Jobs from "./pages/Jobs.jsx";
import Restock from "./pages/Restock.jsx";
import Retailers from "./pages/Retailers.jsx";
import Calendar from "./pages/Calendar.jsx";
import Settings from "./pages/Settings.jsx";

export default function App() {
  return (
    <ThemeProvider>
      <I18nProvider>
        <AuthProvider>
          <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
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
            <Route path="/restock" element={<Restock />} />
            <Route path="/detaillants" element={<Retailers />} />
            <Route path="/calendrier" element={<Calendar />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/reglages" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/cockpit" replace />} />
        </Routes>
          </BrowserRouter>
        </AuthProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}
