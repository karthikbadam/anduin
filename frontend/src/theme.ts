import { extendTheme, type ThemeConfig } from '@chakra-ui/react';

// Default to the user's system mode; users can toggle with the StatusBar switch.
const config: ThemeConfig = {
  initialColorMode: 'system',
  useSystemColorMode: true,
};

// Palette uses semantic tokens so every chrome element responds to the
// light/dark toggle. Dark mode stays near-black zinc (matches karthikbadam.com);
// light mode is a warm off-white with the same restrained hierarchy.
export const theme = extendTheme({
  config,
  semanticTokens: {
    colors: {
      'bg.body':    { default: '#fafaf9', _dark: '#0a0a0b' },
      'bg.panel':   { default: '#ffffff', _dark: '#141418' },
      'bg.border':  { default: '#e4e4e7', _dark: '#27272a' },
      'fg.primary': { default: '#18181b', _dark: '#e4e4e7' },
      'fg.muted':   { default: '#52525b', _dark: '#a1a1aa' },
      'fg.subtle':  { default: '#71717a', _dark: '#71717a' },
      // Reserved accents (stage 2 pass badges, stage 3 alerts).
      'accent.amber': { default: '#d97706', _dark: '#f59e0b' },
      'accent.red':   { default: '#dc2626', _dark: '#ef4444' },
      'accent.green': { default: '#16a34a', _dark: '#22c55e' },
    },
  },
  styles: {
    global: {
      body: { bg: 'bg.body', color: 'fg.primary' },
    },
  },
});
