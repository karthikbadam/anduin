import { Box, Heading, Stack, Text } from '@chakra-ui/react';
import type { LivePosition } from '../ws/store';

export function SatelliteList({ items }: { items: LivePosition[] }) {
  return (
    <Box
      position="absolute"
      top="52px"
      right={4}
      bottom={4}
      w="280px"
      bg="bg.panel"
      border="1px solid"
      borderColor="bg.border"
      backdropFilter="blur(12px)"
      rounded="md"
      p={3}
      overflowY="auto"
      opacity={0.94}
      sx={{
        '&::-webkit-scrollbar': { width: '6px' },
        '&::-webkit-scrollbar-thumb': { background: 'var(--chakra-colors-bg-border)', borderRadius: '3px' },
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
            _hover={{ bg: 'bg.border' }}
            transition="background 120ms"
          >
            <Text fontSize="sm" fontWeight="medium" color="fg.primary" fontFamily="mono">
              {s.norad_id}
            </Text>
            <Text fontSize="xs" color="fg.muted" fontFamily="mono">
              {s.lat.toFixed(2)}°, {s.lon.toFixed(2)}° · {s.alt.toFixed(0)} km
            </Text>
            <Text fontSize="xs" color="fg.subtle">
              {new Date(s.t).toLocaleTimeString()}
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
