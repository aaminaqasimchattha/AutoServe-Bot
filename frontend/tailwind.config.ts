import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/**/*.{js,ts,jsx,tsx}',
    './dashboard/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      maxWidth: {
        '85percent': '85%',
        '1600px': '1600px',
      },
      scale: {
        '97': '0.97',
      },
      fontFamily: {
        inter: ['var(--font-inter)', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
      height: {
        '420px': '420px',
      },
    },
  },
  plugins: [],
};

export default config;
