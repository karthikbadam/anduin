export interface PositionSample {
  t: number;        // ms
  lat: number;
  lon: number;
  alt: number;
  v: number;
  cell: number;
}

export interface ActiveSatellite {
  norad_id: string;
  last_seen_ms: number;
  last_seen: string;
  position: PositionSample | null;
}

export interface ActiveResponse {
  items: ActiveSatellite[];
  count: number;
}

export interface Satellite {
  norad_id: string;
  name: string | null;
  classification: string | null;
  last_tle_epoch: string | null;
  created_at: string;
  updated_at: string;
}
