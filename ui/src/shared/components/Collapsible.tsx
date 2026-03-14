/**
 * Collapsible — a generic accessible expand/collapse primitive.
 *
 * Uses Mantine's Collapse for the CSS grid-row animation and @tabler/icons-react
 * for the chevron, both of which are already project dependencies.
 *
 * Accessibility:
 *  - Toggle button carries aria-expanded and aria-controls
 *  - Content region carries a matching id and role="region" with aria-labelledby
 *  - Fully keyboard-navigable (button is a native <button>)
 */

import { useId, useState } from 'react';
import { Collapse, Group, Text } from '@mantine/core';
import { IconChevronDown } from '@tabler/icons-react';

export interface CollapsibleProps {
  /** Section heading shown in the toggle bar */
  title: string;
  /** Content rendered inside the collapsible region */
  children: React.ReactNode;
  /** Whether the section starts open. Defaults to false (collapsed). */
  defaultOpen?: boolean;
  /**
   * Optional badge / count element rendered to the right of the title
   * (e.g. a Mantine Badge showing the number of log lines).
   */
  badge?: React.ReactNode;
  /** Extra data-testid placed on the root wrapper for easy test selection. */
  'data-testid'?: string;
}

export function Collapsible({
  title,
  children,
  defaultOpen = false,
  badge,
  'data-testid': testId,
}: CollapsibleProps) {
  const [open, setOpen] = useState(defaultOpen);

  // Stable IDs for aria wiring — useId() is React 18+
  const uid = useId();
  const triggerId = `collapsible-trigger-${uid}`;
  const regionId = `collapsible-region-${uid}`;

  return (
    <div data-testid={testId}>
      {/* ── Toggle bar ──────────────────────────────────────────────── */}
      <Group
        justify="space-between"
        px="xs"
        py={6}
        style={{
          borderRadius: 'var(--mantine-radius-sm)',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        className="collapsible-trigger"
        onClick={() => setOpen((v) => !v)}
        role="button"
        tabIndex={0}
        id={triggerId}
        aria-expanded={open}
        aria-controls={regionId}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            setOpen((v) => !v);
          }
        }}
        data-testid={testId ? `${testId}-trigger` : undefined}
      >
        <Group gap="xs">
          <Text size="sm" fw={600}>
            {title}
          </Text>
          {badge}
        </Group>

        {/* Chevron rotates 180° when open */}
        <IconChevronDown
          size={16}
          aria-hidden="true"
          style={{
            transition: 'transform 200ms ease',
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            flexShrink: 0,
          }}
        />
      </Group>

      {/* ── Animated content region ───────────────────────────────────── */}
      {/*
        Mantine's <Collapse> uses a CSS max-height transition internally,
        giving us a smooth expand/collapse without manual height measurement.
      */}
      <div
        id={regionId}
        role="region"
        aria-labelledby={triggerId}
        data-testid={testId ? `${testId}-region` : undefined}
      >
        <Collapse in={open} transitionDuration={250} transitionTimingFunction="ease">
          <div style={{ paddingTop: 4 }}>{children}</div>
        </Collapse>
      </div>
    </div>
  );
}
