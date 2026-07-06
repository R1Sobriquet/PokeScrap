import { Suspense, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";
import { useTheme, THEMES } from "../ThemeContext.jsx";
import { useI18n, LANGS } from "../i18n.jsx";
import { usePolling, invalidatePollingCache } from "../hooks/usePolling.js";
import { useEventStream } from "../hooks/useEventStream.js";
import PackExperience from "./PackExperience.jsx";
import Ticker from "./Ticker.jsx";
import AlertToaster from "./AlertToaster.jsx";
import CommandPalette from "./CommandPalette.jsx";
import PwaControls from "./PwaControls.jsx";
import { startTour } from "../onboarding/tour.js";
import ErrorBoundary from "./ErrorBoundary.jsx";
import { PageSkeleton } from "./Skeleton.jsx";

const SEV_DOT = { critical: "var(--red)", warning: "var(--yellow)", info: "var(--green)" };

function AlertsMenu() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const { data } = usePolling("/alerts?status=pending", { intervalSec: 30 });
  const alerts = data || [];
  return (
    <div className="relative flex-none">
      <button
        data-tour="alerts"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-xl px-2.5 py-2"
        style={{ border: "1px solid rgba(244,88,95,.3)", background: "rgba(244,88,95,.08)" }}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--red)", animation: "pa-pulse 2s infinite" }} />
        <span className="font-mono text-[11px]" style={{ color: "var(--red-text)" }}>
          {alerts.length} {t("chrome.alerts")}
        </span>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-50 mt-2.5 w-[340px] overflow-hidden rounded-2xl"
               style={{ background: "var(--panel-solid)", border: "1px solid var(--border2)", boxShadow: "0 24px 60px var(--shadow)" }}>
            <div className="border-b px-4 py-3 font-mono text-[10px] tracking-[0.14em] text-slate-500" style={{ borderColor: "var(--line)" }}>
              {t("chrome.notifications")}
            </div>
            {alerts.length === 0 ? (
              <div className="px-4 py-6 text-center text-sm text-slate-500">{t("chrome.alerts.none")}</div>
            ) : (
              alerts.slice(0, 8).map((a) => (
                <div key={a.id} className="flex items-start gap-3 border-b px-4 py-3" style={{ borderColor: "var(--line)" }}>
                  <span className="mt-1.5 flex-none" style={{ width: 8, height: 8, borderRadius: "50%", background: SEV_DOT[a.severity] || "var(--green)" }} />
                  <div className="min-w-0 flex-1">
                    <div className="flex justify-between gap-2">
                      <span className="font-mono text-[9.5px] tracking-[0.12em] text-slate-500">{a.alert_type}</span>
                      <span className="font-mono text-[9.5px] text-slate-600">{(a.created_at || "").replace("T", " ").slice(5, 16)}</span>
                    </div>
                    <div className="mt-1 text-[13px] leading-snug text-slate-300">{a.title}</div>
                  </div>
                </div>
              ))
            )}
          </div>
        </>
      )}
    </div>
  );
}

function PlanMenu({ username, onSignOut }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const { data } = usePolling("/settings", { intervalSec: 300 });
  const plan = (data || []).find((s) => s.key === "poketrace_plan")?.value || "free";
  const initials = (username || "PA").slice(0, 2).toUpperCase();
  return (
    <div className="relative flex-none">
      <button onClick={() => setOpen((v) => !v)} className="flex items-center gap-2.5 rounded-xl px-2 py-1.5"
              style={{ border: "1px solid transparent" }}>
        <div className="flex h-8 w-8 items-center justify-center rounded-full text-[12px] font-bold text-white"
             style={{ background: "linear-gradient(150deg, #3D7BFF, #9B7BFF)", boxShadow: "0 0 0 2px var(--bg), 0 0 0 4px var(--logo-accent)" }}>
          {initials}
        </div>
        <div className="hidden text-left lg:block">
          <div className="text-[13px] font-semibold leading-tight">{username || "—"}</div>
          <div className="font-mono text-[10px] tracking-[0.08em]" style={{ color: plan === "pro" ? "var(--violet-text)" : "var(--muted)" }}>
            {plan.toUpperCase()} {t("chrome.plan")} ▾
          </div>
        </div>
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-50 mt-2.5 w-56 overflow-hidden rounded-2xl"
               style={{ background: "var(--panel-solid)", border: "1px solid var(--border2)", boxShadow: "0 24px 60px var(--shadow)" }}>
            <button onClick={() => { setOpen(false); navigate("/reglages"); }}
                    className="block w-full border-b px-4 py-3 text-left text-sm hover:bg-slate-800/40"
                    style={{ borderColor: "var(--line)", color: "var(--blue-soft)" }}>
              {t("chrome.viewSettings")}
            </button>
            <button onClick={onSignOut} className="block w-full px-4 py-3 text-left text-sm text-slate-300 hover:bg-slate-800/40">
              {t("chrome.signOut")}
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// Navigation regroupée par domaine ; les libellés passent par i18n (FR/EN).
// Le bloc « Marché » historique (13 liens à plat) est scindé : analyse marché
// d'un côté, veille détaillants PokéStock FR de l'autre — scan visuel 2× plus court.
const NAV_GROUPS = [
  {
    section: "nav.section.market",
    items: [
      { to: "/cockpit", key: "nav.cockpit" },
      { to: "/opportunites", key: "nav.opportunites" },
      { to: "/sets", key: "nav.sets" },
      { to: "/explorer", key: "nav.explorer" },
      { to: "/future", key: "nav.future" },
      { to: "/analyzer", key: "nav.analyzer" },
      { to: "/watchlist", key: "nav.watchlist" },
    ],
  },
  {
    section: "nav.section.pokestock",
    items: [
      { to: "/restock", key: "nav.restock" },
      { to: "/flip", key: "nav.flip" },
      { to: "/detaillants", key: "nav.detaillants", adminOnly: true },
      { to: "/magasins", key: "nav.magasins" },
      { to: "/achat-assiste", key: "nav.buyrules" },
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
      { to: "/jobs", key: "nav.jobs", adminOnly: true },
      { to: "/reglages", key: "nav.reglages", adminOnly: true },
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

// Corps de navigation partagé entre la sidebar desktop et le tiroir mobile.
function SidebarNav({ t, onNavigate, isAdmin = false }) {
  // Les entrées d'exploitation (jobs, détaillants, réglages globaux) sont
  // réservées au rôle admin — le backend les gate aussi (require_admin).
  const groups = NAV_GROUPS.map((g) => ({
    ...g,
    items: g.items.filter((n) => !n.adminOnly || isAdmin),
  })).filter((g) => g.items.length > 0);
  return (
    <nav className="flex flex-col gap-4" aria-label={t("nav.section.market")}>
      {groups.map((group) => (
        <div key={group.section} className="flex flex-col gap-1">
          <div className="px-3 pb-1 font-mono text-[10px] uppercase tracking-[0.14em] text-slate-500">
            {t(group.section)}
          </div>
          {group.items.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              onClick={onNavigate}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm transition-colors ${
                  isActive ? "font-semibold text-slate-100" : "text-slate-400 hover:bg-slate-800/50"
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
  );
}

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
      data-tour="theme"
      className="flex items-center gap-1.5 rounded-full border p-1"
      style={{ borderColor: "var(--border2)", background: "var(--panel2)" }}
      title={t("chrome.theme")}
      role="group"
      aria-label={t("chrome.theme")}
    >
      {THEMES.map((th) => (
        <button
          key={th}
          onClick={() => setTheme(th)}
          title={t(`theme.${th}`)}
          aria-label={t(`theme.${th}`)}
          aria-pressed={theme === th}
          style={{
            width: 18,
            height: 18,
            borderRadius: "50%",
            background: THEME_SWATCH[th],
            cursor: "pointer",
            border: "1px solid var(--border-hover)",
            // Sélection via box-shadow → l'outline reste réservé au focus clavier.
            boxShadow: theme === th ? "0 0 0 2px var(--bg), 0 0 0 4px var(--blue)" : "none",
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
  const { username, role, signOut } = useAuth();
  const isAdmin = role === "admin";
  const { t, setLang } = useI18n();
  const { setTheme } = useTheme();
  const navigate = useNavigate();
  const location = useLocation();
  const [packOpen, setPackOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false); // tiroir de navigation mobile
  useEventStream(); // push SSE → revalide le cache partagé (polling = filet)

  // Relance la visite guidée depuis le Cockpit (les ancres y vivent).
  const replayTour = () => {
    navigate("/cockpit");
    setTimeout(() => startTour(t), 500);
  };

  // Construit la liste de commandes ⌘K : navigation + actions (filtrées par rôle).
  const commands = [
    ...NAV_GROUPS.flatMap((g) =>
      g.items
        .filter((n) => !n.adminOnly || isAdmin)
        .map((n) => ({ id: `nav:${n.to}`, label: t(n.key), hint: t(g.section), run: () => navigate(n.to) }))
    ),
    { id: "act:pack", label: `✦ ${t("pack.cta")}`, hint: t("palette.action"), run: () => setPackOpen(true) },
    { id: "act:tour", label: `🎓 ${t("tour.replay")}`, hint: t("palette.action"), run: replayTour },
    ...THEMES.map((th) => ({ id: `theme:${th}`, label: `${t("chrome.theme")} · ${t(`theme.${th}`)}`, hint: t("chrome.theme"), run: () => setTheme(th) })),
    ...LANGS.map((l) => ({ id: `lang:${l}`, label: `${t("chrome.lang")} · ${l.toUpperCase()}`, hint: t("chrome.lang"), run: () => setLang(l) })),
    { id: "act:signout", label: t("chrome.signOut"), hint: t("palette.action"), run: () => { signOut(); navigate("/login"); } },
  ];

  return (
    <div className="flex min-h-screen flex-col">
      <a href="#pa-main" className="pa-skip-link">{t("chrome.skip")}</a>
      <PackExperience open={packOpen} onClose={() => setPackOpen(false)} />
      <AlertToaster />
      <CommandPalette commands={commands} />
      {/* Header chrome PokéAlpha */}
      <header
        className="sticky top-0 z-50 flex h-[58px] items-center gap-3 px-5 backdrop-blur-xl"
        style={{
          background: "var(--header-bg)",
          borderBottom: "1px solid var(--line)",
        }}
      >
        <button
          onClick={() => setNavOpen(true)}
          className="rounded-lg p-2 text-slate-300 md:hidden"
          style={{ border: "1px solid var(--border2)" }}
          aria-label={t("chrome.menu")}
          aria-expanded={navOpen}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true">
            <line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" />
          </svg>
        </button>
        <Logo />
        <div className="flex-1" />
        <button
          data-tour="palette"
          onClick={() => window.dispatchEvent(new Event("pa:palette"))}
          className="hidden items-center gap-2 rounded-xl px-3 py-2 text-[12px] md:flex"
          style={{ border: "1px solid var(--border2)", background: "var(--panel2)", color: "var(--muted2)" }}
          title={t("palette.placeholder")}
          aria-label={t("palette.placeholder")}
        >
          <span>🔍 {t("palette.search")}</span>
          <kbd className="font-mono text-[10px] tracking-wide" style={{ color: "var(--muted)" }}>⌘K</kbd>
        </button>
        <PwaControls />
        <button
          onClick={replayTour}
          className="hidden h-9 w-9 rounded-xl text-[14px] font-bold sm:block"
          style={{ border: "1px solid var(--border2)", background: "var(--panel2)", color: "var(--muted2)" }}
          title={t("tour.replay")}
          aria-label={t("tour.replay")}
        >
          ?
        </button>
        <button
          data-tour="pack"
          onClick={() => setPackOpen(true)}
          className="hidden rounded-xl px-3 py-2 text-[13px] font-bold transition-shadow sm:block"
          style={{ border: "1px solid rgba(155,123,255,.45)", background: "rgba(155,123,255,.1)", color: "var(--violet-text)" }}
        >
          ✦ {t("pack.cta")}
        </button>
        <ThemeSwitcher />
        <LangSwitcher />
        <AlertsMenu />
        <PlanMenu username={username} onSignOut={() => { invalidatePollingCache(); signOut(); navigate("/login"); }} />
      </header>

      <div className="flex flex-1">
        {/* Sidebar réskinée */}
        <aside
          data-tour="sidebar"
          className="hidden w-56 shrink-0 p-3 md:block"
          style={{ borderRight: "1px solid var(--line)", background: "var(--panel)" }}
        >
          <SidebarNav t={t} isAdmin={isAdmin} />
        </aside>

        {/* Tiroir de navigation mobile (le sidebar est masqué < md) */}
        {navOpen && (
          <div className="fixed inset-0 z-[60] md:hidden" role="dialog" aria-modal="true">
            <div className="absolute inset-0" style={{ background: "rgba(6,4,16,.6)", backdropFilter: "blur(4px)" }}
                 onClick={() => setNavOpen(false)} />
            <div className="absolute inset-y-0 left-0 w-64 overflow-y-auto p-3"
                 style={{ background: "var(--panel-solid)", borderRight: "1px solid var(--border2)" }}>
              <div className="mb-3 flex items-center justify-between px-1">
                <Logo />
                <button onClick={() => setNavOpen(false)} aria-label={t("common.close")}
                        className="h-8 w-8 rounded-lg text-slate-400"
                        style={{ border: "1px solid var(--border2)" }}>✕</button>
              </div>
              <SidebarNav t={t} isAdmin={isAdmin} onNavigate={() => setNavOpen(false)} />
            </div>
          </div>
        )}

        <main id="pa-main" className="flex-1 overflow-x-hidden" tabIndex={-1}>
          <Ticker />
          <div className="p-5 pa-pagein">
            <ErrorBoundary resetKey={location.pathname}>
              <Suspense fallback={<PageSkeleton />}>
                <Outlet />
              </Suspense>
            </ErrorBoundary>
          </div>
        </main>
      </div>
    </div>
  );
}
