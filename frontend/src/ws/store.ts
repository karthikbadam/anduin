import { create } from 'zustand';

export interface LivePosition {
  norad_id: string;
  name: string | null;
  lat: number;
  lon: number;
  alt: number;
  v: number;
  cell: number;
  t: number; // sampled_at ms
}

interface LiveStore {
  positions: Map<string, LivePosition>;
  version: number;       // bumped on every mutation to trigger React re-renders
  lastFrameAt: number;   // ms — for StatusBar staleness indicator
  connected: boolean;
  upsertPosition: (p: LivePosition) => void;
  setConnected: (c: boolean) => void;
}

export const useLiveStore = create<LiveStore>((set, get) => ({
  positions: new Map(),
  version: 0,
  lastFrameAt: 0,
  connected: false,
  upsertPosition: (p) => {
    const { positions, version } = get();
    positions.set(p.norad_id, p);
    set({ positions, version: version + 1, lastFrameAt: Date.now() });
  },
  setConnected: (c) => set({ connected: c }),
}));
