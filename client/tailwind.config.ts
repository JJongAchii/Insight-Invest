import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary (Soft Lavender)
        primary: {
          50: "#F8F4FF",
          100: "#EDE4FF",
          200: "#D4C3FF",
          300: "rgb(var(--primary-soft-rgb) / <alpha-value>)",
          400: "rgb(var(--primary-rgb) / <alpha-value>)",
          500: "#7251EA",
          600: "#6A48E0",
          700: "#5B39CC",
        },
        // Secondary (Sky Blue)
        secondary: {
          50: "#F0F9FF",
          100: "#E0F2FE",
          200: "#BAE6FD",
          300: "#7DD3FC",
          400: "rgb(var(--secondary-rgb) / <alpha-value>)",
          500: "#0EA5E9",
        },
        // Financial semantics (softer tones)
        gains: "rgb(var(--gains-rgb) / <alpha-value>)",
        losses: "rgb(var(--losses-rgb) / <alpha-value>)",
        warning: "rgb(var(--warning-rgb) / <alpha-value>)",
        // Legacy aliases
        success: "rgb(var(--gains-rgb) / <alpha-value>)",
        danger: "rgb(var(--losses-rgb) / <alpha-value>)",

        // Semantic surface/text tokens — :root(다크 기본)/.light 가 정의 (globals.css)
        canvas: "rgb(var(--canvas-rgb) / <alpha-value>)",
        surface: "rgb(var(--surface-rgb) / <alpha-value>)",
        raised: "rgb(var(--surface-raised-rgb) / <alpha-value>)",
        overlay: "rgb(var(--surface-overlay-rgb) / <alpha-value>)",
        ink: {
          DEFAULT: "rgb(var(--text-primary-rgb) / <alpha-value>)",
          secondary: "rgb(var(--text-secondary-rgb) / <alpha-value>)",
          muted: "rgb(var(--text-muted-rgb) / <alpha-value>)",
        },
        edge: {
          DEFAULT: "var(--border)",
          strong: "var(--border-strong)",
        },
        chart: {
          1: "var(--chart-1)",
          2: "var(--chart-2)",
          3: "var(--chart-3)",
          4: "var(--chart-4)",
          5: "var(--chart-5)",
          6: "var(--chart-6)",
          grid: "var(--grid-line)",
        },

        // Custom neutral scale
        neutral: {
          50: "#FAFAFA",
          100: "#F5F5F5",
          200: "#E5E5E5",
          300: "#D4D4D4",
          400: "#A3A3A3",
          500: "#737373",
          600: "#525252",
          700: "#404040",
          800: "#262626",
          900: "#171717",
          950: "#0A0A0A",
        },
      },
      fontFamily: {
        sans: ["Inter", "-apple-system", "BlinkMacSystemFont", "sans-serif"],
        mono: ["SF Mono", "ui-monospace", "Fira Code", "monospace"],
      },
      borderRadius: {
        xl: "12px",
        "2xl": "16px",
      },
      boxShadow: {
        sm: "0 1px 2px rgba(0, 0, 0, 0.04)",
        DEFAULT: "0 1px 3px rgba(0, 0, 0, 0.08)",
        md: "0 4px 6px rgba(0, 0, 0, 0.06)",
        lg: "0 10px 15px rgba(0, 0, 0, 0.08)",
        xl: "0 20px 25px rgba(0, 0, 0, 0.10)",
      },
      transitionDuration: {
        "150": "150ms",
        "200": "200ms",
      },
    },
  },
  plugins: [],
};

export default config;
