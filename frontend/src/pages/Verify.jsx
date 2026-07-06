import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { verifyEmail } from "../api.js";
import { useI18n } from "../i18n.jsx";
import AuthShell from "../components/AuthShell.jsx";

// Cible du lien reçu par email : /verify?token=… — vérifie au montage.
export default function Verify() {
  const { t } = useI18n();
  const [params] = useSearchParams();
  const [state, setState] = useState("pending"); // pending|ok|error
  const [message, setMessage] = useState("");
  const ran = useRef(false); // StrictMode double-mount : le jeton est à usage unique

  useEffect(() => {
    const token = params.get("token");
    if (!token) {
      setState("error");
      setMessage(t("auth.verify.missing"));
      return;
    }
    if (ran.current) return;
    ran.current = true;
    verifyEmail(token)
      .then(() => setState("ok"))
      .catch((err) => {
        setState("error");
        setMessage(err.message);
      });
  }, [params, t]);

  return (
    <AuthShell>
      <div className="mt-6 space-y-4 text-center">
        {state === "pending" && <p className="text-sm text-slate-400">{t("auth.verify.checking")}</p>}
        {state === "ok" && <p className="text-sm" style={{ color: "var(--green-text)" }}>✅ {t("auth.verify.ok")}</p>}
        {state === "error" && <p className="text-sm text-critical" role="alert">{message}</p>}
        <Link to="/login" className="block text-sm font-semibold" style={{ color: "var(--blue-soft)" }}>
          {t("auth.backToLogin")}
        </Link>
      </div>
    </AuthShell>
  );
}
