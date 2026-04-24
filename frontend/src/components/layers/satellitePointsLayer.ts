import { ScatterplotLayer } from '@deck.gl/layers';

/** Head (current-position) dot per sat, keyed by staleness so sats that drop
 * out of the poll's top-N don't flicker — they just fade out over ~2 min. */
export interface HeadDot {
  norad_id: string;
  lon: number;
  lat: number;
  age_ms: number;
}

// White-with-alpha — matches karthikbadam.com's monochrome aesthetic; reads as
// faint starlight on the dark basemap rather than a branded color.
const DOT_RGB: [number, number, number] = [255, 255, 255];

// Sats that haven't ticked in this long are considered gone.
const HEAD_MAX_AGE_MS = 90 * 1000;

export function createSatellitePointsLayer(heads: HeadDot[], version: number) {
  return new ScatterplotLayer<HeadDot>({
    id: 'satellite-points',
    data: heads,
    pickable: true,
    getPosition: (d) => [d.lon, d.lat, 0],
    getRadius: (d) => {
      // Shrink quadratically with age: 5 px fresh → 2 px stale.
      const n = Math.max(0, 1 - d.age_ms / HEAD_MAX_AGE_MS);
      return 2 + 3 * n * n;
    },
    radiusUnits: 'pixels',
    getFillColor: (d) => {
      // Quadratic fade: head stays bright while fresh, then drops off
      // steeply so stale dots vanish rather than linger dimly.
      const n = Math.max(0, 1 - d.age_ms / HEAD_MAX_AGE_MS);
      return [DOT_RGB[0], DOT_RGB[1], DOT_RGB[2], Math.round(240 * n * n)];
    },
    getLineColor: [0, 0, 0, 180],
    lineWidthUnits: 'pixels',
    lineWidthMinPixels: 0.5,
    updateTriggers: {
      getPosition: version,
      getFillColor: version,
      getRadius: version,
    },
  });
}
