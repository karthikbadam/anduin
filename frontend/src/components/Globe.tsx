import { DeckGL } from '@deck.gl/react';
import type { Layer } from '@deck.gl/core';
import { useColorMode } from '@chakra-ui/react';
import { Map } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

const INITIAL_VIEW = { longitude: 0, latitude: 20, zoom: 1.5, pitch: 0, bearing: 0 };

// CARTO free basemaps (no API key). Dark-matter and positron are visually
// balanced siblings — swapping just the style URL on color mode change is
// enough; deck.gl layers keep rendering on top.
const DARK_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';
const LIGHT_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

export function Globe({ layers }: { layers: Layer[] }) {
  const { colorMode } = useColorMode();
  const style = colorMode === 'dark' ? DARK_STYLE : LIGHT_STYLE;
  return (
    <DeckGL initialViewState={INITIAL_VIEW} controller layers={layers}>
      {/* key on style so MapLibre rebuilds cleanly when toggling modes */}
      <Map key={style} mapStyle={style} reuseMaps />
    </DeckGL>
  );
}
