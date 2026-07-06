import { useState } from "react";
import { Link } from "react-router-dom";
import { registerAccount } from "../api.js";
import { useI18n } from "../i18n.jsx";
import AuthShell, { authField, authFieldStyle, authSubmit, authSubmitStyle } from "../components/AuthShell.jsx";

export default function Register() {
  const { t } = useI18n();
  const [form, setForm] = useState({ email: "", username: "", password: "" });
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await registerAccount(form);
      setDone(true);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      {done ? (
        <div className="mt-6 space-y-4">
          <p className="text-sm text-slate-300">✉️ {t("auth.register.sent")}</p>
          <Link to="/login" className="block text-center text-sm font-semibold" style={{ color: "var(--blue-soft)" }}>
            {t("auth.backToLogin")}
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <label className="block text-xs text-slate-400">
            {t("auth.email")}
            <input type="email" value={form.email} onChange={set("email")}
                   autoComplete="email" required className={authField} style={authFieldStyle} />
          </label>
          <label className="block text-xs text-slate-400">
            {t("login.user")}
            <input type="text" value={form.username} onChange={set("username")}
                   autoComplete="username" required className={authField} style={authFieldStyle} />
          </label>
          <label className="block text-xs text-slate-400">
            {t("login.pass")} <span className="text-slate-600">({t("auth.password.hint")})</span>
            <input type="password" value={form.password} onChange={set("password")}
                   autoComplete="new-password" required minLength={8}
                   className={authField} style={authFieldStyle} />
          </label>
          {error && <p className="text-sm text-critical" role="alert">{error}</p>}
          <button type="submit" disabled={loading} className={authSubmit} style={authSubmitStyle}>
            {loading ? t("auth.register.submitting") : t("auth.register.submit")}
          </button>
          <p className="text-center text-xs text-slate-500">
            {t("auth.register.haveAccount")}{" "}
            <Link to="/login" className="font-semibold" style={{ color: "var(--blue-soft)" }}>
              {t("login.submit")}
            </Link>
          </p>
        </form>
      )}
    </AuthShell>
  );
}
