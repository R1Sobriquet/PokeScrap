import { useEffect, useState } from "react";
import { useI18n } from "../i18n.jsx";

// Conversion clé VAPID base64url → Uint8Array (requis par pushManager.subscribe).
function urlB64ToUint8(base64) {
  const pad = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + pad).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

async function enablePush() {
  if (!("Notification" in window)) return "unsupported";
  const perm = await Notification.requestPermission();
  if (perm !== "granted") return "denied";
  const vapid = import.meta.env.VITE_VAPID_PUBLIC_KEY;
  // Push serveur : seulement si une clé VAPID + un service worker sont dispo.
  if (vapid && "serviceWorker" in navigator) {
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8(vapid) });
      await fetch("/api/push/subscribe", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sub),
      }).catch(() => {});
    } catch {
      /* push serveur indispo — la permission locale reste acquise */
    }
  }
  new Notification("PokéAlpha", { body: "Notifications activées — tu seras alerté des restocks & flips.", icon: "/icon.svg" });
  return "granted";
}

export default function PwaControls() {
  const { t } = useI18n();
  const [deferred, setDeferred] = useState(null);
  const [installed, setInstalled] = useState(false);
  const [notif, setNotif] = useState(typeof Notification !== "undefined" ? Notification.permission : "unsupported");

  useEffect(() => {
    const onPrompt = (e) => { e.preventDefault(); setDeferred(e); };
    const onInstalled = () => { setInstalled(true); setDeferred(null); };
    window.addEventListener("beforeinstallprompt", onPrompt);
    window.addEventListener("appinstalled", onInstalled);
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt);
      window.removeEventListener("appinstalled", onInstalled);
    };
  }, []);

  const install = async () => {
    if (!deferred) return;
    deferred.prompt();
    await deferred.userChoice.catch(() => {});
    setDeferred(null);
  };

  const pill = "rounded-xl px-2.5 py-2 text-[12px] font-semibold";
  return (
    <div className="flex flex-none items-center gap-2">
      {deferred && !installed && (
        <button onClick={install} className={pill} title={t("pwa.install")}
                style={{ border: "1px solid var(--border2)", background: "var(--panel2)", color: "var(--text2)" }}>
          ⬇ {t("pwa.install")}
        </button>
      )}
      {notif !== "granted" && notif !== "unsupported" && (
        <button onClick={async () => setNotif(await enablePush())} className={pill} title={t("pwa.notify")}
                style={{ border: "1px solid rgba(155,123,255,.45)", background: "rgba(155,123,255,.1)", color: "var(--violet-text)" }}>
          🔔
        </button>
      )}
    </div>
  );
}
