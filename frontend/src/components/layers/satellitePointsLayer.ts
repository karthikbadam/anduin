import { ScatterplotLayer } from '@deck.gl/layers';

/** Head (current-position) dot per sat, keyed by staleness so sats that drop
 * out of the poll's top-N don't flicker — they just fade out over ~90s. */
export interface HeadDot {
  norad_id: string;
  lon: number;
  lat: number;
  age_ms: number;
}

// Sats silent for longer than this are rendered fully transparent.
const HEAD_MAX_AGE_MS = 90 * 1000;

export function createSatellitePointsLayer(
  heads: HeadDot[],
  version: number,
  isDark: boolean,
) {
  // White dots look right on dark basemap; a near-black slate works on the
  // light basemap and keeps the monochrome aesthetic.
  const rgb: [number, number, number] = isDark ? [255, 255, 255] : [24, 24, 27];

  return new ScatterplotLayer<HeadDot>({
    id: 'satellite-points',
    data: heads,
    pickable: true,
    getPosition: (d) => [d.lon, d.lat, 0],
    getRadius: (d) => {
      const n = Math.max(0, 1 - d.age_ms / HEAD_MAX_AGE_MS);
      return 2 + 3 * n * n; // 5 px fresh → 2 px stale
    },
    radiusUnits: 'pixels',
    getFillColor: (d) => {
      const n = Math.max(0, 1 - d.age_ms / HEAD_MAX_AGE_MS);
      return [rgb[0], rgb[1], rgb[2], Math.round(240 * n * n)];
    },
    getLineColor: isDark ? [0, 0, 0, 180] : [255, 255, 255, 180],
    lineWidthUnits: 'pixels',
    lineWidthMinPixels: 0.5,
    updateTriggers: {
      getPosition: version,
      getFillColor: [version, isDark],
      getRadius: version,
      getLineColor: isDark,
    },
  });
}
