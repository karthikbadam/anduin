import { Box, HStack, IconButton, Input, Link, Text, useColorMode } from '@chakra-ui/react';
import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { getApiKey, setApiKey } from '../api/client';

// Small inline SVGs — avoids pulling in an icon dep.
const SunIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
  </svg>
);
const MoonIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
       strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
  </svg>
);

export function StatusBar({ activeCount, connected }: { activeCount: number; connected: boolean }) {
  const [keyDraft, setKeyDraft] = useState(getApiKey());
  const { colorMode, toggleColorMode } = useColorMode();

  return (
    <Box
      position="absolute"
      top={0}
      left={0}
      right={0}
      zIndex={10}
      bg="bg.panel"
      borderBottom="1px solid"
      borderColor="bg.border"
      backdropFilter="blur(12px)"
      px={4}
      py={2.5}
      opacity={0.94}
    >
      <HStack spacing={4} align="center">
        <Text fontWeight="semibold" color="fg.primary" letterSpacing="tight">
          anduin
        </Text>
        <HStack spacing={2} align="center">
          <Box
            w="6px"
            h="6px"
            rounded="full"
            bg={connected ? 'accent.green' : 'accent.amber'}
          />
          <Text fontSize="xs" color="fg.muted">
            {connected ? 'streaming' : 'disconnected'}
          </Text>
        </HStack>
        <Text fontSize="xs" color="fg.subtle">
          · {activeCount} active
        </Text>
        <Link as={RouterLink} to="/passes" fontSize="xs" color="fg.muted"
              _hover={{ color: 'fg.primary' }}>
          passes →
        </Link>
        <HStack ml="auto" spacing={2}>
          <Text fontSize="xs" color="fg.subtle">
            api key
          </Text>
          <Input
            size="xs"
            w="240px"
            variant="filled"
            bg="bg.body"
            borderColor="bg.border"
            color="fg.primary"
            _hover={{ bg: 'bg.body' }}
            _focus={{ bg: 'bg.body', borderColor: 'fg.muted' }}
            value={keyDraft}
            onChange={(e) => setKeyDraft(e.target.value)}
            onBlur={() => setApiKey(keyDraft)}
          />
          <IconButton
            aria-label="toggle color mode"
            onClick={toggleColorMode}
            size="xs"
            variant="ghost"
            color="fg.muted"
            _hover={{ color: 'fg.primary', bg: 'bg.border' }}
            icon={colorMode === 'dark' ? <SunIcon /> : <MoonIcon />}
          />
        </HStack>
      </HStack>
    </Box>
  );
}
