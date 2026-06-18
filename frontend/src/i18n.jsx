// Internationalisation légère (FR / EN), bascule dans l'app. Persisté en
// localStorage. `t(key)` retourne la chaîne traduite (fallback : la clé).
//
// Le contexte a une valeur PAR DÉFAUT en français : les composants peuvent donc
// appeler `useI18n()` hors d'un <I18nProvider> (ex. tests de pages unitaires) et
// obtenir le FR sans planter — le provider n'est requis que pour la bascule.

import { createContext, useContext, useEffect, useState } from "react";

export const LANGS = ["fr", "en"];
const STORAGE_KEY = "pa-lang";

const DICT = {
  fr: {
    "app.name": "PokéAlpha",
    "nav.section.market": "Marché",
    "nav.section.portfolio": "Portefeuille",
    "nav.section.ops": "Opérations",
    "nav.cockpit": "Cockpit",
    "nav.opportunites": "Opportunités",
    "nav.portefeuille": "Portefeuille",
    "nav.watchlist": "Watchlist",
    "nav.sets": "Sets & Movers",
    "nav.lots": "Lots & Liquidation",
    "nav.ledger": "Ledger & Fiscalité",
    "nav.grading": "Grading",
    "nav.restock": "Veille restock",
    "nav.detaillants": "Détaillants",
    "nav.calendrier": "Calendrier",
    "nav.jobs": "Actions & Jobs",
    "nav.reglages": "Réglages",
    "chrome.signOut": "Déconnexion",
    "chrome.theme": "Thème",
    "chrome.lang": "Langue",
    "theme.dark": "Sombre",
    "theme.light": "Clair",
    "theme.holo": "Holo",
    "theme.ember": "Ember",
    "login.subtitle": "Intelligence TCG Pokémon",
    "login.user": "Identifiant",
    "login.pass": "Mot de passe",
    "login.submit": "Se connecter",
    "login.submitting": "Connexion…",
    "landing.badge": "INTELLIGENCE TCG · IA",
    "landing.titlePre": "Repère les ",
    "landing.titleHi": "pépites",
    "landing.titlePost": " avant tout le monde",
    "landing.subtitle":
      "Intelligence TCG Pokémon par IA pour collectionneurs, investisseurs et chasseurs de scellé. Suis chaque set, note chaque deal, surfe chaque vague.",
    "landing.cta.explore": "Explorer le marché",
    "landing.cta.launch": "Lancer l'app",
    "landing.stat.products": "produits suivis",
    "landing.stat.sets": "sets surveillés",
    "landing.stat.signals": "signaux aujourd'hui",
    "landing.stat.confidence": "confiance moyenne",
    "landing.movers": "PLUS GROS MOUVEMENTS · LIVE",
    "landing.section.terminal": "LE TERMINAL",
    "landing.section.title": "Des outils de niveau Bloomberg, un cœur de collectionneur",
    "landing.feature.future.kicker": "FUTURE RADAR",
    "landing.feature.future.title": "Vois les sets avant le marché",
    "landing.feature.future.desc":
      "Sets à venir et rumeurs suivis via dépôts d'impression, supply chain et vélocité communautaire.",
    "landing.feature.future.link": "Ouvrir Future Radar →",
    "landing.feature.analyzer.kicker": "DEAL ANALYZER",
    "landing.feature.analyzer.title": "Note n'importe quelle annonce en secondes",
    "landing.feature.analyzer.desc":
      "Colle une URL Cardmarket, eBay ou Leboncoin — obtiens un verdict face aux comparables live.",
    "landing.feature.analyzer.link": "Essayer l'Analyzer →",
    "landing.feature.portfolio.kicker": "PORTFOLIO VAULT",
    "landing.feature.portfolio.title": "Ta collection, valorisée au marché",
    "landing.feature.portfolio.desc":
      "Slabs gradés et cases scellées revalorisés chaque heure, avec le ROI depuis ton achat.",
    "landing.feature.portfolio.link": "Ouvrir le Vault →",
  },
  en: {
    "app.name": "PokéAlpha",
    "nav.section.market": "Market",
    "nav.section.portfolio": "Portfolio",
    "nav.section.ops": "Operations",
    "nav.cockpit": "Dashboard",
    "nav.opportunites": "Opportunities",
    "nav.portefeuille": "Portfolio",
    "nav.watchlist": "Watchlist",
    "nav.sets": "Sets & Movers",
    "nav.lots": "Lots & Liquidation",
    "nav.ledger": "Ledger & Tax",
    "nav.grading": "Grading",
    "nav.restock": "Restock Watch",
    "nav.detaillants": "Retailers",
    "nav.calendrier": "Calendar",
    "nav.jobs": "Actions & Jobs",
    "nav.reglages": "Settings",
    "chrome.signOut": "Sign out",
    "chrome.theme": "Theme",
    "chrome.lang": "Language",
    "theme.dark": "Dark",
    "theme.light": "Light",
    "theme.holo": "Holo",
    "theme.ember": "Ember",
    "login.subtitle": "Pokémon TCG Intelligence",
    "login.user": "Username",
    "login.pass": "Password",
    "login.submit": "Sign in",
    "login.submitting": "Signing in…",
    "landing.badge": "AI-POWERED TCG INTELLIGENCE",
    "landing.titlePre": "Find Tomorrow's ",
    "landing.titleHi": "Grails",
    "landing.titlePost": " Before Everyone Else",
    "landing.subtitle":
      "AI-powered Pokémon TCG intelligence for collectors, investors and sealed product hunters. Track every set, grade every deal, ride every run.",
    "landing.cta.explore": "Explore the Market",
    "landing.cta.launch": "Launch App",
    "landing.stat.products": "products tracked",
    "landing.stat.sets": "sets monitored",
    "landing.stat.signals": "signals today",
    "landing.stat.confidence": "avg confidence",
    "landing.movers": "BIGGEST MOVERS TODAY · LIVE",
    "landing.section.terminal": "THE TERMINAL",
    "landing.section.title": "Bloomberg-grade tools, collector's heart",
    "landing.feature.future.kicker": "FUTURE RADAR",
    "landing.feature.future.title": "See sets before the market does",
    "landing.feature.future.desc":
      "Unreleased and rumored sets tracked from print filings, supply chains and community velocity.",
    "landing.feature.future.link": "Open Future Radar →",
    "landing.feature.analyzer.kicker": "DEAL ANALYZER",
    "landing.feature.analyzer.title": "Grade any listing in seconds",
    "landing.feature.analyzer.desc":
      "Paste a Cardmarket, eBay or Leboncoin URL — get a verdict against live comps.",
    "landing.feature.analyzer.link": "Try the Analyzer →",
    "landing.feature.portfolio.kicker": "PORTFOLIO VAULT",
    "landing.feature.portfolio.title": "Your collection, marked to market",
    "landing.feature.portfolio.desc":
      "Graded slabs and sealed cases revalued hourly, with ROI since the day you bought in.",
    "landing.feature.portfolio.link": "Open the Vault →",
  },
};

function translate(lang, key) {
  return (DICT[lang] && DICT[lang][key]) || DICT.fr[key] || key;
}

function readInitial() {
  if (typeof localStorage !== "undefined") {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && LANGS.includes(saved)) return saved;
  }
  return "fr";
}

const I18nContext = createContext({
  lang: "fr",
  setLang: () => {},
  t: (key) => translate("fr", key),
});

export function I18nProvider({ children }) {
  const [lang, setLangState] = useState(readInitial);

  useEffect(() => {
    if (typeof localStorage !== "undefined") localStorage.setItem(STORAGE_KEY, lang);
    if (typeof document !== "undefined") document.documentElement.setAttribute("lang", lang);
  }, [lang]);

  const setLang = (l) => LANGS.includes(l) && setLangState(l);
  const t = (key) => translate(lang, key);

  return <I18nContext.Provider value={{ lang, setLang, t }}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  return useContext(I18nContext);
}
