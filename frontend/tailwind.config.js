/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Dark navy ground, orange accent. Contrast checked against #0F172A:
        // body 17.0:1, muted 12.0:1, accent 5.0:1, on-accent 5.0:1.
        surface: "#0F172A",
        card: "#111827",
        muted: "#1E293B",
        line: "#475569",
        fg: "#F8FAFC",
        "fg-muted": "#CBD5E1",
        accent: {
          DEFAULT: "#F97316",
          strong: "#EA580C",
          soft: "#FB923C",
        },
      },
      fontFamily: {
        // System stack on purpose: no external font request from a page that
        // handles private expense data.
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "none" },
        },
        fadeOut: {
          from: { opacity: "1", transform: "none" },
          to: { opacity: "0", transform: "translateY(-6px)" },
        },
      },
      animation: {
        "fade-in": "fadeIn 240ms ease-out both",
        "fade-out": "fadeOut 160ms ease-in both",
      },
    },
  },
  plugins: [],
};
