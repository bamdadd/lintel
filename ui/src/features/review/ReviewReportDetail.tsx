import { useEffect, useState } from 'react';
import { Badge, Group, Paper, Stack, Table, Text, Title } from '@mantine/core';
import { useParams } from 'react-router-dom';
import { fetchReviewReport, type ReviewReport } from './reviewApi';

function severityColor(severity: string): string {
  const map: Record<string, string> = {
    critical: 'red',
    high: 'orange',
    medium: 'yellow',
    low: 'blue',
    info: 'gray',
  };
  return map[severity] ?? 'gray';
}

export function ReviewReportDetail() {
  const { reportId } = useParams<{ reportId: string }>();
  const [report, setReport] = useState<ReviewReport | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!reportId) return;
    fetchReviewReport(reportId)
      .then(setReport)
      .finally(() => setLoading(false));
  }, [reportId]);

  if (loading) return <Text>Loading report…</Text>;
  if (!report) return <Text>Report not found.</Text>;

  return (
    <Stack gap="lg">
      <Title order={2}>Review Report {report.report_id.slice(0, 8)}…</Title>

      <Group>
        {Object.entries(report.aggregate_scores).map(([dim, score]) => (
          <Paper key={dim} p="sm" withBorder>
            <Text size="xs" c="dimmed" style={{ textTransform: 'capitalize' }}>{dim}</Text>
            <Text size="xl" fw={700}>{score.toFixed(1)}</Text>
          </Paper>
        ))}
      </Group>

      <Title order={3}>Per-File Scores</Title>
      <Paper p="md" withBorder>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>File</Table.Th>
              <Table.Th>Dimension</Table.Th>
              <Table.Th>Score</Table.Th>
              <Table.Th>Severity</Table.Th>
              <Table.Th>Findings</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {report.per_file_scores.map((pfs, idx) => (
              <Table.Tr key={idx}>
                <Table.Td><Text size="sm" ff="monospace">{pfs.file_path}</Text></Table.Td>
                <Table.Td style={{ textTransform: 'capitalize' }}>{pfs.dimension}</Table.Td>
                <Table.Td>{pfs.score.toFixed(1)}</Table.Td>
                <Table.Td>
                  <Badge color={severityColor(pfs.severity)}>{pfs.severity}</Badge>
                </Table.Td>
                <Table.Td>{pfs.findings.length}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Paper>
    </Stack>
  );
}

export function Component() {
  return <ReviewReportDetail />;
}
