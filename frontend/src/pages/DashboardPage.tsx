import { Box, useColorMode } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useMemo, useRef, useState } from 'react';
import { fetchHotCells } from '../api/zones';
import { Globe } from '../components/Globe';
import { SatelliteList } from '../components/SatelliteList';
import { StatusBar } from '../components/StatusBar';
import { createHotCellsLayer } from '../components/layers/hotCellsLayer';
import {
  type HeadDot,
  createSatellitePointsLayer,
} from '../components/layers/satellitePointsLayer';
import { createTrailDotsLayer, type TrailMap } from '../components/layers/trailDotsLayer';
import { useLiveStream } from '../ws/useLiveStream';
import { useLiveStore } from '../ws/store';

const MAX_TRAIL_POINTS = 120;
const EVICT_AFTER_MS = 10 * 60 * 1000;

export function DashboardPage() {
  useLiveStream(); // opens the singleton WebSocket

  const { colorMode } = useColorMode();
  const isDark = colorMode === 'dark';

  const positions = useLiveStore((s) => s.positions);
  const storeVersion = useLiveStore((s) => s.version);
  const connected = useLiveStore((s) => s.connected);

  // Trail buffer keyed by norad_id. Ref for stability, counter for layer updates.
  const trailsRef = useRef<TrailMap>(new Map());
  const [trailsVersion, setTrailsVersion] = useState(0);

  // On every store mutation, append each sat's latest sample to its trail.
  useEffect(() => {
    const trails = trailsRef.current;
    positions.forEach((p, norad_id) => {
      const cur = trails.get(norad_id) ?? [];
      const tail = cur[cur.length - 1];
      if (tail && tail[2] === p.t) return; // same sample as last tick
      cur.push([p.lon, p.lat, p.t]);
      if (cur.length > MAX_TRAIL_POINTS) cur.splice(0, cur.length - MAX_TRAIL_POINTS);
      trails.set(norad_id, cur);
    });
    const cutoff = Date.now() - EVICT_AFTER_MS;
    for (const [id, samples] of trails) {
      const last = samples[samples.length - 1];
      if (!last || last[2] < cutoff) trails.delete(id);
    }
    setTrailsVersion((v) => v + 1);
  }, [storeVersion, positions]);

  // Head dots derived from the trail buffer's tail per sat.
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

  // Hot-cells heatmap — polled every 30 s; Flink writes new windows once a minute.
  const { data: hotCells } = useQuery({
    queryKey: ['zones', 'hot'],
    queryFn: () => fetchHotCells(400),
    refetchInterval: 30_000,
    refetchOnWindowFocus: false,
  });

  const layers = useMemo(
    () => [
      // Hot cells rendered below everything else so dots sit on top.
      createHotCellsLayer(hotCells?.features ?? [], isDark),
      createTrailDotsLayer(trailsRef.current, trailsVersion, isDark),
      createSatellitePointsLayer(heads, trailsVersion, isDark),
    ],
    [heads, trailsVersion, isDark, hotCells],
  );

  // Sidebar shows latest 50 by age (still useful as a "recent activity" feed).
  const sidebarItems = useMemo(() => {
    const all = Array.from(positions.values());
    return all.sort((a, b) => b.t - a.t).slice(0, 50);
  }, [storeVersion, positions]);

  return (
    <Box position="fixed" inset={0} bg="bg.body">
      <Globe layers={layers} />
      <StatusBar activeCount={heads.length} connected={connected} />
      <SatelliteList items={sidebarItems} />
    </Box>
  );
}
