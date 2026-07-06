import { lazy } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { MotionConfig } from "framer-motion";
import { AuthProvider } from "./AuthContext.jsx";
import { ThemeProvider } from "./ThemeContext.jsx";
import { I18nProvider } from "./i18n.jsx";
import ProtectedRoute from "./ProtectedRoute.jsx";
import Layout from "./components/Layout.jsx";
// Landing et Login restent EAGER : premier écran instantané (et rendus
// synchrones attendus par les tests). Toutes les pages protégées sont lazy →
// code-splitting par route (le shell charge sans recharts ni pages).
import Landing from "./pages/Landing.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import Verify from "./pages/Verify.jsx";
import Forgot from "./pages/Forgot.jsx";
import ResetPassword from "./pages/ResetPassword.jsx";

const Cockpit = lazy(() => import("./pages/Cockpit.jsx"));
const Opportunities = lazy(() => import("./pages/Opportunities.jsx"));
const Portfolio = lazy(() => import("./pages/Portfolio.jsx"));
const Watchlist = lazy(() => import("./pages/Watchlist.jsx"));
const Sets = lazy(() => import("./pages/Sets.jsx"));
const Lots = lazy(() => import("./pages/Lots.jsx"));
const Ledger = lazy(() => import("./pages/Ledger.jsx"));
const Grading = lazy(() => import("./pages/Grading.jsx"));
const Jobs = lazy(() => import("./pages/Jobs.jsx"));
const Restock = lazy(() => import("./pages/Restock.jsx"));
const FlipRadar = lazy(() => import("./pages/FlipRadar.jsx"));
const Retailers = lazy(() => import("./pages/Retailers.jsx"));
const Stores = lazy(() => import("./pages/Stores.jsx"));
const BuyRules = lazy(() => import("./pages/BuyRules.jsx"));
const Calendar = lazy(() => import("./pages/Calendar.jsx"));
const FutureRadar = lazy(() => import("./pages/FutureRadar.jsx"));
const DealAnalyzer = lazy(() => import("./pages/DealAnalyzer.jsx"));
const SetExplorer = lazy(() => import("./pages/SetExplorer.jsx"));
const SetDetail = lazy(() => import("./pages/SetDetail.jsx"));
const Settings = lazy(() => import("./pages/Settings.jsx"));

export default function App() {
  return (
    <ThemeProvider>
      <I18nProvider>
        <AuthProvider>
          <MotionConfig reducedMotion="user">
          <BrowserRouter>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/verify" element={<Verify />} />
          <Route path="/forgot" element={<Forgot />} />
          <Route path="/reset" element={<ResetPassword />} />
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
            <Route path="/explorer" element={<SetExplorer />} />
            <Route path="/set/:slug" element={<SetDetail />} />
            <Route path="/lots" element={<Lots />} />
            <Route path="/ledger" element={<Ledger />} />
            <Route path="/grading" element={<Grading />} />
            <Route path="/restock" element={<Restock />} />
            <Route path="/flip" element={<FlipRadar />} />
            <Route path="/detaillants" element={<Retailers />} />
            <Route path="/magasins" element={<Stores />} />
            <Route path="/achat-assiste" element={<BuyRules />} />
            <Route path="/calendrier" element={<Calendar />} />
            <Route path="/future" element={<FutureRadar />} />
            <Route path="/analyzer" element={<DealAnalyzer />} />
            <Route path="/jobs" element={<Jobs />} />
            <Route path="/reglages" element={<Settings />} />
          </Route>
          <Route path="*" element={<Navigate to="/cockpit" replace />} />
        </Routes>
          </BrowserRouter>
          </MotionConfig>
        </AuthProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}
