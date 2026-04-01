import { useEffect, useState } from 'react';
import { Paper, Select, Stack, Table, Text, Title } from '@mantine/core';
import { useParams } from 'react-router-dom';
import { fetchScoreTrends, type ReviewScoreRecord } from './reviewApi';

const DIMENSIONS = [
  { value: '', label: 'All Dimensions' },
  { value: 'correctness', label: 'Correctness' },
  { value: 'security', label: 'Security' },
  { value: 'performance', label: 'Performance' },
  { value: 'maintainability', label: 'Maintainability' },
  { value: 'architecture', label: 'Architecture' },
];

export function ReviewScoreTrends() {
  const { repoId } = useParams<{ repoId: string }>();
  const [dimension, setDimension] = useState('');
  const [scores, setScores] = useState<ReviewScoreRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!repoId) return;
    setLoading(true);
    fetchScoreTrends(repoId, dimension || undefined)
      .then(setScores)
      .finally(() => setLoading(false));
  }, [repoId, dimension]);

  return (
    <Stack gap="lg">
      <Title order={2}>Review Score Trends</Title>
      <Select
        label="Dimension"
        data={DIMENSIONS}
        value={dimension}
        onChange={(v) => setDimension(v ?? '')}
        w={250}
      />
      {loading ? (
        <Text>Loading trends…</Text>
      ) : (
        <Paper p="md" withBorder>
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Date</Table.Th>
                <Table.Th>Dimension</Table.Th>
                <Table.Th>Score</Table.Th>
                <Table.Th>Severity</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {scores.map((s) => (
                <Table.Tr key={s.score_id}>
                  <Table.Td>{new Date(s.recorded_at).toLocaleDateString()}</Table.Td>
                  <Table.Td style={{ textTransform: 'capitalize' }}>{s.dimension}</Table.Td>
                  <Table.Td>{s.score.toFixed(1)}</Table.Td>
                  <Table.Td>{s.severity}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Paper>
      )}
    </Stack>
  );
}

export function Component() {
  return <ReviewScoreTrends />;
}
