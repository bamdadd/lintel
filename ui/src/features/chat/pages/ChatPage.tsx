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
import { IconSend, IconPlus, IconTrash, IconCopy, IconCheck } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import '../chat-markdown.css';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import {
  useChatListConversations,
  useChatCreateConversation,
  useChatGetConversation,
  useChatDeleteConversation,
} from '@/generated/api/chat/chat';
import { useModelsListModels } from '@/generated/api/models/models';
import { useProjectsListProjects } from '@/generated/api/projects/projects';
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
  project_id: string | null;
  messages: Message[];
}

function CopyBtn({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    void navigator.clipboard.writeText(content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <ActionIcon size="xs" variant="subtle" color={copied ? 'teal' : 'gray'} onClick={handleCopy} title="Copy" ml={4}>
      {copied ? <IconCheck size={12} /> : <IconCopy size={12} />}
    </ActionIcon>
  );
}

export function Component() {
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [newMessage, setNewMessage] = useState('');
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [pendingMessages, setPendingMessages] = useState<Message[]>([]);
  const [isThinking, setIsThinking] = useState(false);
  const [streamingContent, setStreamingContent] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const queryClient = useQueryClient();

  const { data: modelsResp } = useModelsListModels();
  const models = (modelsResp?.data ?? []) as Array<{ model_id: string; name: string; model_name: string; provider_name: string; is_default: boolean }>;

  const { data: projectsResp } = useProjectsListProjects();
  const projects = (projectsResp?.data ?? []) as Array<{ project_id: string; name: string; repo_ids: string[] }>;

  // Auto-select default model
  useEffect(() => {
    if (!selectedModelId && models.length > 0) {
      const defaultModel = models.find((m) => m.is_default);
      setSelectedModelId(defaultModel?.model_id ?? models[0].model_id);
    }
  }, [models, selectedModelId]);

  const { data: convsResp, isLoading } = useChatListConversations();
  const isRealConvId = !!activeConvId && !activeConvId.startsWith('new-');
  const { data: convResp } = useChatGetConversation(activeConvId ?? '', {
    query: {
      enabled: isRealConvId,
      refetchInterval: 3000,
    },
  });
  const createMutation = useChatCreateConversation();
  const deleteMutation = useChatDeleteConversation();

  const conversations = (convsResp?.data ?? []) as Conversation[];
  const activeConversation = convResp?.data as Conversation | undefined;
  const serverMessages = activeConversation?.messages ?? [];

  // Deduplicate: drop pending messages whose content already appears in server messages
  const serverContents = new Set(serverMessages.map((m) => m.content));
  const dedupedPending = pendingMessages.filter((m) => !serverContents.has(m.content));
  // Clear pending state when server catches up
  useEffect(() => {
    if (pendingMessages.length > 0 && dedupedPending.length === 0) {
      setPendingMessages([]);
    }
  }, [pendingMessages.length, dedupedPending.length]);

  const messages = [...serverMessages, ...dedupedPending];

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length, isThinking, streamingContent]);

  const handleNewConversation = () => {
    // Optimistically add a local conversation and switch to it immediately
    const tempId = `new-${Date.now()}`;
    const tempConv: Conversation = {
      conversation_id: tempId,
      display_name: null,
      created_at: new Date().toISOString(),
      model_id: selectedModelId,
      project_id: selectedProjectId,
      messages: [],
    };
    queryClient.setQueryData(['/api/v1/chat/conversations'], (old: { data?: Conversation[] } | undefined) => ({
      ...old,
      data: [tempConv, ...(old?.data ?? [])],
    }));
    setActiveConvId(tempId);
    setPendingMessages([]);
    setIsThinking(false);

    createMutation.mutate(
      {
        data: {
          user_id: 'ui-user',
          display_name: 'You',
          model_id: selectedModelId,
          project_id: selectedProjectId,
        },
      },
      {
        onSuccess: (resp) => {
          const conv = resp?.data as Conversation | undefined;
          if (conv) {
            // Replace temp conversation with the real one
            setActiveConvId(conv.conversation_id);
            queryClient.setQueryData(['/api/v1/chat/conversations'], (old: { data?: Conversation[] } | undefined) => ({
              ...old,
              data: (old?.data ?? []).map((c: Conversation) =>
                c.conversation_id === tempId ? { ...conv } : c,
              ),
            }));
          }
        },
        onError: () => {
          // Remove the temp conversation
          queryClient.setQueryData(['/api/v1/chat/conversations'], (old: { data?: Conversation[] } | undefined) => ({
            ...old,
            data: (old?.data ?? []).filter((c: Conversation) => c.conversation_id !== tempId),
          }));
          setActiveConvId(null);
          notifications.show({ title: 'Error', message: 'Failed to start conversation', color: 'red' });
        },
      },
    );
  };

  const handleSend = () => {
    if (!newMessage.trim() || !activeConvId || activeConvId.startsWith('new-')) return;
    const msg = newMessage;
    setNewMessage('');

    // Optimistically show user message
    const optimisticMsg: Message = {
      message_id: `pending-${Date.now()}`,
      role: 'user',
      content: msg,
      display_name: 'You',
      timestamp: new Date().toISOString(),
    };
    setPendingMessages((prev) => [...prev, optimisticMsg]);
    setIsThinking(true);
    setStreamingContent('');

    const controller = new AbortController();
    abortRef.current = controller;

    fetch(`/api/v1/chat/conversations/${activeConvId}/messages/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: 'ui-user',
        display_name: 'You',
        message: msg,
      }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const reader = response.body?.getReader();
        if (!reader) throw new Error('No reader');
        const decoder = new TextDecoder();
        let accumulated = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const text = decoder.decode(value, { stream: true });
          const lines = text.split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') continue;
              try {
                const parsed = JSON.parse(data) as { token: string };
                accumulated += parsed.token;
                setStreamingContent(accumulated);
              } catch {
                // skip malformed chunks
              }
            }
          }
        }
      })
      .catch((err) => {
        if ((err as Error).name !== 'AbortError') {
          notifications.show({ title: 'Error', message: 'Failed to send message', color: 'red' });
        }
      })
      .finally(() => {
        setIsThinking(false);
        setStreamingContent('');
        abortRef.current = null;
        void queryClient.invalidateQueries({ queryKey: [`/api/v1/chat/conversations/${activeConvId}`] });
      });
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
            <ActionIcon
              size="sm"
              variant="filled"
              onClick={handleNewConversation}
            >
              <IconPlus size={14} />
            </ActionIcon>
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

          {/* Project selector */}
          {projects.length > 0 && (
            <Select
              size="xs"
              mb="xs"
              placeholder="Select project (optional)"
              value={selectedProjectId}
              onChange={setSelectedProjectId}
              clearable
              data={projects.map((p) => ({
                value: p.project_id,
                label: p.name,
              }))}
            />
          )}

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
                    onClick={() => { setActiveConvId(c.conversation_id); setPendingMessages([]); setIsThinking(false); }}
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
                description="Click + to start a new conversation"
              />
            </Center>
          ) : (
            <>
              <Group gap="xs" mb="xs">
                {activeConversation?.project_id && (
                  <>
                    <Text size="xs" c="dimmed">Project:</Text>
                    <Badge size="xs" variant="light" color="teal">
                      {projects.find((p) => p.project_id === activeConversation.project_id)?.name ?? activeConversation.project_id}
                    </Badge>
                  </>
                )}
                {activeConversation?.model_id && (
                  <>
                    <Text size="xs" c="dimmed">Model:</Text>
                    <Badge size="xs" variant="light">
                      {models.find((m) => m.model_id === activeConversation.model_id)?.name ?? activeConversation.model_id}
                    </Badge>
                  </>
                )}
              </Group>
              <ScrollArea style={{ flex: 1 }} viewportRef={scrollRef}>
                <Stack gap="md" p="xs">
                  {messages.length === 0 && !isThinking && (
                    <Center py="xl">
                      <Text size="sm" c="dimmed">Type a message to start chatting</Text>
                    </Center>
                  )}
                  {messages.map((m) => (
                    <Box
                      key={m.message_id}
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: m.role === 'user' ? 'flex-end' : 'flex-start',
                      }}
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
                        {m.role === 'user' ? (
                          <Text size="sm" style={{ whiteSpace: 'pre-wrap' }} c="white" dir="auto">
                            {m.content}
                          </Text>
                        ) : (
                          <Box className="chat-markdown" fz="sm" dir="auto">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {m.content}
                            </ReactMarkdown>
                          </Box>
                        )}
                      </Paper>
                      <CopyBtn content={m.content} />
                    </Box>
                  ))}
                  {isThinking && streamingContent && (
                    <Box style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                      <Paper
                        p="sm"
                        radius="md"
                        maw="70%"
                        style={{ background: 'var(--mantine-color-dark-5)' }}
                      >
                        <Group gap="xs" mb={4}>
                          <Badge size="xs" variant="light">Lintel</Badge>
                        </Group>
                        <Box className="chat-markdown" fz="sm" dir="auto">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {streamingContent}
                          </ReactMarkdown>
                        </Box>
                      </Paper>
                      <CopyBtn content={streamingContent} />
                    </Box>
                  )}
                  {isThinking && !streamingContent && (
                    <Group justify="flex-start" align="flex-end" gap="xs">
                      <Paper
                        p="sm"
                        radius="md"
                        style={{ background: 'var(--mantine-color-dark-5)' }}
                      >
                        <Group gap="xs" mb={4}>
                          <Badge size="xs" variant="light">Lintel</Badge>
                        </Group>
                        <Group gap={4}>
                          <Loader size="xs" type="dots" />
                          <Text size="sm" c="dimmed">Thinking...</Text>
                        </Group>
                      </Paper>
                    </Group>
                  )}
                </Stack>
              </ScrollArea>

              <Group gap="xs" mt="md">
                <TextInput
                  placeholder="Type a message..."
                  dir="auto"
                  style={{ flex: 1 }}
                  value={newMessage}
                  onChange={(e) => setNewMessage(e.currentTarget.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                />
                <ActionIcon
                  size="lg"
                  variant="filled"
                  onClick={handleSend}
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
