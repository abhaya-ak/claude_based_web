import type { Config } from 'tailwindcss';

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        gov: {
          blue: '#003366',
          navy: '#001f3f',
          red: '#c0392b',
          yellow: '#f39c12',
          green: '#27ae60',
          gray: '#f4f6f8',
          border: '#d1d5db',
        },
        high: {
          bg: '#000000',
          fg: '#ffffff',
          yellow: '#ffff00',
          cyan: '#00ffff',
          green: '#00ff00',
          red: '#ff3333',
          border: '#ffffff',
          surface: '#121212',
        },
      },
      fontSize: {
        'a11y-xs': 'var(--a11y-font-xs, 0.75rem)',
        'a11y-sm': 'var(--a11y-font-sm, 0.875rem)',
        'a11y-base': 'var(--a11y-font-base, 1rem)',
        'a11y-lg': 'var(--a11y-font-lg, 1.125rem)',
        'a11y-xl': 'var(--a11y-font-xl, 1.25rem)',
        'a11y-2xl': 'var(--a11y-font-2xl, 1.5rem)',
        'a11y-3xl': 'var(--a11y-font-3xl, 1.875rem)',
      },
    },
  },
  plugins: [],
} satisfies Config;
