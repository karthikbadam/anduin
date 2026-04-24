import { api } from './client';
import type { ActiveResponse, Satellite } from './types';

export async function fetchActive(limit = 50): Promise<ActiveResponse> {
  const r = await api.get<ActiveResponse>('/satellites/active', { params: { limit } });
  return r.data;
}

export async function fetchSatellite(noradId: string): Promise<Satellite> {
  const r = await api.get<Satellite>(`/satellites/${noradId}`);
  return r.data;
}
