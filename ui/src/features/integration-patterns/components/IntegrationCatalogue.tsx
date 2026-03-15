import { useMemo, useState } from 'react';
import { Table, Select, Group, Text, Paper } from '@mantine/core';
import type { PatternCatalogueEntry } from '../types';

interface IntegrationCatalogueProps {
  patterns: PatternCatalogueEntry[];
}

type SortDir = 'asc' | 'desc';

export function IntegrationCatalogue({ patterns }: IntegrationCatalogueProps) {
  const [filterType, setFilterType] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>('desc');

  // Unique pattern types for the filter dropdown
  const patternTypes = useMemo(() => {
    const types = [...new Set(patterns.map((p) => p.pattern_type))];
    return types.map((t) => ({ value: t, label: t }));
  }, [patterns]);

  // Filter + sort
  const rows = useMemo(() => {
    let filtered = patterns;
    if (filterType) {
      filtered = filtered.filter((p) => p.pattern_type === filterType);
    }
    return [...filtered].sort((a, b) =>
      sortDir === 'desc'
        ? b.occurrences - a.occurrences
        : a.occurrences - b.occurrences,
    );
  }, [patterns, filterType, sortDir]);

  const toggleSort = () => setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));

  return (
    <Paper withBorder p="md" radius="md">
      <Group justify="space-between" mb="md">
        <Text fw={600}>Pattern Catalogue</Text>
        <Select
          placeholder="Filter by type"
          data={patternTypes}
          value={filterType}
          onChange={setFilterType}
          clearable
          size="xs"
          w={200}
        />
      </Group>

      {rows.length === 0 ? (
        <Text c="dimmed" size="sm" ta="center" py="lg">
          No patterns found.
        </Text>
      ) : (
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Pattern Name</Table.Th>
              <Table.Th>Pattern Type</Table.Th>
              <Table.Th
                style={{ cursor: 'pointer', userSelect: 'none' }}
                onClick={toggleSort}
              >
                Occurrences {sortDir === 'desc' ? '\u2193' : '\u2191'}
              </Table.Th>
              <Table.Th>Details</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((p) => (
              <Table.Tr key={p.entry_id}>
                <Table.Td>
                  <Text size="sm" fw={500}>
                    {p.pattern_name}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" c="dimmed">
                    {p.pattern_type}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="sm" fw={500}>
                    {p.occurrences}
                  </Text>
                </Table.Td>
                <Table.Td>
                  <Text size="xs" c="dimmed" lineClamp={1}>
                    {Object.keys(p.details).length > 0
                      ? JSON.stringify(p.details)
                      : '-'}
                  </Text>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Paper>
  );
}
