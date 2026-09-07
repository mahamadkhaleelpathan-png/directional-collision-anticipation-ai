/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        hud: ['"Rajdhani"', '"Inter"', 'system-ui', 'sans-serif'],
      },
      colors: {
        hud: {
          bg: '#0B0F19',
          panel: '#111827',
          panel2: '#0F172A',
          border: '#1E293B',
          cyan: '#22D3EE',
          cyanDim: '#0891B2',
          blue: '#3B82F6',
          green: '#34D399',
          amber: '#FBBF24',
          red: '#F87171',
          text: '#E2E8F0',
          dim: '#64748B',
        },
      },
      boxShadow: {
        hud: '0 0 20px rgba(34, 211, 238, 0.08), inset 0 0 20px rgba(34, 211, 238, 0.03)',
        hudHover: '0 0 30px rgba(34, 211, 238, 0.2), inset 0 0 25px rgba(34, 211, 238, 0.05)',
        glowCyan: '0 0 15px rgba(34, 211, 238, 0.4)',
        glowRed: '0 0 20px rgba(248, 113, 113, 0.5)',
        glowGreen: '0 0 15px rgba(52, 211, 153, 0.4)',
      },
      borderRadius: {
        hud: '0.75rem',
      },
    },
  },
  plugins: [],
};
