import { useState, useMemo } from 'react';
import {
  Title,
  Stack,
  Table,
  Group,
  Loader,
  Center,
  Badge,
  TextInput,
  Text,
} from '@mantine/core';
import { IconSearch } from '@tabler/icons-react';
import { useArtifactsListTestResults } from '@/generated/api/artifacts/artifacts';
import { EmptyState } from '@/shared/components/EmptyState';

interface TestResult {
  test_result_id: string;
  pipeline_run_id: string;
  test_name: string;
  status: string;
  duration_ms: number;
  output: string;
  created_at: string;
}

export function Component() {
  const { data: resp, isLoading } = useArtifactsListTestResults();
  const [search, setSearch] = useState('');

  const results = useMemo(() => {
    const all = (resp?.data ?? []) as unknown as TestResult[];
    if (!search.trim()) return all;
    const lower = search.toLowerCase();
    return all.filter((r) => r.test_name.toLowerCase().includes(lower));
  }, [resp?.data, search]);

  if (isLoading) return <Center py="xl"><Loader /></Center>;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={2}>Test Results</Title>
      </Group>

      <TextInput
        placeholder="Search by test name…"
        leftSection={<IconSearch size={16} />}
        value={search}
        onChange={(e) => setSearch(e.currentTarget.value)}
      />

      {results.length === 0 ? (
        <EmptyState
          title="No test results"
          description={search ? 'No results match your search.' : 'Test results will appear here once pipelines run tests.'}
        />
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Test Name</Table.Th>
              <Table.Th>Pipeline</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Duration</Table.Th>
              <Table.Th>Date</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {results.map((r) => (
              <Table.Tr key={r.test_result_id}>
                <Table.Td><Text size="sm">{r.test_name}</Text></Table.Td>
                <Table.Td>
                  <Badge size="sm" variant="light" color="blue">
                    {r.pipeline_run_id?.slice(0, 8) ?? '—'}…
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Badge color={r.status === 'passed' ? 'green' : 'red'} size="sm">
                    {r.status}
                  </Badge>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{r.duration_ms != null ? `${r.duration_ms}ms` : '—'}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">
                    {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
