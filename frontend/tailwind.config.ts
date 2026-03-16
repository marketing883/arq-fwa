import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      colors: {
        // ArqAI Brand
        "arq-blue": {
          400: "#4F7AEF",
          500: "#2A5BDB",
          600: "#1E45B0",
          700: "#162E80",
          900: "#0B1A40",
        },
        "arq-lime": {
          400: "#A3E635",
          500: "#84CC16",
        },
        // Surface system (dark)
        surface: {
          0: "#0A0E1A",
          1: "#111827",
          2: "#1A2235",
          3: "#243044",
        },
        // Semantic text
        "t-primary": "#F1F5F9",
        "t-secondary": "#94A3B8",
        "t-muted": "#64748B",
        // Risk (dark-mode optimized)
        risk: {
          low: "#22c55e",
          medium: "#f59e0b",
          high: "#ef4444",
          critical: "#991b1b",
        },
        // Primary alias → arq-blue (backward compat for any leftover usage)
        primary: {
          400: "#4F7AEF",
          500: "#2A5BDB",
          600: "#1E45B0",
          700: "#1E45B0",
          800: "#0B1A40",
          900: "#0B1A40",
        },
      },
      boxShadow: {
        glow: "0 0 20px rgba(42, 91, 219, 0.15)",
        "glow-lg": "0 0 40px rgba(42, 91, 219, 0.2)",
        "glow-lime": "0 0 20px rgba(163, 230, 53, 0.15)",
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
