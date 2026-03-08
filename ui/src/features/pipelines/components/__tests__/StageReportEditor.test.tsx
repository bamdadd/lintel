import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MantineProvider } from '@mantine/core';
import { StageReportEditor } from '../StageReportEditor';

function renderEditor(props: Partial<React.ComponentProps<typeof StageReportEditor>> = {}) {
  const defaultProps = {
    runId: 'run-1',
    stageId: 'stage-1',
    stageName: 'research',
    initialContent: '# Research\nFindings here',
    status: 'succeeded',
  };
  return render(
    <MantineProvider>
      <StageReportEditor {...defaultProps} {...props} />
    </MantineProvider>,
  );
}

describe('StageReportEditor', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders markdown preview by default', () => {
    renderEditor();
    expect(screen.getByText('Findings here')).toBeInTheDocument();
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  });

  it('shows edit button for succeeded stages', () => {
    renderEditor({ status: 'succeeded' });
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
  });

  it('shows edit button for waiting_approval stages', () => {
    renderEditor({ status: 'waiting_approval' });
    expect(screen.getByRole('button', { name: /edit/i })).toBeInTheDocument();
  });

  it('hides edit button for pending stages', () => {
    renderEditor({ status: 'pending' });
    expect(screen.queryByRole('button', { name: /edit/i })).not.toBeInTheDocument();
  });

  it('switches to textarea on Edit click', () => {
    renderEditor();
    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    expect(screen.getByRole('textbox')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
  });

  it('Cancel reverts content and exits edit mode', () => {
    renderEditor();
    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    const textarea = screen.getByRole('textbox');
    fireEvent.change(textarea, { target: { value: 'changed' } });
    // Find Cancel next to Save (in edit toolbar)
    const cancelBtn = screen.getAllByRole('button', { name: /cancel/i })[0];
    fireEvent.click(cancelBtn);
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.getByText('Findings here')).toBeInTheDocument();
  });

  it('Save calls PATCH API and exits edit mode', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ version: 1 }), { status: 200 }),
    );

    renderEditor();
    fireEvent.click(screen.getByRole('button', { name: /edit/i }));
    fireEvent.click(screen.getByRole('button', { name: /save/i }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledWith(
        '/api/v1/pipelines/run-1/stages/stage-1/report',
        expect.objectContaining({ method: 'PATCH' }),
      );
    });

    await waitFor(() => {
      expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    });
  });

  it('Regenerate panel opens on button click', async () => {
    renderEditor();
    // Open regenerate panel
    const regenButtons = screen.getAllByRole('button', { name: /regenerate/i });
    fireEvent.click(regenButtons[0]);

    // Guidance input should appear (inside Collapse)
    await waitFor(() => {
      expect(screen.getByPlaceholderText(/Focus more on/)).toBeInTheDocument();
    });
  });

  it('History loads and displays versions', async () => {
    const versions = [
      { version: 1, content: 'v1', editor: 'user', type: 'edit', timestamp: '2026-01-01T00:00:00Z' },
    ];
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(versions), { status: 200 }),
    );

    renderEditor();
    fireEvent.click(screen.getByRole('button', { name: /history/i }));

    await waitFor(() => {
      expect(screen.getByText('v1')).toBeInTheDocument();
      expect(screen.getByText('user')).toBeInTheDocument();
    });
  });
});
