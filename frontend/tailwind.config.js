/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        bank: {
          bg: "#0b0f19",
          panel: "#121826",
          border: "#1e293b",
          accent: "#3b82f6",
          danger: "#ef4444",
          success: "#22c55e",
          warn: "#f59e0b",
        },
      },
    },
  },
  plugins: [],
};
