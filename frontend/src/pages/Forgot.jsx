import { useState } from "react";
import { Link } from "react-router-dom";
import { forgotPassword } from "../api.js";
import { useI18n } from "../i18n.jsx";
import AuthShell, { authField, authFieldStyle, authSubmit, authSubmitStyle } from "../components/AuthShell.jsx";

export default function Forgot() {
  const { t } = useI18n();
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await forgotPassword(email);
      setDone(true); // toujours 200 côté backend (anti-énumération)
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      {done ? (
        <div className="mt-6 space-y-4 text-center">
          <p className="text-sm text-slate-300">✉️ {t("auth.forgot.sent")}</p>
          <Link to="/login" className="block text-sm font-semibold" style={{ color: "var(--blue-soft)" }}>
            {t("auth.backToLogin")}
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="mt-6 space-y-4">
          <p className="text-xs text-slate-500">{t("auth.forgot.intro")}</p>
          <label className="block text-xs text-slate-400">
            {t("auth.email")}
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                   autoComplete="email" required className={authField} style={authFieldStyle} />
          </label>
          {error && <p className="text-sm text-critical" role="alert">{error}</p>}
          <button type="submit" disabled={loading} className={authSubmit} style={authSubmitStyle}>
            {loading ? t("auth.forgot.submitting") : t("auth.forgot.submit")}
          </button>
        </form>
      )}
    </AuthShell>
  );
}
