import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";
import { useTheme, THEMES } from "../ThemeContext.jsx";
import { useI18n, LANGS } from "../i18n.jsx";

// Navigation regroupée par domaine ; les libellés passent par i18n (FR/EN).
const NAV_GROUPS = [
  {
    section: "nav.section.market",
    items: [
      { to: "/cockpit", key: "nav.cockpit" },
      { to: "/opportunites", key: "nav.opportunites" },
      { to: "/sets", key: "nav.sets" },
      { to: "/watchlist", key: "nav.watchlist" },
      { to: "/restock", key: "nav.restock" },
      { to: "/detaillants", key: "nav.detaillants" },
      { to: "/calendrier", key: "nav.calendrier" },
    ],
  },
  {
    section: "nav.section.portfolio",
    items: [
      { to: "/portefeuille", key: "nav.portefeuille" },
      { to: "/lots", key: "nav.lots" },
      { to: "/ledger", key: "nav.ledger" },
      { to: "/grading", key: "nav.grading" },
    ],
  },
  {
    section: "nav.section.ops",
    items: [
      { to: "/jobs", key: "nav.jobs" },
      { to: "/reglages", key: "nav.reglages" },
    ],
  },
];

// Pastille représentative de chaque thème dans le sélecteur.
const THEME_SWATCH = {
  dark: "#0A0D14",
  light: "#F4F6FA",
  holo: "conic-gradient(from 210deg, #5B8CFF, #B89CFF, #FFCB2E, #34E2A4, #5B8CFF)",
  ember: "linear-gradient(150deg, #FF8A3D, #FF5E54)",
};

function Logo() {
  return (
    <div className="flex items-center gap-2">
      <div
        style={{
          width: 22,
          height: 22,
          borderRadius: "50%",
          background:
            "conic-gradient(from 210deg, #3D7BFF, #9B7BFF, #FFCB2E, #34D399, #3D7BFF)",
          boxShadow: "inset 0 0 0 4px var(--bg)",
        }}
      />
      <div className="text-[16.5px] font-extrabold tracking-tight">
        Poké<span style={{ color: "var(--logo-accent)" }}>Alpha</span>
      </div>
    </div>
  );
}

function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const { t } = useI18n();
  return (
    <div
      className="flex items-center gap-1.5 rounded-full border p-1"
      style={{ borderColor: "var(--border2)", background: "var(--panel2)" }}
      title={t("chrome.theme")}
    >
      {THEMES.map((th) => (
        <button
          key={th}
          onClick={() => setTheme(th)}
          title={t(`theme.${th}`)}
          aria-label={t(`theme.${th}`)}
          style={{
            width: 18,
            height: 18,
            borderRadius: "50%",
            background: THEME_SWATCH[th],
            cursor: "pointer",
            border: "1px solid var(--border-hover)",
            outline: theme === th ? "2px solid var(--blue)" : "none",
            outlineOffset: 1,
          }}
        />
      ))}
    </div>
  );
}

function LangSwitcher() {
  const { lang, setLang } = useI18n();
  return (
    <div
      className="flex items-center gap-0.5 rounded-full border p-0.5"
      style={{ borderColor: "var(--border2)", background: "var(--panel2)" }}
    >
      {LANGS.map((l) => (
        <button
          key={l}
          onClick={() => setLang(l)}
          className="rounded-full px-2.5 py-1 font-mono text-[11px] font-semibold uppercase transition-colors"
          style={
            lang === l
              ? { background: "var(--tab-active-bg)", color: "var(--text)" }
              : { background: "transparent", color: "var(--muted)" }
          }
        >
          {l}
        </button>
      ))}
    </div>
  );
}

export default function Layout() {
  const { username, signOut } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const initials = (username || "PA").slice(0, 2).toUpperCase();

  return (
    <div className="flex min-h-screen flex-col">
      {/* Header chrome PokéAlpha */}
      <header
        className="sticky top-0 z-50 flex h-[58px] items-center gap-3 px-5 backdrop-blur-xl"
        style={{
          background: "var(--header-bg)",
          borderBottom: "1px solid var(--line)",
        }}
      >
        <Logo />
        <div className="flex-1" />
        <ThemeSwitcher />
        <LangSwitcher />
        <div
          className="hidden items-center gap-2.5 rounded-xl px-2.5 py-1.5 sm:flex"
          style={{ border: "1px solid var(--border2)", background: "var(--panel2)" }}
        >
          <div
            className="flex h-7 w-7 items-center justify-center rounded-full text-[11px] font-bold text-white"
            style={{ background: "linear-gradient(150deg, #3D7BFF, #9B7BFF)" }}
          >
            {initials}
          </div>
          <div className="text-[13px] font-semibold leading-none">{username || "—"}</div>
        </div>
        <button
          onClick={() => {
            signOut();
            navigate("/login");
          }}
          className="rounded-xl px-3 py-2 text-[13px] font-semibold transition-colors"
          style={{ border: "1px solid var(--border2)", background: "var(--panel2)", color: "var(--text2)" }}
        >
          {t("chrome.signOut")}
        </button>
      </header>

      <div className="flex flex-1">
        {/* Sidebar réskinée */}
        <aside
          className="w-56 shrink-0 p-3"
          style={{ borderRight: "1px solid var(--line)", background: "var(--panel)" }}
        >
          <nav className="flex flex-col gap-4">
            {NAV_GROUPS.map((group) => (
              <div key={group.section} className="flex flex-col gap-1">
                <div className="px-3 pb-1 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-500">
                  {t(group.section)}
                </div>
                {group.items.map((n) => (
                  <NavLink
                    key={n.to}
                    to={n.to}
                    className={({ isActive }) =>
                      `rounded-lg px-3 py-2 text-sm transition-colors ${
                        isActive
                          ? "font-semibold text-slate-100"
                          : "text-slate-400 hover:bg-slate-800/50"
                      }`
                    }
                    style={({ isActive }) =>
                      isActive
                        ? { background: "var(--tab-active-bg)", border: "1px solid var(--tab-active-border)" }
                        : { border: "1px solid transparent" }
                    }
                  >
                    {t(n.key)}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>
        </aside>

        <main className="flex-1 overflow-x-hidden p-5 pa-pagein">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
