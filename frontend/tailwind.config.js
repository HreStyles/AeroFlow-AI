/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        aero: {
          bg: "#0a0f1a",
          card: "#111827",
          border: "#1e293b",
          red: "#ef4444",
          green: "#22c55e",
          blue: "#3b82f6",
          amber: "#f59e0b",
          muted: "#64748b",
          text: "#e2e8f0",
        },
      },
      fontFamily: {
        sans: ["Inter Variable", "Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        panel: "0 1px 2px rgba(0,0,0,0.4), 0 8px 24px -12px rgba(0,0,0,0.5)",
        glow: "0 0 12px rgba(59,130,246,0.35)",
      },
    },
  },
  plugins: [],
};
