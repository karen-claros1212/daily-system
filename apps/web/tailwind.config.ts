import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        primary: 'var(--ds-primary)',
        primaryLight: 'var(--ds-primary-muted)',
        primaryDark: 'var(--ds-primary-strong)',
        primaryContainer: 'var(--ds-primary-container)',
        onPrimary: 'var(--ds-on-primary)',
        accent: 'var(--ds-accent)',
        accentLight: 'var(--ds-accent-muted)',
        accentDark: 'var(--ds-accent-strong)',
        accentContainer: 'var(--ds-accent-container)',
        tertiary: 'var(--ds-tertiary)',
        success: 'var(--ds-success)',
        successContainer: 'var(--ds-success-container)',
        warning: 'var(--ds-warning)',
        warningContainer: 'var(--ds-warning-container)',
        error: 'var(--ds-danger)',
        errorContainer: 'var(--ds-danger-container)',
        info: 'var(--ds-info)',
        infoContainer: 'var(--ds-info-container)',
        bg: 'var(--ds-bg)',
        surface: 'var(--ds-surface)',
        surfaceElevated: 'var(--ds-surface-elevated)',
        surfaceContainer: 'var(--ds-surface-muted)',
        textPrimary: 'var(--ds-fg)',
        textSecondary: 'var(--ds-fg-muted)',
        outline: 'var(--ds-border)',
        outlineStrong: 'var(--ds-border-strong)',
        focus: 'var(--ds-focus-ring)',
      },
      boxShadow: {
        xs: 'var(--ds-shadow-xs)',
        sm: 'var(--ds-shadow-sm)',
        md: 'var(--ds-shadow-md)',
        lg: 'var(--ds-shadow-lg)',
      },
      borderRadius: {
        sm: 'var(--ds-radius-sm)',
        md: 'var(--ds-radius-md)',
        lg: 'var(--ds-radius-lg)',
        full: 'var(--ds-radius-full)',
      },
      spacing: {
        md: 'var(--ds-space-4)',
        lg: 'var(--ds-space-6)',
      },
      fontFamily: {
        sans: ['var(--ds-font-sans)'],
      },
    },
  },
  plugins: [],
};

export default config;