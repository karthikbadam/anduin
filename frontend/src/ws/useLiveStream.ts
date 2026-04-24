import { useEffect, useRef } from 'react';
import { getApiKey } from '../api/client';
import { useLiveStore } from './store';

interface WsFrame {
  topic: string;
  ts: number;
  data?: any;
}

declare global {
  interface Window {
    ANDUIN_CONFIG?: { API_BASE?: string; WS_BASE?: string };
  }
}

function wsUrl(): string {
  // Prefer explicit WS base from env.js; fall back to same-origin /ws.
  const base =
    (typeof window !== 'undefined' && window.ANDUIN_CONFIG?.WS_BASE) ||
    `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`;
  const apiKey = encodeURIComponent(getApiKey());
  return `${base.replace(/\/$/, '')}/stream?api_key=${apiKey}`;
}

/** Single persistent WebSocket to /ws/stream with exponential-backoff reconnect.
 * On connect, subscribes to satellite.position + alerts + passes and routes
 * frames into the Zustand live store. */
export function useLiveStream() {
  const upsert = useLiveStore((s) => s.upsertPosition);
  const setConnected = useLiveStore((s) => s.setConnected);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(1000);
  const stopRef = useRef(false);

  useEffect(() => {
    stopRef.current = false;

    const open = () => {
      const ws = new WebSocket(wsUrl());
      wsRef.current = ws;

      ws.addEventListener('open', () => {
        backoffRef.current = 1000;
        setConnected(true);
        ws.send(JSON.stringify({
          subscribe: ['satellite.position', 'passes', 'alerts'],
        }));
      });

      ws.addEventListener('message', (evt) => {
        let f: WsFrame;
        try { f = JSON.parse(evt.data); } catch { return; }
        if (f.topic === 'satellite.position' && f.data) {
          const d = f.data;
          const pos = d.position ?? {};
          upsert({
            norad_id: d.norad_id,
            name: d.name ?? null,
            lat: pos.lat_deg ?? 0,
            lon: pos.lon_deg ?? 0,
            alt: pos.alt_km ?? 0,
            v: d.speed_km_s ?? 0,
            cell: d.healpix_cell ?? 0,
            t: d.sampled_at ? new Date(d.sampled_at).getTime() : f.ts,
          });
        }
        // passes / alerts / subscribed / ping frames are accepted silently here;
        // Stage 2 PassesPage + AlertsPage subscribe directly to the store/events.
      });

      const closeHandler = () => {
        setConnected(false);
        if (stopRef.current) return;
        const delay = Math.min(30_000, backoffRef.current);
        backoffRef.current = Math.min(30_000, backoffRef.current * 2);
        setTimeout(open, delay);
      };
      ws.addEventListener('close', closeHandler);
      ws.addEventListener('error', () => {
        try { ws.close(); } catch { /* ignore */ }
      });
    };

    open();
    return () => {
      stopRef.current = true;
      wsRef.current?.close();
    };
  }, [upsert, setConnected]);
}
