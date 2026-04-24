import { Box, HStack, Input, Text } from '@chakra-ui/react';
import { useState } from 'react';
import { getApiKey, setApiKey } from '../api/client';

export function StatusBar({ activeCount, pollOk }: { activeCount: number; pollOk: boolean }) {
  const [keyDraft, setKeyDraft] = useState(getApiKey());

  return (
    <Box
      position="absolute"
      top={0}
      left={0}
      right={0}
      zIndex={10}
      bg="rgba(10, 10, 11, 0.8)"
      borderBottom="1px solid"
      borderColor="bg.border"
      backdropFilter="blur(12px)"
      px={4}
      py={2.5}
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
            bg={pollOk ? 'accent.green' : 'accent.amber'}
            boxShadow={pollOk ? '0 0 6px #22c55e' : '0 0 6px #f59e0b'}
          />
          <Text fontSize="xs" color="fg.muted">
            {pollOk ? 'connected' : 'stalled'}
          </Text>
        </HStack>
        <Text fontSize="xs" color="fg.subtle">
          · {activeCount} active
        </Text>
        <HStack ml="auto" spacing={2}>
          <Text fontSize="xs" color="fg.subtle">
            api key
          </Text>
          <Input
            size="xs"
            w="240px"
            variant="filled"
            bg="bg.panel"
            borderColor="bg.border"
            color="fg.primary"
            _hover={{ bg: 'bg.panel' }}
            _focus={{ bg: 'bg.panel', borderColor: 'fg.muted' }}
            value={keyDraft}
            onChange={(e) => setKeyDraft(e.target.value)}
            onBlur={() => setApiKey(keyDraft)}
          />
        </HStack>
      </HStack>
    </Box>
  );
}
