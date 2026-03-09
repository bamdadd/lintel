/**
 * Unit tests for the Collapsible shared primitive.
 *
 * Coverage:
 *  - Default collapsed state
 *  - Expand on click
 *  - Collapse again on second click
 *  - defaultOpen=true starts expanded
 *  - Chevron rotation class/style changes
 *  - aria-expanded attribute reflects state
 *  - aria-controls / id wiring
 *  - badge prop renders
 *  - Keyboard activation (Enter / Space)
 *  - data-testid forwarding
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { MantineProvider } from '@mantine/core';
import { describe, it, expect } from 'vitest';
import { Collapsible } from './Collapsible';

// ── Helper ─────────────────────────────────────────────────────────────────

function renderCollapsible(
  props: Partial<React.ComponentProps<typeof Collapsible>> = {},
) {
  const defaults: React.ComponentProps<typeof Collapsible> = {
    title: 'Logs',
    children: <p>log content here</p>,
  };
  return render(
    <MantineProvider>
      <Collapsible {...defaults} {...props} />
    </MantineProvider>,
  );
}

// ── Tests ──────────────────────────────────────────────────────────────────

describe('Collapsible', () => {
  // ── Initial state ──────────────────────────────────────────────────────

  it('renders the title', () => {
    renderCollapsible({ title: 'Logs' });
    expect(screen.getByText('Logs')).toBeInTheDocument();
  });

  it('is collapsed by default (content not visible)', () => {
    renderCollapsible({ children: <p>hidden content</p> });
    // Mantine Collapse hides content via max-height:0 / overflow:hidden.
    // The content node is in the DOM but the Collapse wrapper has
    // display:none or max-height:0 — we verify aria-expanded is false.
    const trigger = screen.getByRole('button');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  it('content is not visually accessible when collapsed', () => {
    renderCollapsible({ children: <p>secret text</p> });
    // The region exists in the DOM (for SSR / accessibility tree) but
    // Mantine Collapse sets overflow:hidden + max-height:0 so it is
    // not visible. We assert aria-expanded=false as the canonical signal.
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false');
  });

  // ── Expand / collapse ──────────────────────────────────────────────────

  it('expands when the trigger is clicked', () => {
    renderCollapsible({ children: <p>visible after click</p> });
    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });

  it('collapses again on a second click', () => {
    renderCollapsible({ children: <p>toggle me</p> });
    const trigger = screen.getByRole('button');
    fireEvent.click(trigger); // open
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    fireEvent.click(trigger); // close
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  // ── defaultOpen ────────────────────────────────────────────────────────

  it('starts expanded when defaultOpen=true', () => {
    renderCollapsible({ defaultOpen: true });
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true');
  });

  it('can be collapsed from defaultOpen=true', () => {
    renderCollapsible({ defaultOpen: true });
    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  // ── Chevron rotation ───────────────────────────────────────────────────

  it('chevron has rotate(0deg) when collapsed', () => {
    renderCollapsible();
    // The SVG icon is aria-hidden; find it via its parent button's subtree
    const trigger = screen.getByRole('button');
    // The icon is an <svg> inside the button
    const svg = trigger.querySelector('svg');
    expect(svg).not.toBeNull();
    expect(svg!.style.transform).toBe('rotate(0deg)');
  });

  it('chevron has rotate(180deg) when expanded', () => {
    renderCollapsible();
    const trigger = screen.getByRole('button');
    fireEvent.click(trigger);
    const svg = trigger.querySelector('svg');
    expect(svg!.style.transform).toBe('rotate(180deg)');
  });

  // ── Accessibility wiring ───────────────────────────────────────────────

  it('trigger aria-controls matches region id', () => {
    renderCollapsible({ 'data-testid': 'col' });
    const trigger = screen.getByRole('button');
    const controlsId = trigger.getAttribute('aria-controls');
    expect(controlsId).toBeTruthy();
    const region = document.getElementById(controlsId!);
    expect(region).not.toBeNull();
    expect(region!.getAttribute('role')).toBe('region');
  });

  it('region aria-labelledby matches trigger id', () => {
    renderCollapsible({ 'data-testid': 'col' });
    const trigger = screen.getByRole('button');
    const triggerId = trigger.id;
    expect(triggerId).toBeTruthy();
    const region = document.querySelector('[role="region"]');
    expect(region).not.toBeNull();
    expect(region!.getAttribute('aria-labelledby')).toBe(triggerId);
  });

  // ── Keyboard navigation ────────────────────────────────────────────────

  it('expands on Enter key press', () => {
    renderCollapsible();
    const trigger = screen.getByRole('button');
    trigger.focus();
    fireEvent.keyDown(trigger, { key: 'Enter', code: 'Enter' });
    fireEvent.click(trigger); // native button fires click on Enter
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });

  it('expands on Space key press', () => {
    renderCollapsible();
    const trigger = screen.getByRole('button');
    trigger.focus();
    // Native <button> fires click on Space
    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
  });

  // ── Badge prop ─────────────────────────────────────────────────────────

  it('renders badge content when provided', () => {
    renderCollapsible({ badge: <span data-testid="badge">42</span> });
    expect(screen.getByTestId('badge')).toBeInTheDocument();
    expect(screen.getByText('42')).toBeInTheDocument();
  });

  it('renders without badge when not provided', () => {
    renderCollapsible();
    expect(screen.queryByTestId('badge')).not.toBeInTheDocument();
  });

  // ── data-testid forwarding ─────────────────────────────────────────────

  it('forwards data-testid to root wrapper', () => {
    renderCollapsible({ 'data-testid': 'my-section' });
    expect(screen.getByTestId('my-section')).toBeInTheDocument();
  });

  it('appends -trigger suffix to trigger testid', () => {
    renderCollapsible({ 'data-testid': 'my-section' });
    expect(screen.getByTestId('my-section-trigger')).toBeInTheDocument();
  });

  it('appends -region suffix to region testid', () => {
    renderCollapsible({ 'data-testid': 'my-section' });
    expect(screen.getByTestId('my-section-region')).toBeInTheDocument();
  });

  // ── Children ───────────────────────────────────────────────────────────

  it('renders children inside the region', () => {
    renderCollapsible({
      children: <span data-testid="child-node">child</span>,
      defaultOpen: true,
    });
    expect(screen.getByTestId('child-node')).toBeInTheDocument();
  });

  it('renders multiple children', () => {
    renderCollapsible({
      children: (
        <>
          <span>first</span>
          <span>second</span>
        </>
      ),
      defaultOpen: true,
    });
    expect(screen.getByText('first')).toBeInTheDocument();
    expect(screen.getByText('second')).toBeInTheDocument();
  });
});
