/** @type {import('tailwindcss').Config} */

// Helper : couleur Tailwind adossée à un triplet de canaux RGB (`R G B`) exposé
// en variable CSS par index.css. Le placeholder `<alpha-value>` préserve les
// modificateurs d'opacité (ex. `bg-slate-800/40`). Le thème actif (data-pa-theme)
// réécrit les variables → tout le palette bascule au runtime.
const ch = (v) => `rgb(var(${v}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Outfit", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        // Palette « slate » réécrite sur les tokens du design (réskin global sans
        // toucher les pages : chaque nuance pointe vers la variable de thème la
        // plus proche). Les pages existantes basculent ainsi sur les 4 thèmes.
        slate: {
          50: ch("--c-text"),
          100: ch("--c-text"),
          200: ch("--c-text2"),
          300: ch("--c-text2"),
          400: ch("--c-muted2"),
          500: ch("--c-muted"),
          600: ch("--c-faint"),
          700: ch("--c-border-hover"),
          800: ch("--c-border"),
          900: ch("--c-panel"),
          950: ch("--c-bg"),
        },
        // Sévérités (cohérentes Discord) adossées aux tokens du design.
        info: ch("--c-green"),
        warning: ch("--c-yellow"),
        critical: ch("--c-red"),
        // Accents du design réutilisables directement.
        blue: ch("--c-blue"),
        violet: ch("--c-violet"),
        // Texte sombre constant pour les boutons « brillants » (jaune/vert) — ne
        // doit jamais s'éclaircir en thème clair.
        ink: "#12131A",
      },
    },
  },
  plugins: [],
};
