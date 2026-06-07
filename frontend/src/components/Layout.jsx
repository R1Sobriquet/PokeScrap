import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";

const NAV = [
  { to: "/cockpit", label: "Cockpit" },
  { to: "/opportunites", label: "Opportunités" },
  { to: "/portefeuille", label: "Portefeuille" },
  { to: "/watchlist", label: "Watchlist" },
  { to: "/lots", label: "Lots & Liquidation" },
  { to: "/ledger", label: "Ledger & Fiscalité" },
  { to: "/grading", label: "Grading" },
  { to: "/reglages", label: "Réglages" },
];

export default function Layout() {
  const { username, signOut } = useAuth();
  const navigate = useNavigate();
  return (
    <div className="flex min-h-screen">
      <aside className="w-52 shrink-0 border-r border-slate-800 bg-slate-900 p-3">
        <div className="mb-4 px-2 text-sm font-bold text-slate-200">Pokémon Arbitrage</div>
        <nav className="flex flex-col gap-1">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                `rounded px-3 py-2 text-sm ${
                  isActive ? "bg-slate-700 text-white" : "text-slate-400 hover:bg-slate-800"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-6 border-t border-slate-800 px-2 pt-3 text-xs text-slate-500">
          <div className="mb-2">{username}</div>
          <button
            onClick={() => { signOut(); navigate("/login"); }}
            className="rounded bg-slate-800 px-3 py-1 text-slate-300 hover:bg-slate-700"
          >
            Déconnexion
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-x-hidden p-5">
        <Outlet />
      </main>
    </div>
  );
}
