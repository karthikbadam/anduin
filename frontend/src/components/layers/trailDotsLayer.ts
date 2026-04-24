import { ScatterplotLayer } from '@deck.gl/layers';

/** Per-sat history: [lon, lat, t_ms] triples, newest last. */
export type TrailMap = Map<string, Array<[number, number, number]>>;

// Quadratic falloff over 5 minutes.
const MAX_TRAIL_AGE_MS = 5 * 60 * 1000;

interface Dot {
  lon: number;
  lat: number;
  age_ms: number;
}

export function createTrailDotsLayer(
  trails: TrailMap,
  version: number,
  isDark: boolean,
) {
  const rgb: [number, number, number] = isDark ? [255, 255, 255] : [24, 24, 27];

  const now = Date.now();
  const data: Dot[] = [];
  trails.forEach((samples) => {
    // Drop the newest — satellitePointsLayer draws that as the bright head.
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
      return 0.8 + 1.4 * n * n;
    },
    radiusUnits: 'pixels',
    getFillColor: (d) => {
      const n = Math.max(0, 1 - d.age_ms / MAX_TRAIL_AGE_MS);
      return [rgb[0], rgb[1], rgb[2], Math.round(220 * n * n)];
    },
    stroked: false,
    updateTriggers: {
      getRadius: version,
      getFillColor: [version, isDark],
      getPosition: version,
    },
  });
}
