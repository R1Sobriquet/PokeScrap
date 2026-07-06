// Coquille commune des écrans d'authentification (login, inscription, reset…) :
// carte centrée sur le fond héro, logo PokéAlpha, champs au look terminal.
import { useI18n } from "../i18n.jsx";

export const authField =
  "mt-1 w-full rounded-xl border px-3 py-2.5 text-sm text-slate-100";
export const authFieldStyle = { borderColor: "var(--border2)", background: "var(--panel2)" };
export const authSubmit =
  "w-full rounded-xl px-4 py-2.5 text-sm font-bold text-ink transition-transform disabled:opacity-60";
export const authSubmitStyle = { background: "linear-gradient(180deg, #FFD75A, #FFC91F)" };

export default function AuthShell({ children }) {
  const { t } = useI18n();
  return (
    <div
      className="flex min-h-screen items-center justify-center px-4"
      style={{ background: "var(--hero-overlay), var(--bg)" }}
    >
      <div
        className="w-full max-w-[380px] rounded-2xl border p-7 backdrop-blur-xl"
        style={{
          borderColor: "var(--border2)",
          background: "var(--panel)",
          boxShadow: "0 30px 70px var(--shadow)",
        }}
      >
        <div className="flex items-center gap-2.5">
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: "50%",
              background:
                "conic-gradient(from 210deg, #3D7BFF, #9B7BFF, #FFCB2E, #34D399, #3D7BFF)",
              boxShadow: "inset 0 0 0 6px var(--bg)",
            }}
          />
          <div>
            <div className="text-xl font-extrabold leading-none tracking-tight">
              Poké<span style={{ color: "var(--logo-accent)" }}>Alpha</span>
            </div>
            <div className="mt-1 font-mono text-[10px] uppercase tracking-[0.16em] text-slate-500">
              {t("login.subtitle")}
            </div>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}
