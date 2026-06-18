// Thème visuel PokéAlpha (dark / light / holo / ember). Le thème actif est posé
// sur <html data-pa-theme> ; index.css réécrit alors toutes les variables CSS et
// le palette Tailwind bascule au runtime. Persisté en localStorage.

import { createContext, useContext, useEffect, useState } from "react";

export const THEMES = ["dark", "light", "holo", "ember"];
const STORAGE_KEY = "pa-theme";

function readInitial() {
  if (typeof localStorage !== "undefined") {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved && THEMES.includes(saved)) return saved;
  }
  return "dark";
}

const ThemeContext = createContext({ theme: "dark", setTheme: () => {} });

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(readInitial);

  useEffect(() => {
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-pa-theme", theme);
    }
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(STORAGE_KEY, theme);
    }
  }, [theme]);

  const setTheme = (t) => THEMES.includes(t) && setThemeState(t);

  return (
    <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
