import { Box } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchActive } from '../api/satellites';
import { Globe } from '../components/Globe';
import { SatelliteList } from '../components/SatelliteList';
import { StatusBar } from '../components/StatusBar';
import {
  type HeadDot,
  createSatellitePointsLayer,
} from '../components/layers/satellitePointsLayer';
import { createTrailDotsLayer, type TrailMap } from '../components/layers/trailDotsLayer';

// At 5 s polling, 120 samples ≈ 10 minutes of history per sat.
const MAX_TRAIL_POINTS = 120;
// Drop sats from the client buffer entirely when they've been silent this long.
const EVICT_AFTER_MS = 10 * 60 * 1000;

export function DashboardPage() {
  const { data, isFetching, isError } = useQuery({
    queryKey: ['satellites', 'active'],
    queryFn: () => fetchActive(500),
    refetchInterval: 5_000,
    refetchOnWindowFocus: false,
  });

  const items = data?.items ?? [];

  // Client-side trail buffer. Ref for stability, counter for layer invalidation.
  // We render everything from this buffer — the poll response only feeds it.
  // That removes flicker when a sat drops out of the top-500 response.
  const trailsRef = useRef<TrailMap>(new Map());
  const [trailsVersion, setTrailsVersion] = useState(0);

  useEffect(() => {
    if (!data) return;
    const trails = trailsRef.current;
    for (const s of data.items) {
      if (!s.position) continue;
      const { lon, lat, t } = s.position;
      const cur = trails.get(s.norad_id) ?? [];
      const tail = cur[cur.length - 1];
      if (tail && tail[2] === t) continue; // same sample as last tick
      cur.push([lon, lat, t]);
      if (cur.length > MAX_TRAIL_POINTS) cur.splice(0, cur.length - MAX_TRAIL_POINTS);
      trails.set(s.norad_id, cur);
    }

    // Evict sats we haven't heard from in EVICT_AFTER_MS so the buffer doesn't grow unboundedly.
    const cutoff = Date.now() - EVICT_AFTER_MS;
    for (const [id, samples] of trails) {
      const last = samples[samples.length - 1];
      if (!last || last[2] < cutoff) trails.delete(id);
    }

    setTrailsVersion((v) => v + 1);
  }, [data]);

  // Derive head dots from the trail buffer, not from the poll response.
  const heads = useMemo<HeadDot[]>(() => {
    const now = Date.now();
    const out: HeadDot[] = [];
    trailsRef.current.forEach((samples, norad_id) => {
      const last = samples[samples.length - 1];
      if (!last) return;
      const [lon, lat, t] = last;
      out.push({ norad_id, lon, lat, age_ms: now - t });
    });
    return out;
  }, [trailsVersion]);

  const layers = useMemo(
    () => [
      createTrailDotsLayer(trailsRef.current, trailsVersion),
      createSatellitePointsLayer(heads, trailsVersion),
    ],
    [heads, trailsVersion],
  );

  return (
    <Box position="fixed" inset={0}>
      <Globe layers={layers} />
      <StatusBar activeCount={items.length} pollOk={!isError && !isFetching} />
      <SatelliteList items={items} />
    </Box>
  );
}
