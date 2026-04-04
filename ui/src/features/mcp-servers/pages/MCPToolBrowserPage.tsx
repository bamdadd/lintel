import { useCallback, useEffect, useRef, useState } from 'react';
import {
  Title, Stack, Loader, Center, Text, Paper, Badge, Group,
  TextInput, Accordion, Code, Table, ThemeIcon, Anchor, TypographyStylesProvider,
} from '@mantine/core';
import { IconSearch, IconTool, IconServer } from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { EmptyState } from '@/shared/components/EmptyState';
import { Link } from 'react-router';

interface MCPServerItem {
  server_id: string;
  name: string;
  url: string;
  enabled: boolean;
  description: string;
}

interface MCPTool {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
}

interface ServerTools {
  server: MCPServerItem;
  tools: MCPTool[];
  loading: boolean;
  error: boolean;
}

const API = '/api/v1/mcp-servers';

export function Component() {
  const [serverTools, setServerTools] = useState<ServerTools[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const hasLoaded = useRef(false);

  const load = useCallback(() => {
    fetch(API)
      .then((r) => r.json())
      .then((servers: MCPServerItem[]) => {
        const enabled = servers.filter((s) => s.enabled);
        setServerTools(
          enabled.map((s) => ({ server: s, tools: [], loading: true, error: false })),
        );
        setIsLoading(false);

        for (const server of enabled) {
          fetch(`${API}/${server.server_id}/tools`)
            .then((r) => {
              if (!r.ok) throw new Error();
              return r.json();
            })
            .then((tools: MCPTool[]) => {
              setServerTools((prev) =>
                prev.map((st) =>
                  st.server.server_id === server.server_id
                    ? { ...st, tools, loading: false }
                    : st,
                ),
              );
            })
            .catch(() => {
              setServerTools((prev) =>
                prev.map((st) =>
                  st.server.server_id === server.server_id
                    ? { ...st, loading: false, error: true }
                    : st,
                ),
              );
            });
        }
      })
      .catch(() => setIsLoading(false));
  }, []);

  useEffect(() => {
    if (!hasLoaded.current) {
      hasLoaded.current = true;
      load();
    }
  }, [load]);

  const lowerSearch = search.toLowerCase();
  const filtered = serverTools
    .map((st) => ({
      ...st,
      tools: st.tools.filter(
        (t) =>
          t.name.toLowerCase().includes(lowerSearch) ||
          t.description.toLowerCase().includes(lowerSearch),
      ),
    }))
    .filter((st) => st.loading || st.tools.length > 0 || (search === '' && st.error));

  const totalTools = serverTools.reduce((n, st) => n + st.tools.length, 0);

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>MCP Tool Browser</Title>
        <Badge size="lg" variant="light">{totalTools} tools</Badge>
      </Group>

      <Text size="sm" c="dimmed">
        Browse all tools available from connected MCP servers.{' '}
        <Anchor component={Link} to="/mcp-servers" size="sm">Manage servers</Anchor>
      </Text>

      <TextInput
        placeholder="Search tools by name or description..."
        leftSection={<IconSearch size={16} />}
        value={search}
        onChange={(e) => setSearch(e.currentTarget.value)}
      />

      {filtered.length === 0 ? (
        <EmptyState
          title="No tools found"
          description={
            search
              ? 'No tools match your search. Try a different query.'
              : 'No enabled MCP servers with tools. Add and enable servers first.'
          }
        />
      ) : (
        <Accordion variant="separated" multiple defaultValue={filtered.map((st) => st.server.server_id)}>
          {filtered.map((st) => (
            <Accordion.Item key={st.server.server_id} value={st.server.server_id}>
              <Accordion.Control>
                <Group gap="sm">
                  <ThemeIcon size="sm" variant="light" color="blue">
                    <IconServer size={14} />
                  </ThemeIcon>
                  <Text fw={500}>{st.server.name}</Text>
                  <Badge size="xs" variant="light">
                    {st.loading ? '...' : `${st.tools.length} tools`}
                  </Badge>
                  {st.server.description && (
                    <Text size="xs" c="dimmed" truncate maw={300}>
                      {st.server.description}
                    </Text>
                  )}
                </Group>
              </Accordion.Control>
              <Accordion.Panel>
                {st.loading ? (
                  <Center py="sm"><Loader size="sm" /></Center>
                ) : st.error ? (
                  <Text c="red" size="sm">Failed to fetch tools from this server.</Text>
                ) : st.tools.length === 0 ? (
                  <Text c="dimmed" size="sm">No tools available.</Text>
                ) : (
                  <Stack gap="xs">
                    {st.tools.map((tool) => (
                      <Paper key={tool.name} withBorder p="sm">
                        <Group gap="xs" mb={4}>
                          <IconTool size={14} />
                          <Badge variant="outline" size="sm">{tool.name}</Badge>
                        </Group>
                        <TypographyStylesProvider fz="sm" mb="xs">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>
                            {tool.description}
                          </ReactMarkdown>
                        </TypographyStylesProvider>
                        {tool.input_schema &&
                          typeof tool.input_schema === 'object' &&
                          'properties' in tool.input_schema && (
                            <InputSchemaTable schema={tool.input_schema} />
                          )}
                      </Paper>
                    ))}
                  </Stack>
                )}
              </Accordion.Panel>
            </Accordion.Item>
          ))}
        </Accordion>
      )}
    </Stack>
  );
}

function InputSchemaTable({ schema }: { schema: Record<string, unknown> }) {
  const properties = schema.properties as Record<string, Record<string, unknown>> | undefined;
  const required = (schema.required as string[]) ?? [];
  if (!properties || Object.keys(properties).length === 0) return null;

  return (
    <Table size="xs" withTableBorder>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Parameter</Table.Th>
          <Table.Th>Type</Table.Th>
          <Table.Th>Required</Table.Th>
          <Table.Th>Description</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {Object.entries(properties).map(([name, prop]) => (
          <Table.Tr key={name}>
            <Table.Td><Code>{name}</Code></Table.Td>
            <Table.Td><Badge size="xs" variant="light">{String(prop.type ?? 'any')}</Badge></Table.Td>
            <Table.Td>{required.includes(name) ? 'Yes' : 'No'}</Table.Td>
            <Table.Td><Text size="xs" truncate maw={300}>{String(prop.description ?? '')}</Text></Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}
