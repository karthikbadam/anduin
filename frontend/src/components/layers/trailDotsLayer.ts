import { ScatterplotLayer } from '@deck.gl/layers';

/** Per-sat history: [lon, lat, t_ms] triples, newest last. */
export type TrailMap = Map<string, Array<[number, number, number]>>;

// White-with-alpha — monochrome trail tail, matches site palette.
const DOT_RGB: [number, number, number] = [255, 255, 255];

// How old a sample must be to fade fully out. 5 min window with quadratic
// falloff: fresh dots bright, older ones fall off fast.
const MAX_TRAIL_AGE_MS = 5 * 60 * 1000;

interface Dot {
  lon: number;
  lat: number;
  age_ms: number;
}

export function createTrailDotsLayer(trails: TrailMap, version: number) {
  const now = Date.now();
  const data: Dot[] = [];
  trails.forEach((samples) => {
    // Skip the newest sample — the satellitePointsLayer draws that as the bright head.
    // Iterate reversed so oldest is first (order doesn't matter for Scatterplot,
    // but keeps the logic explicit).
    for (let i = 0; i < samples.length - 1; i++) {
      const [lon, lat, t] = samples[i];
      data.push({ lon, lat, age_ms: now - t });
    }
  });

  return new ScatterplotLayer<Dot>({
    id: 'trail-dots',
    data,
    pickable: false,
    getPosition: (d) => [d.lon, d.lat, 0],
    getRadius: (d) => {
      const n = Math.max(0, 1 - d.age_ms / MAX_TRAIL_AGE_MS);
      return 0.8 + 1.4 * n * n; // 2.2 → 0.8 px, steeper taper
    },
    radiusUnits: 'pixels',
    getFillColor: (d) => {
      // Quadratic fade: alpha = max * (1 - age/MAX)^2. Bright near head,
      // drops off fast so older dots look wispy rather than uniform.
      const n = Math.max(0, 1 - d.age_ms / MAX_TRAIL_AGE_MS);
      return [DOT_RGB[0], DOT_RGB[1], DOT_RGB[2], Math.round(220 * n * n)];
    },
    stroked: false,
    // Recompute size + color every poll so the fade visibly advances.
    updateTriggers: {
      getRadius: version,
      getFillColor: version,
      getPosition: version,
    },
  });
}
