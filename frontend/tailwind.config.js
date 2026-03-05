/** @type {import("tailwindcss").Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          950: "#020B18",
          900: "#050B18",
          800: "#071221",
          700: "#0A1628",
          600: "#0F1E35",
          500: "#162440",
          400: "#1A2E4A",
          300: "#243858",
        },
        surface: {
          900: "#0A1628",
          800: "#0F1E35",
          700: "#162440",
          600: "#1A2E4A",
          500: "#243858",
          400: "#2D4668",
        },
        accent: {
          DEFAULT: "#00D4FF",
          dark: "#0099BB",
          light: "#33DFFF",
          muted: "rgba(0,212,255,0.15)",
        },
        terminal: {
          green: "#10B981",
          amber: "#F59E0B",
          red: "#EF4444",
          blue: "#3B82F6",
          purple: "#8B5CF6",
          pink: "#EC4899",
        },
      },
      fontFamily: {
        display: ["Space Grotesk", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
      backgroundImage: {
        "navy-gradient": "linear-gradient(135deg, #020B18 0%, #050B18 40%, #071221 100%)",
        "card-gradient": "linear-gradient(135deg, #0F1E35 0%, #0A1628 100%)",
        "accent-gradient": "linear-gradient(135deg, #00D4FF 0%, #0099BB 100%)",
        "score-bar": "linear-gradient(to right, #EF4444 0%, #F59E0B 40%, #10B981 75%, #3B82F6 100%)",
      },
      animation: {
        "pulse-slow": "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "slide-in": "slideIn 0.2s ease-out",
        "fade-in": "fadeIn 0.15s ease-out",
      },
      keyframes: {
        slideIn: {
          "0%": { transform: "translateX(-8px)", opacity: "0" },
          "100%": { transform: "translateX(0)", opacity: "1" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
      boxShadow: {
        "card": "0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3)",
        "card-hover": "0 4px 12px rgba(0,212,255,0.08), 0 2px 4px rgba(0,0,0,0.4)",
        "panel": "0 0 0 1px rgba(26,46,74,0.8), 0 4px 16px rgba(0,0,0,0.3)",
        "accent-glow": "0 0 20px rgba(0,212,255,0.2)",
      },
    },
  },
  plugins: [],
}
