import { useEffect, useState } from 'react';
import { Badge, Group, Paper, Stack, Table, Text, Title } from '@mantine/core';
import { useParams, Link } from 'react-router-dom';
import { fetchReviewReports, type ReviewReport } from './reviewApi';

const DIMENSIONS = ['correctness', 'security', 'performance', 'maintainability', 'architecture'];

function scoreBadgeColor(score: number): string {
  if (score >= 8) return 'green';
  if (score >= 5) return 'yellow';
  return 'red';
}

export function ReviewReportsList() {
  const { repoId } = useParams<{ repoId: string }>();
  const [reports, setReports] = useState<ReviewReport[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!repoId) return;
    fetchReviewReports(repoId)
      .then(setReports)
      .finally(() => setLoading(false));
  }, [repoId]);

  if (loading) return <Text>Loading review reports…</Text>;

  return (
    <Stack gap="lg">
      <Title order={2}>Review Reports</Title>
      <Paper p="md" withBorder>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Report ID</Table.Th>
              {DIMENSIONS.map((d) => (
                <Table.Th key={d} style={{ textTransform: 'capitalize' }}>{d}</Table.Th>
              ))}
              <Table.Th>Pipeline Run</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {reports.map((r) => (
              <Table.Tr key={r.report_id}>
                <Table.Td>
                  <Link to={`/review/reports/${r.report_id}`}>
                    {r.report_id.slice(0, 8)}…
                  </Link>
                </Table.Td>
                {DIMENSIONS.map((d) => (
                  <Table.Td key={d}>
                    <Badge color={scoreBadgeColor(r.aggregate_scores[d] ?? 0)}>
                      {(r.aggregate_scores[d] ?? 0).toFixed(1)}
                    </Badge>
                  </Table.Td>
                ))}
                <Table.Td>{r.pipeline_run_id.slice(0, 8)}…</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Paper>
    </Stack>
  );
}

export function Component() {
  return <ReviewReportsList />;
}
