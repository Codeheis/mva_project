/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        base:    '#0f0f17',
        surface: '#13131f',
        raised:  '#1a1a2e',
        accent:  { DEFAULT: '#6366f1', light: '#818cf8', dark: '#4f46e5' },
      },
      fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
      boxShadow: {
        'glow-sm': '0 0 16px rgba(99,102,241,0.2)',
        'glow':    '0 0 32px rgba(99,102,241,0.25)',
        'glow-lg': '0 0 48px rgba(99,102,241,0.3)',
        'card':    '0 8px 32px rgba(0,0,0,0.4)',
      },
      backgroundImage: {
        'accent-grad': 'linear-gradient(135deg,#6366f1,#4f46e5)',
        'accent-grad-soft': 'linear-gradient(135deg,rgba(99,102,241,0.15),rgba(79,70,229,0.08))',
      },
    },
  },
  plugins: [],
};
