/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./ui/templates/**/*.html", "./ui/src/input.css"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        bg: "#09090b",
        "bg-raised": "#111113",
        "bg-overlay": "#18181b",
        border: "rgba(255,255,255,0.08)",
        "border-hover": "rgba(255,255,255,0.14)",
      },
      animation: {
        "fade-in": "fadeIn 0.3s ease-out",
        "slide-up": "slideUp 0.35s ease-out both",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        slideUp: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
