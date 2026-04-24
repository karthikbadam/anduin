import {
  Badge,
  Box,
  Button,
  HStack,
  Heading,
  Input,
  Link,
  Stack,
  Table,
  TableContainer,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tr,
} from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { fetchPasses, registerObserver } from '../api/passes';
import { useObserverLocation } from '../hooks/useObserverLocation';

function kindLabel(k: string): { label: string; color: string } {
  switch (k) {
    case 'rise_0': return { label: 'rise', color: 'accent.green' };
    case 'rise_10': return { label: 'rise 10°', color: 'accent.green' };
    case 'culmination': return { label: 'peak', color: 'accent.amber' };
    case 'set_10': return { label: 'set 10°', color: 'fg.muted' };
    case 'set_0': return { label: 'set', color: 'fg.muted' };
    default: return { label: k, color: 'fg.muted' };
  }
}

export function PassesPage() {
  const { observer, setObserver, requestGeolocation, error } = useObserverLocation();
  const [latDraft, setLatDraft] = useState(observer?.lat?.toString() ?? '');
  const [lonDraft, setLonDraft] = useState(observer?.lon?.toString() ?? '');

  useEffect(() => {
    setLatDraft(observer?.lat?.toString() ?? '');
    setLonDraft(observer?.lon?.toString() ?? '');
  }, [observer]);

  const { data, isLoading, isError } = useQuery({
    queryKey: ['passes', observer?.lat, observer?.lon],
    queryFn: () => fetchPasses(observer!.lat, observer!.lon, 24),
    enabled: !!observer,
    refetchInterval: 15_000,
  });

  // Register observer on first set so pass-worker starts emitting.
  useEffect(() => {
    if (observer) {
      registerObserver(observer.lat, observer.lon).catch(() => { /* silent */ });
    }
  }, [observer]);

  const applyManual = () => {
    const lat = parseFloat(latDraft);
    const lon = parseFloat(lonDraft);
    if (Number.isFinite(lat) && Number.isFinite(lon)) {
      setObserver({ lat, lon });
    }
  };

  return (
    <Box minH="100vh" bg="bg.body" color="fg.primary" p={{ base: 4, md: 8 }}>
      <Box maxW="960px" mx="auto">
        <HStack justify="space-between" mb={6}>
          <Heading size="md" letterSpacing="tight">satellite passes</Heading>
          <Link as={RouterLink} to="/" color="fg.muted" fontSize="sm">← map</Link>
        </HStack>

        <Box bg="bg.panel" border="1px solid" borderColor="bg.border" rounded="md" p={4} mb={6}>
          <Heading size="xs" color="fg.muted" mb={3} textTransform="uppercase" letterSpacing="widest" fontSize="10px">
            observer location
          </Heading>
          <Stack direction={{ base: 'column', md: 'row' }} spacing={3} align={{ md: 'flex-end' }}>
            <Box>
              <Text fontSize="xs" color="fg.subtle" mb={1}>latitude</Text>
              <Input size="sm" fontFamily="mono" bg="bg.body" borderColor="bg.border"
                     value={latDraft} onChange={(e) => setLatDraft(e.target.value)} w="120px" />
            </Box>
            <Box>
              <Text fontSize="xs" color="fg.subtle" mb={1}>longitude</Text>
              <Input size="sm" fontFamily="mono" bg="bg.body" borderColor="bg.border"
                     value={lonDraft} onChange={(e) => setLonDraft(e.target.value)} w="120px" />
            </Box>
            <Button size="sm" onClick={applyManual} colorScheme="gray">apply</Button>
            <Button size="sm" variant="ghost" onClick={requestGeolocation}>use my location</Button>
            {error && <Text fontSize="xs" color="accent.red">{error}</Text>}
          </Stack>
          {observer && (
            <Text fontSize="xs" color="fg.subtle" mt={3} fontFamily="mono">
              observer_id {data?.observer_id ?? '…'} · {observer.lat.toFixed(4)}°, {observer.lon.toFixed(4)}°
            </Text>
          )}
        </Box>

        {!observer && (
          <Text fontSize="sm" color="fg.muted">Enter a lat/lon or use your geolocation to start predicting passes.</Text>
        )}
        {observer && isLoading && (
          <Text fontSize="sm" color="fg.muted">loading passes…</Text>
        )}
        {observer && isError && (
          <Text fontSize="sm" color="accent.red">failed to load passes</Text>
        )}
        {observer && data && data.items.length === 0 && (
          <Text fontSize="sm" color="fg.muted">
            no pass events yet for the next {data.window_hours}h. pass-worker computes as satellites are propagated — events typically start appearing within a minute.
          </Text>
        )}
        {observer && data && data.items.length > 0 && (
          <TableContainer bg="bg.panel" border="1px solid" borderColor="bg.border" rounded="md">
            <Table size="sm" variant="simple">
              <Thead>
                <Tr>
                  <Th color="fg.muted">norad</Th>
                  <Th color="fg.muted">event</Th>
                  <Th color="fg.muted">local time</Th>
                  <Th color="fg.muted" isNumeric>elev°</Th>
                  <Th color="fg.muted" isNumeric>az°</Th>
                  <Th color="fg.muted" isNumeric>range km</Th>
                </Tr>
              </Thead>
              <Tbody>
                {data.items.map((p, i) => {
                  const k = kindLabel(p.event_kind);
                  return (
                    <Tr key={`${p.norad_id}-${p.event_time}-${i}`}>
                      <Td fontFamily="mono">{p.norad_id}</Td>
                      <Td><Badge colorScheme="gray" color={k.color} bg="transparent" px={0}>{k.label}</Badge></Td>
                      <Td fontFamily="mono">{new Date(p.event_time).toLocaleString()}</Td>
                      <Td isNumeric fontFamily="mono">{p.elevation_deg.toFixed(1)}</Td>
                      <Td isNumeric fontFamily="mono">{p.azimuth_deg.toFixed(1)}</Td>
                      <Td isNumeric fontFamily="mono">{p.range_km.toFixed(0)}</Td>
                    </Tr>
                  );
                })}
              </Tbody>
            </Table>
          </TableContainer>
        )}
      </Box>
    </Box>
  );
}
