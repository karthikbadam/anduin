import { api } from './client';

export interface PassEvent {
  norad_id: string;
  name: string | null;
  event_kind: 'rise_0' | 'rise_10' | 'culmination' | 'set_10' | 'set_0';
  event_time: string;
  elevation_deg: number;
  azimuth_deg: number;
  range_km: number;
}

export interface PassesResponse {
  observer_id: string;
  items: PassEvent[];
  count: number;
  window_hours: number;
}

export async function fetchPasses(
  lat: number,
  lon: number,
  hours: number = 24,
): Promise<PassesResponse> {
  const r = await api.get<PassesResponse>('/passes', { params: { lat, lon, hours } });
  return r.data;
}

export async function registerObserver(lat: number, lon: number, alt_km: number = 0) {
  await api.post('/observers', { lat, lon, alt_km });
}
