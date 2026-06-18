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
