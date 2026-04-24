import { Box, Heading, Stack, Text } from '@chakra-ui/react';
import type { ActiveSatellite } from '../api/types';

export function SatelliteList({ items }: { items: ActiveSatellite[] }) {
  return (
    <Box
      position="absolute"
      top="52px"
      right={4}
      bottom={4}
      w="280px"
      bg="rgba(20, 20, 24, 0.85)"
      border="1px solid"
      borderColor="bg.border"
      backdropFilter="blur(12px)"
      rounded="md"
      p={3}
      overflowY="auto"
      sx={{
        '&::-webkit-scrollbar': { width: '6px' },
        '&::-webkit-scrollbar-thumb': { background: '#27272a', borderRadius: '3px' },
      }}
    >
      <Heading
        size="xs"
        color="fg.muted"
        mb={3}
        textTransform="uppercase"
        letterSpacing="widest"
        fontSize="10px"
      >
        active satellites
      </Heading>
      <Stack spacing={1.5}>
        {items.map((s) => (
          <Box
            key={s.norad_id}
            py={1.5}
            px={2}
            rounded="sm"
            _hover={{ bg: 'whiteAlpha.50' }}
            transition="background 120ms"
          >
            <Text fontSize="sm" fontWeight="medium" color="fg.primary" fontFamily="mono">
              {s.norad_id}
            </Text>
            {s.position && (
              <Text fontSize="xs" color="fg.muted" fontFamily="mono">
                {s.position.lat.toFixed(2)}°, {s.position.lon.toFixed(2)}° ·{' '}
                {s.position.alt.toFixed(0)} km
              </Text>
            )}
            <Text fontSize="xs" color="fg.subtle">
              {new Date(s.last_seen_ms).toLocaleTimeString()}
            </Text>
          </Box>
        ))}
        {items.length === 0 && (
          <Text fontSize="xs" color="fg.subtle">
            waiting for data…
          </Text>
        )}
      </Stack>
    </Box>
  );
}
