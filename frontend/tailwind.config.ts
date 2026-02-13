import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'SF Pro Display', 'sans-serif'],
        mono: ['JetBrains Mono', 'SF Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        brand: {
          blue: '#0055F2',
          'blue-light': '#3B7CFF',
          'blue-soft': '#EBF0FF',
          lime: '#C8E616',
          'lime-soft': '#F5FADC',
        },
        surface: {
          page: '#F5F6F8',
          card: '#FFFFFF',
          elevated: '#FFFFFF',
          sidebar: '#08080F',
        },
        text: {
          primary: '#111318',
          secondary: '#5F6577',
          tertiary: '#8E95A7',
          quaternary: '#B4BAC9',
        },
        border: {
          DEFAULT: 'rgba(0,0,0,0.06)',
          subtle: 'rgba(0,0,0,0.03)',
        },
        risk: {
          low: '#1CA855',
          'low-bg': '#EFFBF3',
          'low-text': '#0C7A3A',
          medium: '#E5A800',
          'medium-bg': '#FFF9E6',
          'medium-text': '#946D00',
          high: '#ED6C02',
          'high-bg': '#FFF5EB',
          'high-text': '#C25700',
          critical: '#E5243B',
          'critical-bg': '#FEF1F2',
          'critical-text': '#BA1A2E',
        },
        primary: {
          50: '#EBF0FF',
          100: '#D6E0FF',
          200: '#ADC1FF',
          300: '#85A3FF',
          400: '#5C84FF',
          500: '#0055F2',
          600: '#0048D1',
          700: '#003BAF',
          800: '#002E8E',
          900: '#00216C',
          950: '#001449',
        },
      },
      boxShadow: {
        'xs': '0 1px 2px rgba(0,0,0,0.04)',
        'sm': '0 1px 2px rgba(0,0,0,0.03), 0 2px 8px rgba(0,0,0,0.03)',
        'md': '0 1px 2px rgba(0,0,0,0.03), 0 4px 16px rgba(0,0,0,0.05)',
        'lg': '0 2px 4px rgba(0,0,0,0.02), 0 8px 32px rgba(0,0,0,0.08)',
      },
      borderRadius: {
        'sm': '8px',
        'md': '12px',
        'lg': '16px',
        'xl': '20px',
      },
      fontSize: {
        'xxs': ['10px', { lineHeight: '14px' }],
      },
      animation: {
        'fade-in': 'fadeIn 0.4s cubic-bezier(0.25, 0.46, 0.45, 0.94) both',
        'fade-in-up': 'fadeInUp 0.5s cubic-bezier(0.25, 0.46, 0.45, 0.94) both',
        'glow': 'glow 3s ease-in-out infinite',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        fadeInUp: {
          from: { opacity: '0', transform: 'translateY(12px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        glow: {
          '0%, 100%': { boxShadow: '0 0 6px rgba(200,230,22,0.4)' },
          '50%': { boxShadow: '0 0 10px rgba(200,230,22,0.6)' },
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};

export default config;
