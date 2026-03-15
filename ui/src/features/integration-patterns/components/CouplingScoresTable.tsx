import { useMemo, useState } from 'react';
import { Table, Progress, Text, Paper } from '@mantine/core';
import type { ServiceCouplingScore, ServiceNode } from '../types';

interface CouplingScoresTableProps {
  scores: ServiceCouplingScore[];
  nodes: ServiceNode[];
}

type SortField = 'service' | 'afferent' | 'efferent' | 'instability';
type SortDir = 'asc' | 'desc';

function instabilityColor(value: number): string {
  if (value > 0.7) return 'red';
  if (value > 0.4) return 'yellow';
  return 'green';
}

export function CouplingScoresTable({
  scores,
  nodes,
}: CouplingScoresTableProps) {
  const [sortField, setSortField] = useState<SortField>('instability');
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  const nodeMap = useMemo(
    () => new Map(nodes.map((n) => [n.node_id, n.service_name])),
    [nodes],
  );

  const rows = useMemo(() => {
    return [...scores].sort((a, b) => {
      let cmp = 0;
      switch (sortField) {
        case 'service':
          cmp = (nodeMap.get(a.service_node_id) ?? '').localeCompare(
            nodeMap.get(b.service_node_id) ?? '',
          );
          break;
        case 'afferent':
          cmp = a.afferent_coupling - b.afferent_coupling;
          break;
        case 'efferent':
          cmp = a.efferent_coupling - b.efferent_coupling;
          break;
        case 'instability':
          cmp = a.instability - b.instability;
          break;
      }
      return sortDir === 'desc' ? -cmp : cmp;
    });
  }, [scores, sortField, sortDir, nodeMap]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortField(field);
      setSortDir('desc');
    }
  };

  const sortIndicator = (field: SortField) =>
    sortField === field ? (sortDir === 'desc' ? ' \u2193' : ' \u2191') : '';

  const thStyle = { cursor: 'pointer', userSelect: 'none' as const };

  return (
    <Paper withBorder p="md" radius="md">
      <Text fw={600} mb="md">
        Coupling Scores
      </Text>

      {rows.length === 0 ? (
        <Text c="dimmed" size="sm" ta="center" py="lg">
          No coupling scores available.
        </Text>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th style={thStyle} onClick={() => handleSort('service')}>
                Service Name{sortIndicator('service')}
              </Table.Th>
              <Table.Th style={thStyle} onClick={() => handleSort('afferent')}>
                Afferent{sortIndicator('afferent')}
              </Table.Th>
              <Table.Th style={thStyle} onClick={() => handleSort('efferent')}>
                Efferent{sortIndicator('efferent')}
              </Table.Th>
              <Table.Th style={thStyle} onClick={() => handleSort('instability')}>
                Instability{sortIndicator('instability')}
              </Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((s) => (
              <Table.Tr key={s.score_id}>
                <Table.Td>
                  <Text size="sm" fw={500}>
                    {nodeMap.get(s.service_node_id) ?? s.service_node_id}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{s.afferent_coupling}</Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm">{s.efferent_coupling}</Text>
                </Table.Td>
                <Table.Td>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 8,
                    }}
                  >
                    <Progress
                      value={s.instability * 100}
                      color={instabilityColor(s.instability)}
                      size="sm"
                      style={{ flex: 1, minWidth: 60 }}
                    />
                    <Text size="xs" fw={500} w={36} ta="right">
                      {s.instability.toFixed(2)}
                    </Text>
                  </div>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Paper>
  );
}
