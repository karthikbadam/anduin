import { api } from './client';

export interface HotCellFeature {
  type: 'Feature';
  geometry: { type: 'Polygon'; coordinates: [number, number][][] };
  properties: { cell: number; n_sats: number };
}

export interface HotCellsResponse {
  type: 'FeatureCollection';
  features: HotCellFeature[];
  window_end_ms: number | null;
  count?: number;
}

export async function fetchHotCells(limit = 400): Promise<HotCellsResponse> {
  const r = await api.get<HotCellsResponse>('/zones/hot', { params: { limit } });
  return r.data;
}
