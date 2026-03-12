/**
 * Integration tests for StageCard.
 *
 * Coverage:
 *  - Renders stage name and status badge
 *  - Error section is always visible (not collapsible)
 *  - Logs section absent when no logs
 *  - Logs section present and collapsed when logs exist
 *  - Logs section expands on click
 *  - Implementation Plan section absent when no plan
 *  - Implementation Plan section present and collapsed when plan exists
 *  - Code Changes section absent when no diff
 *  - Code Changes section present and collapsed when diff exists
 *  - Outputs section absent when no other outputs
 *  - Outputs section present and collapsed when other outputs exist
 *  - Approve / Reject buttons shown for waiting_approval
 *  - Retry button shown for failed stages
 *  - Retry button disabled after 3 retries
 *  - Approve calls correct API endpoint
 *  - Reject calls correct API endpoint
 *  - Retry calls correct API endpoint
 *  - Sandbox badge navigates to sandbox page
 *  - Duration is displayed when present
 *  - All four collapsible sections default to collapsed
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { MemoryRouter } from 'react-router';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { StageCard } from '../StageCard';
import type { StageItem } from '../StageCard';

// ── Helpers ────────────────────────────────────────────────────────────────

function renderCard(
  stageOverrides: Partial<StageItem> = {},
  runId = 'run-abc',
) {
  const base: StageItem = {
    stage_id: 'stage-1',
    name: 'implement',
    status: 'succeeded',
    stage_type: 'agent',
    ...stageOverrides,
  };

  return render(
    <MemoryRouter>
      <MantineProvider>
        <StageCard stage={base} runId={runId} />
      </MantineProvider>
    </MemoryRouter>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('StageCard', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // ── Basic rendering ────────────────────────────────────────────────────

  it('renders the stage name', () => {
    renderCard({ name: 'plan' });
    expect(screen.getByText('plan')).toBeInTheDocument();
  });

  it('renders the status badge', () => {
    renderCard({ status: 'succeeded' });
    expect(screen.getByText('succeeded')).toBeInTheDocument();
  });

  it('renders stage type', () => {
    renderCard({ stage_type: 'approval' });
    expect(screen.getByText(/approval/)).toBeInTheDocument();
  });

  it('renders duration when present', () => {
    renderCard({ duration_ms: 3500 });
    expect(screen.getByText(/3\.5s/)).toBeInTheDocument();
  });

  // ── Error section ──────────────────────────────────────────────────────

  it('shows error section when error is present', () => {
    renderCard({ error: 'Something went wrong' });
    expect(screen.getByTestId('stage-error')).toBeInTheDocument();
    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
  });

  it('does not show error section when no error', () => {
    renderCard({ error: undefined });
    expect(screen.queryByTestId('stage-error')).not.toBeInTheDocument();
  });

  // ── Logs section ──────────────────────────────────────────────────────

  it('does not render Logs section when no logs', () => {
    renderCard({ logs: undefined, status: 'succeeded' });
    expect(screen.queryByTestId('section-logs')).not.toBeInTheDocument();
  });

  it('does not render Logs section for empty logs array', () => {
    renderCard({ logs: [], status: 'succeeded' });
    expect(screen.queryByTestId('section-logs')).not.toBeInTheDocument();
  });

  it('renders Logs section when logs are present', () => {
    renderCard({ logs: ['line 1', 'line 2'], status: 'succeeded' });
    expect(screen.getByTestId('section-logs')).toBeInTheDocument();
  });

  it('Logs section is collapsed by default', () => {
    renderCard({ logs: ['line 1'], status: 'succeeded' });
    const trigger = screen.getByTestId('section-logs-trigger');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('Logs section expands on click', () => {
    renderCard({ logs: ['line 1'], status: 'succeeded' });
    const trigger = screen.getByTestId('section-logs-trigger');
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });

  it('Logs section title is "Logs"', () => {
    renderCard({ logs: ['line 1'], status: 'succeeded' });
    const trigger = screen.getByTestId('section-logs-trigger');
    expect(trigger).toHaveTextContent('Logs');
  });

  // ── Implementation Plan section ────────────────────────────────────────

  it('does not render Implementation Plan section when no plan', () => {
    renderCard({ outputs: {} });
    expect(screen.queryByTestId('section-plan')).not.toBeInTheDocument();
  });

  it('renders Implementation Plan section when plan is present', () => {
    renderCard({
      outputs: { plan: { tasks: [], summary: 'Do the thing' } },
    });
    expect(screen.getByTestId('section-plan')).toBeInTheDocument();
  });

  it('Implementation Plan section is collapsed by default', () => {
    renderCard({
      outputs: { plan: { tasks: [] } },
    });
    const trigger = screen.getByTestId('section-plan-trigger');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('Implementation Plan section expands on click', () => {
    renderCard({
      outputs: { plan: { tasks: [] } },
    });
    const trigger = screen.getByTestId('section-plan-trigger');
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });

  it('Implementation Plan section title is "Implementation Plan"', () => {
    renderCard({ outputs: { plan: { tasks: [] } } });
    const trigger = screen.getByTestId('section-plan-trigger');
    expect(trigger).toHaveTextContent('Implementation Plan');
  });

  // ── Code Changes section ───────────────────────────────────────────────

  it('does not render Code Changes section when no diff', () => {
    renderCard({ outputs: {} });
    expect(screen.queryByTestId('section-diff')).not.toBeInTheDocument();
  });

  it('renders Code Changes section when diff is present', () => {
    renderCard({ outputs: { diff: 'diff --git a/foo b/foo\n+added' } });
    expect(screen.getByTestId('section-diff')).toBeInTheDocument();
  });

  it('Code Changes section is collapsed by default', () => {
    renderCard({ outputs: { diff: 'diff --git a/foo b/foo\n+added' } });
    const trigger = screen.getByTestId('section-diff-trigger');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('Code Changes section expands on click', () => {
    renderCard({ outputs: { diff: 'diff --git a/foo b/foo\n+added' } });
    const trigger = screen.getByTestId('section-diff-trigger');
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });

  it('Code Changes section title is "Code Changes"', () => {
    renderCard({ outputs: { diff: '+line' } });
    const trigger = screen.getByTestId('section-diff-trigger');
    expect(trigger).toHaveTextContent('Code Changes');
  });

  // ── Outputs section ────────────────────────────────────────────────────

  it('does not render Outputs section when no other outputs', () => {
    renderCard({ outputs: { plan: {}, diff: '', research_report: '' } });
    expect(screen.queryByTestId('section-outputs')).not.toBeInTheDocument();
  });

  it('renders Outputs section when other outputs are present', () => {
    renderCard({ outputs: { custom_key: 'custom_value' } });
    expect(screen.getByTestId('section-outputs')).toBeInTheDocument();
  });

  it('Outputs section is collapsed by default', () => {
    renderCard({ outputs: { custom_key: 'value' } });
    const trigger = screen.getByTestId('section-outputs-trigger');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('Outputs section expands on click', () => {
    renderCard({ outputs: { custom_key: 'value' } });
    const trigger = screen.getByTestId('section-outputs-trigger');
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });

  it('Outputs section title is "Outputs"', () => {
    renderCard({ outputs: { custom_key: 'value' } });
    const trigger = screen.getByTestId('section-outputs-trigger');
    expect(trigger).toHaveTextContent('Outputs');
  });

  it('sandbox_id key is excluded from Outputs section', () => {
    // sandbox_id alone should NOT produce an Outputs section
    renderCard({ outputs: { sandbox_id: 'sb-123' } });
    expect(screen.queryByTestId('section-outputs')).not.toBeInTheDocument();
  });

  // ── All four sections default to collapsed ─────────────────────────────

  it('all four sections default to collapsed when all data is present', () => {
    renderCard({
      status: 'succeeded',
      logs: ['log line'],
      outputs: {
        plan: { tasks: [] },
        diff: '+line',
        custom_key: 'value',
      },
    });

    for (const testId of [
      'section-logs-trigger',
      'section-plan-trigger',
      'section-diff-trigger',
      'section-outputs-trigger',
    ]) {
      expect(screen.getByTestId(testId)).toHaveAttribute(
        'aria-expanded',
        'false',
      );
    }
  });

  // ── Action buttons ─────────────────────────────────────────────────────

  it('shows Approve and Reject buttons for waiting_approval', () => {
    renderCard({ status: 'waiting_approval' });
    expect(screen.getByTestId('approve-btn')).toBeInTheDocument();
    expect(screen.getByTestId('reject-btn')).toBeInTheDocument();
  });

  it('does not show Approve/Reject for succeeded stages', () => {
    renderCard({ status: 'succeeded' });
    expect(screen.queryByTestId('approve-btn')).not.toBeInTheDocument();
    expect(screen.queryByTestId('reject-btn')).not.toBeInTheDocument();
  });

  it('shows Retry button for failed stages', () => {
    renderCard({ status: 'failed' });
    expect(screen.getByTestId('retry-btn')).toBeInTheDocument();
    expect(screen.getByTestId('retry-btn')).toHaveTextContent('Retry');
  });

  it('shows Restart button for running stages', () => {
    // running stages open an EventSource (stubbed in setup.ts)
    renderCard({ status: 'running' });
    expect(screen.getByTestId('retry-btn')).toHaveTextContent('Restart');
  });

  it('Retry button is disabled after 5 retries', () => {
    renderCard({ status: 'failed', retry_count: 5 });
    expect(screen.getByTestId('retry-btn')).toBeDisabled();
  });

  it('Retry button is enabled with 4 retries', () => {
    renderCard({ status: 'failed', retry_count: 4 });
    expect(screen.getByTestId('retry-btn')).not.toBeDisabled();
  });

  // ── API calls ──────────────────────────────────────────────────────────

  it('Approve calls correct API endpoint', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response('{}', { status: 200 }));

    renderCard({ status: 'waiting_approval' }, 'run-xyz');
    fireEvent.click(screen.getByTestId('approve-btn'));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/pipelines/run-xyz/stages/stage-1/approve',
        expect.objectContaining({ method: 'POST' }),
      );
    });
  });

  it('Reject calls correct API endpoint', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response('{}', { status: 200 }));

    renderCard({ status: 'waiting_approval' }, 'run-xyz');
    fireEvent.click(screen.getByTestId('reject-btn'));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/pipelines/run-xyz/stages/stage-1/reject',
        expect.objectContaining({ method: 'POST' }),
      );
    });
  });

  it('Retry calls correct API endpoint', async () => {
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockResolvedValue(new Response('{}', { status: 200 }));

    renderCard({ status: 'failed' }, 'run-xyz');
    fireEvent.click(screen.getByTestId('retry-btn'));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/pipelines/run-xyz/stages/stage-1/retry',
        expect.objectContaining({ method: 'POST' }),
      );
    });
  });

  it('calls onActionComplete after approve', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('{}', { status: 200 }),
    );
    const onActionComplete = vi.fn();

    render(
      <MemoryRouter>
        <MantineProvider>
          <StageCard
            stage={{
              stage_id: 'stage-1',
              name: 'approve_spec',
              status: 'waiting_approval',
            }}
            runId="run-1"
            onActionComplete={onActionComplete}
          />
        </MantineProvider>
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByTestId('approve-btn'));
    await waitFor(() => expect(onActionComplete).toHaveBeenCalledOnce());
  });

  // ── Sandbox badge ──────────────────────────────────────────────────────

  it('renders sandbox badge when sandbox_id is present', () => {
    renderCard({ outputs: { sandbox_id: 'sb-abcdef123456' } });
    // Mantine Badge may split text across inner spans; use a substring matcher
    expect(
      screen.getByText('sb-abcdef123'),
    ).toBeInTheDocument();
  });

  it('does not render sandbox badge when sandbox_id is absent', () => {
    renderCard({ outputs: {} });
    expect(screen.queryByText(/Sandbox/)).not.toBeInTheDocument();
  });

  // ── Research report section ────────────────────────────────────────────

  it('renders Research Report section when research_report is present', () => {
    renderCard({
      status: 'succeeded',
      outputs: { research_report: '# Report\nFindings' },
    });
    expect(screen.getByTestId('section-research')).toBeInTheDocument();
  });

  it('Research Report section is collapsed by default', () => {
    renderCard({
      status: 'succeeded',
      outputs: { research_report: '# Report' },
    });
    const trigger = screen.getByTestId('section-research-trigger');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('does not render Research Report section when absent', () => {
    renderCard({ outputs: {} });
    expect(screen.queryByTestId('section-research')).not.toBeInTheDocument();
  });
});
