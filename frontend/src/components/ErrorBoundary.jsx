import { Component } from "react";

// Garde-fou : une page qui crashe n'emporte plus tout le shell (header/sidebar
// restent utilisables). Composant classe (seule API React pour attraper les
// erreurs de rendu) → pas de hook i18n ; on lit la langue persistée directement.
function lang() {
  try {
    return localStorage.getItem("pa-lang") || "fr";
  } catch {
    return "fr";
  }
}

const TEXTS = {
  fr: {
    title: "Cette page a rencontré un problème",
    body: "L'erreur est locale à cet écran — le reste de l'app fonctionne. Réessaie, ou navigue vers un autre écran.",
    retry: "Réessayer",
  },
  en: {
    title: "This page hit a problem",
    body: "The error is local to this screen — the rest of the app still works. Retry, or navigate to another screen.",
    retry: "Retry",
  },
};

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("ErrorBoundary:", error, info?.componentStack);
  }

  componentDidUpdate(prevProps) {
    // Changer de route réarme le boundary (l'erreur était propre à la page).
    if (this.state.error && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ error: null });
    }
  }

  render() {
    if (!this.state.error) return this.props.children;
    const t = TEXTS[lang()] || TEXTS.fr;
    return (
      <div className="mx-auto mt-16 max-w-md rounded-2xl p-8 text-center"
           style={{ background: "var(--panel)", border: "1px solid var(--border2)" }}
           role="alert">
        <div style={{ fontSize: 40 }}>🫠</div>
        <h2 className="mt-3 text-lg font-extrabold">{t.title}</h2>
        <p className="mt-2 text-sm" style={{ color: "var(--muted2)" }}>{t.body}</p>
        <p className="mt-2 font-mono text-[11px]" style={{ color: "var(--faint)" }}>
          {String(this.state.error?.message || this.state.error).slice(0, 160)}
        </p>
        <button onClick={() => this.setState({ error: null })}
                className="mt-5 rounded-xl px-4 py-2.5 text-sm font-bold text-ink"
                style={{ background: "linear-gradient(180deg, #FFD75A, #FFC91F)" }}>
          {t.retry}
        </button>
      </div>
    );
  }
}
