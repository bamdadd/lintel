import { useEffect, useRef, useState, useCallback } from 'react';
import { Paper, Text, Center, Loader, ActionIcon, Group } from '@mantine/core';
import { IconZoomIn, IconZoomOut, IconZoomReset } from '@tabler/icons-react';
import mermaid from 'mermaid';

let mermaidInitialized = false;

interface MermaidDiagramProps {
  source: string;
  title?: string;
}

const MIN_ZOOM = 0.25;
const MAX_ZOOM = 3;
const ZOOM_STEP = 0.15;

export function MermaidDiagram({ source, title }: MermaidDiagramProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const dragRef = useRef<{ startX: number; startY: number; panX: number; panY: number } | null>(
    null,
  );

  useEffect(() => {
    if (!mermaidInitialized) {
      mermaid.initialize({
        startOnLoad: false,
        theme: 'dark',
        securityLevel: 'strict',
        fontFamily: 'inherit',
      });
      mermaidInitialized = true;
    }

    const id = `mermaid-${Math.random().toString(36).slice(2, 10)}`;

    async function render() {
      if (!containerRef.current) return;
      setLoading(true);
      setError(null);
      try {
        // Strip YAML frontmatter and sanitize invalid participant names
        let cleaned = source.replace(/^---\n[\s\S]*?\n---\n?/, '').trim();
        // Remove lines with <unknown> or other angle-bracket participants
        cleaned = cleaned
          .split('\n')
          .filter((line) => !/<[^>]*>/.test(line))
          .join('\n');
        const { svg } = await mermaid.render(id, cleaned);
        if (containerRef.current) {
          containerRef.current.innerHTML = svg;
          // Make SVG fill container
          const svgEl = containerRef.current.querySelector('svg');
          if (svgEl) {
            svgEl.style.maxWidth = 'none';
            svgEl.style.height = 'auto';
          }
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to render diagram');
      } finally {
        setLoading(false);
      }
    }

    setZoom(1);
    setPan({ x: 0, y: 0 });
    void render();
  }, [source]);

  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (e.ctrlKey || e.metaKey) {
      e.preventDefault();
      setZoom((z) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z - e.deltaY * 0.005)));
    } else {
      // Pan with scroll
      setPan((p) => ({ x: p.x - e.deltaX, y: p.y - e.deltaY }));
    }
  }, []);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (e.button !== 0) return;
      dragRef.current = { startX: e.clientX, startY: e.clientY, panX: pan.x, panY: pan.y };
      e.preventDefault();
    },
    [pan],
  );

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragRef.current) return;
    setPan({
      x: dragRef.current.panX + (e.clientX - dragRef.current.startX),
      y: dragRef.current.panY + (e.clientY - dragRef.current.startY),
    });
  }, []);

  const handleMouseUp = useCallback(() => {
    dragRef.current = null;
  }, []);

  return (
    <Paper p="md" withBorder>
      <Group justify="space-between" mb="sm">
        {title ? (
          <Text fw={600} size="sm">
            {title}
          </Text>
        ) : (
          <div />
        )}
        <Group gap={4}>
          <ActionIcon
            variant="subtle"
            size="sm"
            color="gray"
            onClick={() => setZoom((z) => Math.min(MAX_ZOOM, z + ZOOM_STEP))}
            aria-label="Zoom in"
          >
            <IconZoomIn size={16} />
          </ActionIcon>
          <ActionIcon
            variant="subtle"
            size="sm"
            color="gray"
            onClick={() => setZoom((z) => Math.max(MIN_ZOOM, z - ZOOM_STEP))}
            aria-label="Zoom out"
          >
            <IconZoomOut size={16} />
          </ActionIcon>
          <ActionIcon
            variant="subtle"
            size="sm"
            color="gray"
            onClick={() => {
              setZoom(1);
              setPan({ x: 0, y: 0 });
            }}
            aria-label="Reset zoom"
          >
            <IconZoomReset size={16} />
          </ActionIcon>
          <Text size="xs" c="dimmed" w={40} ta="right">
            {Math.round(zoom * 100)}%
          </Text>
        </Group>
      </Group>
      {loading && (
        <Center py="md">
          <Loader size="sm" />
        </Center>
      )}
      {error && (
        <Text c="red" size="sm">
          {error}
        </Text>
      )}
      <div
        ref={viewportRef}
        onWheel={handleWheel}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{
          overflow: 'hidden',
          height: 500,
          cursor: dragRef.current ? 'grabbing' : 'grab',
          borderRadius: 'var(--mantine-radius-sm)',
          background: 'var(--mantine-color-dark-7, #1a1b1e)',
        }}
      >
        <div
          ref={containerRef}
          style={{
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: '0 0',
            transition: dragRef.current ? 'none' : 'transform 100ms ease-out',
          }}
        />
      </div>
    </Paper>
  );
}
