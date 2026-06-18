import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../api.js";
import { useAuth } from "../AuthContext.jsx";
import { useI18n } from "../i18n.jsx";

export default function Login() {
  const { signIn } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { access_token } = await login(username, password);
      signIn(access_token, username);
      navigate("/cockpit", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const field =
    "mt-1 w-full rounded-xl border px-3 py-2.5 text-sm text-slate-100 outline-none";
  const fieldStyle = { borderColor: "var(--border2)", background: "var(--panel2)" };

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

        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <label className="block text-xs text-slate-400">
            {t("login.user")}
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              className={field}
              style={fieldStyle}
            />
          </label>
          <label className="block text-xs text-slate-400">
            {t("login.pass")}
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
              className={field}
              style={fieldStyle}
            />
          </label>
          {error && <p className="text-sm text-critical">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-xl px-4 py-2.5 text-sm font-bold text-ink transition-transform disabled:opacity-60"
            style={{ background: "linear-gradient(180deg, #FFD75A, #FFC91F)" }}
          >
            {loading ? t("login.submitting") : t("login.submit")}
          </button>
        </form>
      </div>
    </div>
  );
}
