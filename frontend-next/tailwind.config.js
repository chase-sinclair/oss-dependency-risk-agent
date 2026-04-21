/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Tactical "Midnight Carbon" palette
        "mc":      "#0B0E14",   // midnight-carbon background
        "sc":      "#161B22",   // surface-carbon cards
        "nc":      "#FF4C4C",   // neon-crimson critical
        "ep":      "#00E676",   // emerald-pulse healthy
        "ev":      "#8B5CF6",   // electric-violet agent/AI
        "tp":      "#F0F6FC",   // text-primary
        "tm":      "#8B9BB4",   // text-muted
        // Legacy aliases kept for backward-compat
        sidebar:  "#0f172a",
        healthy:  "#16a34a",
        warning:  "#ca8a04",
        critical: "#dc2626",
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Courier New"', 'monospace'],
      },
      backdropBlur: {
        glass: '10px',
      },
    },
  },
  plugins: [],
};
