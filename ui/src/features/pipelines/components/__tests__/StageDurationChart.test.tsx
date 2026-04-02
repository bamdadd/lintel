import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, it, expect } from 'vitest';
import { StageDurationChart } from '../StageDurationChart';
import type { StageItem } from '../StageCard';

function makeStage(overrides: Partial<StageItem> & { stage_id: string; name: string; status: string }): StageItem {
  return {
    stage_id: overrides.stage_id,
    name: overrides.name,
    status: overrides.status,
    duration_ms: overrides.duration_ms,
    ...overrides,
  };
}

describe('StageDurationChart', () => {
  it('shows empty message when no stages have durations', () => {
    const stages = [makeStage({ stage_id: '1', name: 'research', status: 'pending' })];
    render(<MantineProvider><StageDurationChart stages={stages} /></MantineProvider>);
    expect(screen.getByText('No duration data available yet')).toBeTruthy();
  });

  it('renders bars for stages with duration', () => {
    const stages = [
      makeStage({ stage_id: '1', name: 'Research', status: 'completed', duration_ms: 5000 }),
      makeStage({ stage_id: '2', name: 'Implement', status: 'failed', duration_ms: 12000 }),
      makeStage({ stage_id: '3', name: 'Review', status: 'running', duration_ms: 3000 }),
    ];
    render(<MantineProvider><StageDurationChart stages={stages} /></MantineProvider>);

    expect(screen.getByText('Research')).toBeTruthy();
    expect(screen.getByText('Implement')).toBeTruthy();
    expect(screen.getByText('Review')).toBeTruthy();
    expect(screen.getByText('5.0s')).toBeTruthy();
    expect(screen.getByText('12.0s')).toBeTruthy();
    expect(screen.getByText('3.0s')).toBeTruthy();
  });

  it('shows total duration', () => {
    const stages = [
      makeStage({ stage_id: '1', name: 'A', status: 'completed', duration_ms: 65000 }),
      makeStage({ stage_id: '2', name: 'B', status: 'completed', duration_ms: 35000 }),
    ];
    render(<MantineProvider><StageDurationChart stages={stages} /></MantineProvider>);
    expect(screen.getByText('Total: 1m 40s')).toBeTruthy();
  });

  it('filters out stages without duration', () => {
    const stages = [
      makeStage({ stage_id: '1', name: 'Done', status: 'completed', duration_ms: 1000 }),
      makeStage({ stage_id: '2', name: 'Pending', status: 'pending' }),
    ];
    render(<MantineProvider><StageDurationChart stages={stages} /></MantineProvider>);
    expect(screen.getByText('Done')).toBeTruthy();
    expect(screen.queryByText('Pending')).toBeNull();
  });

  it('renders legend items', () => {
    const stages = [
      makeStage({ stage_id: '1', name: 'A', status: 'completed', duration_ms: 1000 }),
    ];
    render(<MantineProvider><StageDurationChart stages={stages} /></MantineProvider>);
    expect(screen.getByText('Completed')).toBeTruthy();
    expect(screen.getByText('Failed')).toBeTruthy();
    expect(screen.getByText('Running')).toBeTruthy();
  });
});
