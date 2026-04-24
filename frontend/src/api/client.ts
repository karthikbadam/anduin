import axios from 'axios';

// Runtime-configurable base URL (emitted into /env.js by nginx envsubst in prod,
// fallback to dev proxy at /api). API key is dev-only — persist to localStorage
// for convenience but the user can override it in the UI.
declare global {
  interface Window {
    ANDUIN_CONFIG?: {
      API_BASE?: string;
      WS_BASE?: string;
    };
  }
}

const runtimeBase =
  (typeof window !== 'undefined' && window.ANDUIN_CONFIG?.API_BASE) || '/api';

const DEV_KEY_FALLBACK = 'dev-key-anduin-local-only';
const LS_KEY = 'anduin.apiKey';

export function getApiKey(): string {
  if (typeof localStorage === 'undefined') return DEV_KEY_FALLBACK;
  return localStorage.getItem(LS_KEY) ?? DEV_KEY_FALLBACK;
}

export function setApiKey(v: string) {
  localStorage.setItem(LS_KEY, v);
}

export const api = axios.create({
  baseURL: runtimeBase,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((cfg) => {
  cfg.headers['X-API-Key'] = getApiKey();
  return cfg;
});
