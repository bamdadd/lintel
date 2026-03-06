import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { EmptyState } from './EmptyState';
import { describe, it, expect, vi } from 'vitest';

function renderWithMantine(ui: React.ReactElement) {
  return render(<MantineProvider>{ui}</MantineProvider>);
}

describe('EmptyState', () => {
  it('renders title and description', () => {
    renderWithMantine(
      <EmptyState title="No data" description="Nothing here yet" />,
    );
    expect(screen.getByText('No data')).toBeInTheDocument();
    expect(screen.getByText('Nothing here yet')).toBeInTheDocument();
  });

  it('renders action button when provided', () => {
    const onAction = vi.fn();
    renderWithMantine(
      <EmptyState
        title="Empty"
        description="Desc"
        actionLabel="Add Item"
        onAction={onAction}
      />,
    );
    expect(screen.getByText('Add Item')).toBeInTheDocument();
  });

  it('does not render button when no action', () => {
    renderWithMantine(<EmptyState title="Empty" description="Desc" />);
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });
});
