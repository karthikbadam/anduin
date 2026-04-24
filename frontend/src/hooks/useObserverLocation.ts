import { useCallback, useEffect, useState } from 'react';

export interface ObserverLocation {
  lat: number;
  lon: number;
  alt_km?: number;
}

const LS_KEY = 'anduin.observer';

function load(): ObserverLocation | null {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

/** Observer location with geolocation + manual override. Persists to localStorage.
 * The caller is responsible for registering the observer with the backend via
 * POST /observers or GET /passes (both register implicitly). */
export function useObserverLocation() {
  const [obs, setObs] = useState<ObserverLocation | null>(() => load());
  const [error, setError] = useState<string | null>(null);

  const set = useCallback((v: ObserverLocation | null) => {
    setObs(v);
    if (v) localStorage.setItem(LS_KEY, JSON.stringify(v));
    else localStorage.removeItem(LS_KEY);
  }, []);

  const requestGeolocation = useCallback(() => {
    if (!('geolocation' in navigator)) {
      setError('geolocation not supported');
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setError(null);
        set({ lat: p.coords.latitude, lon: p.coords.longitude });
      },
      (e) => setError(e.message),
      { timeout: 10_000, maximumAge: 60_000 },
    );
  }, [set]);

  // Re-sync from localStorage on visibility change (e.g., user updated in another tab).
  useEffect(() => {
    const handler = () => {
      const stored = load();
      if (stored) setObs(stored);
    };
    window.addEventListener('storage', handler);
    return () => window.removeEventListener('storage', handler);
  }, []);

  return { observer: obs, setObserver: set, requestGeolocation, error };
}
