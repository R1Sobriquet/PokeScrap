import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../AuthContext.jsx";
import { useTheme, THEMES } from "../ThemeContext.jsx";
import { useI18n, LANGS } from "../i18n.jsx";
import { usePolling } from "../hooks/usePolling.js";
import PackModal from "./PackModal.jsx";

const SEV_DOT = { critical: "var(--red)", warning: "var(--yellow)", info: "var(--green)" };

function AlertsMenu() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const { data } = usePolling("/alerts?status=pending", { intervalSec: 30 });
  const alerts = data || [];
  return (
    <div className="relative flex-none">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-xl px-2.5 py-2"
        style={{ border: "1px solid rgba(244,88,95,.3)", background: "rgba(244,88,95,.08)" }}
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
const NAV_GROUPS = [
  {
    section: "nav.section.market",
    items: [
      { to: "/cockpit", key: "nav.cockpit" },
      { to: "/opportunites", key: "nav.opportunites" },
      { to: "/sets", key: "nav.sets" },
      { to: "/future", key: "nav.future" },
      { to: "/analyzer", key: "nav.analyzer" },
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
  const [packOpen, setPackOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col">
      <PackModal open={packOpen} onClose={() => setPackOpen(false)} />
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
        <button
          onClick={() => setPackOpen(true)}
          className="hidden rounded-xl px-3 py-2 text-[13px] font-bold transition-shadow sm:block"
          style={{ border: "1px solid rgba(155,123,255,.45)", background: "rgba(155,123,255,.1)", color: "var(--violet-text)" }}
        >
          ✦ {t("pack.cta")}
        </button>
        <ThemeSwitcher />
        <LangSwitcher />
        <AlertsMenu />
        <PlanMenu username={username} onSignOut={() => { signOut(); navigate("/login"); }} />
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
