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
        sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
};
