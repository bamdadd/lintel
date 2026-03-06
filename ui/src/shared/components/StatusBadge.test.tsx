import { render, screen } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { StatusBadge } from './StatusBadge';
import { describe, it, expect } from 'vitest';

function renderWithMantine(ui: React.ReactElement) {
  return render(<MantineProvider>{ui}</MantineProvider>);
}

describe('StatusBadge', () => {
  it('renders the status text', () => {
    renderWithMantine(<StatusBadge status="active" />);
    expect(screen.getByText('active')).toBeInTheDocument();
  });

  it('renders unknown status with gray fallback', () => {
    renderWithMantine(<StatusBadge status="custom_status" />);
    expect(screen.getByText('custom_status')).toBeInTheDocument();
  });
});
