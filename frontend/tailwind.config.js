/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        'background-base': 'var(--bg-base)',
        'background-sidebar': 'var(--bg-sidebar)',
        'background-surface': 'var(--bg-surface)',
        'background-elevated': 'var(--bg-elevated)',
        'text-primary': 'var(--text-primary)',
        'text-secondary': 'var(--text-secondary)',
        'text-tertiary': 'var(--text-tertiary)',
        'text-muted': 'var(--text-muted)',
        'border': 'var(--border)',
        'border-soft': 'var(--border-soft)',
        'border-strong': 'var(--border-strong)',
        'accent': 'var(--accent)',
        'accent-hover': 'var(--accent-hover)',
        'danger': 'var(--danger)',
        'warning': 'var(--warning)',
        'success': 'var(--success)',
        'text-icon-inactive': 'var(--text-icon-inactive)',
        'text-icon-hover': 'var(--text-icon-hover)',
        'role-power-user': 'var(--role-power-user)',
        'role-user': 'var(--role-user)',
      },
      fontFamily: {
        // Must match the faces index.html loads; a name that is never
        // loaded makes font-heading/body/mono silently fall back.
        heading: ['"Instrument Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
        body: ['"Instrument Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInLeft: {
          '0%': { opacity: '0', transform: 'translateX(-8px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        pulseSlow: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        thinkingDot: {
          '0%, 80%, 100%': { transform: 'scale(0)', opacity: '0' },
          '40%': { transform: 'scale(1)', opacity: '1' },
        },
        scaleIn: {
          '0%': { opacity: '0', transform: 'scale(0.97)' },
          '100%': { opacity: '1', transform: 'scale(1)' },
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.25s ease-out forwards',
        'slide-in-left': 'slideInLeft 0.2s ease-out forwards',
        'pulse-slow': 'pulseSlow 2s ease-in-out infinite',
        'scale-in': 'scaleIn 0.2s ease-out forwards',
      },
      screens: {
        xs: '480px',
      },
      boxShadow: {
        card: 'var(--shadow-soft)',
        'card-hover': 'var(--shadow-panel)',
        sidebar: 'var(--shadow-panel)',
      },
    },
  },
  plugins: [],
}
