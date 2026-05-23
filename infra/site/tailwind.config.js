/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./app/templates/**/*.html'],
  theme: {
    extend: {
      colors: {
        bg: { main: '#F7F3EB', card: '#FFFFFF', alt: '#EFE9DD' },
        text: { primary: '#1A1818', secondary: '#4A4541', muted: '#6B6661' },
        accent: { gold: '#B8935A', goldDk: '#966D40' },
        cta: { DEFAULT: '#B8351F', hover: '#9A2B17' },
        success: '#5F8B5C',
        warning: '#C48A2C',
        border: { light: '#E8DCC0', strong: '#C9B898' },
      },
      fontFamily: {
        serif: ['"Cormorant Garamond"', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'Menlo', 'monospace'],
      },
      fontSize: {
        hero: ['clamp(3.5rem, 8vw, 7rem)', { lineHeight: '0.95', letterSpacing: '-0.03em' }],
      },
      boxShadow: {
        card: '0 8px 24px rgba(26,24,24,0.06)',
        cta: '0 4px 16px rgba(184,53,31,0.25)',
        ctaHover: '0 8px 24px rgba(184,53,31,0.35)',
      },
      animation: {
        'fade-in-up': 'fadeInUp 600ms ease-out both',
        'gentle-pulse': 'gentlePulse 2.4s ease-in-out infinite',
      },
      keyframes: {
        fadeInUp: {
          '0%': { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        gentlePulse: {
          '0%, 100%': { opacity: '0.7' },
          '50%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [],
};
