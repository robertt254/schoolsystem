/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{vue,js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#0A192F',
          light: '#112240',
        },
        red: {
          accent: '#E63946',
          hover: '#D62828',
        },
        gray: {
          bg: '#F3F4F6',
        }
      }
    },
  },
  plugins: [],
}
