import { DeckGL } from '@deck.gl/react';
import type { Layer } from '@deck.gl/core';
import { Map } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

const INITIAL_VIEW = { longitude: 0, latitude: 20, zoom: 1.5, pitch: 0, bearing: 0 };

// Free CARTO dark basemap — no API key required, attribution included in the style.
const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

export function Globe({ layers }: { layers: Layer[] }) {
  return (
    <DeckGL initialViewState={INITIAL_VIEW} controller layers={layers}>
      <Map mapStyle={MAP_STYLE} reuseMaps />
    </DeckGL>
  );
}
