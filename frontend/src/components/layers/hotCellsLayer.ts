import { PolygonLayer } from '@deck.gl/layers';
import type { HotCellFeature } from '../../api/zones';

/** HEALPix heatmap — polygon per cell, alpha scales with n_sats density.
 * Warm amber works on both dark and light basemaps. */
export function createHotCellsLayer(features: HotCellFeature[], isDark: boolean) {
  const max = features.reduce((m, f) => Math.max(m, f.properties.n_sats), 1);

  // Amber color, slightly different tint per mode so it reads against each basemap.
  const rgb: [number, number, number] = isDark ? [245, 158, 11] : [217, 119, 6];

  return new PolygonLayer<HotCellFeature>({
    id: 'hot-cells',
    data: features,
    getPolygon: (f) => f.geometry.coordinates[0],
    getFillColor: (f) => {
      const n = f.properties.n_sats / max;
      // Quadratic so only the densest cells really glow.
      return [rgb[0], rgb[1], rgb[2], Math.round(140 * n * n)];
    },
    getLineColor: [0, 0, 0, 0],
    filled: true,
    stroked: false,
    pickable: false,
    wrapLongitude: true,
    updateTriggers: {
      getFillColor: isDark,
    },
  });
}
