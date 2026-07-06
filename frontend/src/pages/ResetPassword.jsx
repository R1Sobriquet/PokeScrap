import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { resetPassword } from "../api.js";
import { useI18n } from "../i18n.jsx";
import AuthShell, { authField, authFieldStyle, authSubmit, authSubmitStyle } from "../components/AuthShell.jsx";

// Cible du lien reçu par email : /reset?token=… — choisit le nouveau mot de passe.
export default function ResetPassword() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (password !== confirm) {
      setError(t("auth.reset.mismatch"));
      return;
    }
    setLoading(true);
    try {
      await resetPassword(params.get("token") || "", password);
      navigate("/login", { replace: true });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell>
      <form onSubmit={handleSubmit} className="mt-6 space-y-4">
        <label className="block text-xs text-slate-400">
          {t("auth.reset.new")} <span className="text-slate-600">({t("auth.password.hint")})</span>
          <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                 autoComplete="new-password" required minLength={8}
                 className={authField} style={authFieldStyle} />
        </label>
        <label className="block text-xs text-slate-400">
          {t("auth.reset.confirm")}
          <input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)}
                 autoComplete="new-password" required minLength={8}
                 className={authField} style={authFieldStyle} />
        </label>
        {error && <p className="text-sm text-critical" role="alert">{error}</p>}
        <button type="submit" disabled={loading} className={authSubmit} style={authSubmitStyle}>
          {loading ? t("auth.reset.submitting") : t("auth.reset.submit")}
        </button>
        <Link to="/login" className="block text-center text-xs" style={{ color: "var(--blue-soft)" }}>
          {t("auth.backToLogin")}
        </Link>
      </form>
    </AuthShell>
  );
}
