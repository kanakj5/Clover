/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        forest: {
          50: '#f0fdf4',
          100: '#dcfce7',
          200: '#bbf7d0',
          300: '#86efac',
          400: '#4ade80',
          500: '#22c55e',
          600: '#16a34a',
          700: '#15803d',
          800: '#166534',
          900: '#14532d',
          950: '#052e16',
        },
        mint: {
          50: '#f2fcf5',
          100: '#e1f8eb',
          200: '#c5f2d7',
          300: '#97e6bc',
          400: '#60d19c',
          500: '#38b781',
          600: '#289467',
          700: '#227654',
          800: '#1e5e44',
          900: '#1a4e39',
        },
      },
    },
  },
  plugins: [],
}
