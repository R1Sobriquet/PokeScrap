/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Sévérités cohérentes avec Discord (info vert / warning orange / critical rouge).
        info: "#2ECC71",
        warning: "#E67E22",
        critical: "#E74C3C",
      },
    },
  },
  plugins: [],
};
