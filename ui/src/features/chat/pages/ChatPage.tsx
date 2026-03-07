import { useState, useRef, useEffect } from 'react';
import {
  Title,
  Stack,
  Group,
  Paper,
  Text,
  TextInput,
  Button,
  ActionIcon,
  Loader,
  Center,
  ScrollArea,
  Box,
  Badge,
  Select,
} from '@mantine/core';
import { IconSend, IconPlus, IconTrash } from '@tabler/icons-react';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import {
  useChatListConversations,
  useChatCreateConversation,
  useChatGetConversation,
  useChatSendMessage,
  useChatDeleteConversation,
} from '@/generated/api/chat/chat';
import { useModelsListModels } from '@/generated/api/models/models';
import { EmptyState } from '@/shared/components/EmptyState';

interface Message {
  message_id: string;
  role: string;
  content: string;
  display_name: string | null;
  timestamp: string;
}

interface Conversation {
  conversation_id: string;
  display_name: string | null;
  created_at: string;
  model_id: string | null;
  messages: Message[];
}

export function Component() {
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [newMessage, setNewMessage] = useState('');
  const [newConvMessage, setNewConvMessage] = useState('');
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const { data: modelsResp } = useModelsListModels();
  const models = (modelsResp?.data ?? []) as Array<{ model_id: string; name: string; model_name: string; provider_name: string; is_default: boolean }>;

  // Auto-select default model
  useEffect(() => {
    if (!selectedModelId && models.length > 0) {
      const defaultModel = models.find((m) => m.is_default);
      setSelectedModelId(defaultModel?.model_id ?? models[0].model_id);
    }
  }, [models, selectedModelId]);

  const { data: convsResp, isLoading } = useChatListConversations();
  const { data: convResp } = useChatGetConversation(activeConvId ?? '', {
    query: {
      enabled: !!activeConvId,
      refetchInterval: 3000,
    },
  });
  const createMutation = useChatCreateConversation();
  const sendMutation = useChatSendMessage();
  const deleteMutation = useChatDeleteConversation();

  const conversations = (convsResp?.data ?? []) as Conversation[];
  const activeConversation = convResp?.data as Conversation | undefined;
  const messages = activeConversation?.messages ?? [];

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length]);

  const handleNewConversation = () => {
    if (!newConvMessage.trim()) return;
    createMutation.mutate(
      {
        data: {
          user_id: 'ui-user',
          display_name: 'You',
          message: newConvMessage,
          model_id: selectedModelId,
        },
      },
      {
        onSuccess: (resp) => {
          const conv = resp?.data as Conversation | undefined;
          if (conv) {
            setActiveConvId(conv.conversation_id);
          }
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/chat/conversations'] });
          setNewConvMessage('');
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to start conversation', color: 'red' });
        },
      },
    );
  };

  const handleSend = () => {
    if (!newMessage.trim() || !activeConvId) return;
    sendMutation.mutate(
      {
        conversationId: activeConvId,
        data: {
          user_id: 'ui-user',
          display_name: 'You',
          message: newMessage,
        },
      },
      {
        onSuccess: () => {
          void queryClient.invalidateQueries({ queryKey: [`/api/v1/chat/conversations/${activeConvId}`] });
          setNewMessage('');
        },
        onError: () => {
          notifications.show({ title: 'Error', message: 'Failed to send message', color: 'red' });
        },
      },
    );
  };

  const handleDelete = (convId: string) => {
    deleteMutation.mutate(
      { conversationId: convId },
      {
        onSuccess: () => {
          if (activeConvId === convId) setActiveConvId(null);
          void queryClient.invalidateQueries({ queryKey: ['/api/v1/chat/conversations'] });
        },
      },
    );
  };

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  return (
    <Stack gap="md" h="calc(100vh - 140px)">
      <Title order={2}>Chat</Title>
      <Group align="flex-start" gap="md" style={{ flex: 1, minHeight: 0 }}>
        {/* Sidebar */}
        <Paper withBorder p="sm" w={280} h="100%" style={{ display: 'flex', flexDirection: 'column' }}>
          <Group justify="space-between" mb="sm">
            <Text fw={600} size="sm">Conversations</Text>
          </Group>

          {/* Model selector */}
          {models.length > 0 && (
            <Select
              size="xs"
              mb="xs"
              placeholder="Select model"
              value={selectedModelId}
              onChange={setSelectedModelId}
              data={models.map((m) => ({
                value: m.model_id,
                label: `${m.name} (${m.provider_name})`,
              }))}
            />
          )}

          {/* New conversation input */}
          <Group gap="xs" mb="sm">
            <TextInput
              placeholder="Start a conversation..."
              size="xs"
              style={{ flex: 1 }}
              value={newConvMessage}
              onChange={(e) => setNewConvMessage(e.currentTarget.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleNewConversation()}
            />
            <ActionIcon
              size="sm"
              variant="filled"
              onClick={handleNewConversation}
              loading={createMutation.isPending}
            >
              <IconPlus size={14} />
            </ActionIcon>
          </Group>

          <ScrollArea style={{ flex: 1 }}>
            <Stack gap={4}>
              {conversations.length === 0 ? (
                <Text size="xs" c="dimmed" ta="center" py="md">No conversations</Text>
              ) : (
                conversations.map((c) => (
                  <Group
                    key={c.conversation_id}
                    gap="xs"
                    p="xs"
                    style={{
                      borderRadius: 6,
                      cursor: 'pointer',
                      background: activeConvId === c.conversation_id ? 'var(--mantine-color-dark-5)' : undefined,
                    }}
                    onClick={() => setActiveConvId(c.conversation_id)}
                  >
                    <Box style={{ flex: 1, minWidth: 0 }}>
                      <Text size="xs" truncate>
                        {c.messages?.[0]?.content?.slice(0, 40) ?? 'New conversation'}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {new Date(c.created_at).toLocaleString()}
                      </Text>
                    </Box>
                    <ActionIcon
                      size="xs"
                      color="red"
                      variant="subtle"
                      onClick={(e) => { e.stopPropagation(); handleDelete(c.conversation_id); }}
                    >
                      <IconTrash size={12} />
                    </ActionIcon>
                  </Group>
                ))
              )}
            </Stack>
          </ScrollArea>
        </Paper>

        {/* Chat area */}
        <Paper withBorder p="md" style={{ flex: 1, display: 'flex', flexDirection: 'column', height: '100%' }}>
          {!activeConvId ? (
            <Center style={{ flex: 1 }}>
              <EmptyState
                title="No conversation selected"
                description="Start a new conversation or select one from the sidebar"
              />
            </Center>
          ) : (
            <>
              {activeConversation?.model_id && (
                <Group gap="xs" mb="xs">
                  <Text size="xs" c="dimmed">Model:</Text>
                  <Badge size="xs" variant="light">
                    {models.find((m) => m.model_id === activeConversation.model_id)?.name ?? activeConversation.model_id}
                  </Badge>
                </Group>
              )}
              <ScrollArea style={{ flex: 1 }} viewportRef={scrollRef}>
                <Stack gap="md" p="xs">
                  {messages.map((m) => (
                    <Group
                      key={m.message_id}
                      justify={m.role === 'user' ? 'flex-end' : 'flex-start'}
                      align="flex-end"
                      gap="xs"
                    >
                      <Paper
                        p="sm"
                        radius="md"
                        maw="70%"
                        style={{
                          background: m.role === 'user'
                            ? 'var(--mantine-color-blue-filled)'
                            : 'var(--mantine-color-dark-5)',
                        }}
                      >
                        <Group gap="xs" mb={4}>
                          <Badge size="xs" variant="light">
                            {m.display_name ?? m.role}
                          </Badge>
                          <Text size="xs" c="dimmed">
                            {new Date(m.timestamp).toLocaleTimeString()}
                          </Text>
                        </Group>
                        <Text
                          size="sm"
                          style={{ whiteSpace: 'pre-wrap' }}
                          c={m.role === 'user' ? 'white' : undefined}
                        >
                          {m.content}
                        </Text>
                      </Paper>
                    </Group>
                  ))}
                </Stack>
              </ScrollArea>

              <Group gap="xs" mt="md">
                <TextInput
                  placeholder="Type a message..."
                  style={{ flex: 1 }}
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.currentTarget.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                />
                <ActionIcon
                  size="lg"
                  variant="filled"
                  onClick={handleSend}
                  loading={sendMutation.isPending}
                >
                  <IconSend size={18} />
                </ActionIcon>
              </Group>
            </>
          )}
        </Paper>
      </Group>
    </Stack>
  );
}
