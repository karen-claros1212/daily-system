import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#0B4654',
        primaryLight: '#125466',
        primaryDark: '#083340',
        primaryContainer: '#B0D4DE',
        accent: '#0F6B55',
        accentLight: '#14916F',
        accentContainer: '#B2DFD6',
        tertiary: '#D7A33D',
        success: '#0F6B55',
        warning: '#8A5A00',
        error: '#B3261E',
        surface: '#F6F8F7',
        surfaceContainer: '#EDEDED',
        textPrimary: '#17242B',
        textSecondary: '#5F6368',
        outline: '#B0B0B0',
      },
      borderRadius: {
        sm: '8px',
        md: '12px',
        lg: '16px',
      },
      spacing: {
        md: '16px',
        lg: '24px',
      },
    },
  },
  plugins: [],
};

export default config;
