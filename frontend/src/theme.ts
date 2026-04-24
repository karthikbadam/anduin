import { extendTheme, type ThemeConfig } from '@chakra-ui/react';

const config: ThemeConfig = {
  initialColorMode: 'dark',
  useSystemColorMode: false,
};

// Palette matches karthikbadam.com: restrained zinc/neutral dark, no saturated
// accent. Data points on the map use white-with-alpha instead of cyan so they
// read as faint stars rather than a brand color.
export const theme = extendTheme({
  config,
  colors: {
    bg: {
      body: '#0a0a0b',      // ~zinc-950 with a hint of warmth
      panel: '#141418',     // card/sidebar background
      border: '#27272a',    // ~zinc-800
    },
    fg: {
      primary: '#e4e4e7',   // ~zinc-200
      muted: '#a1a1aa',     // ~zinc-400
      subtle: '#71717a',    // ~zinc-500
    },
    // Reserved accents (Stage 2/3 alerts + pass visibility). Kept warm/low-sat.
    accent: {
      amber: '#f59e0b',
      red: '#ef4444',
      green: '#22c55e',
    },
  },
  styles: {
    global: {
      body: {
        bg: 'bg.body',
        color: 'fg.primary',
      },
    },
  },
});
