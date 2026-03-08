import { useState, useCallback } from 'react';
import {
  Stack, Group, Text, Button, Paper, Textarea, ScrollArea, Badge,
  Collapse, TextInput, Divider,
} from '@mantine/core';
import {
  IconPencil, IconDeviceFloppy, IconRefresh, IconHistory, IconX,
} from '@tabler/icons-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import '../../chat/chat-markdown.css';
import { TimeAgo } from '@/shared/components/TimeAgo';

interface ReportVersion {
  version: number;
  content: string;
  editor: string;
  type: string;
  timestamp: string;
}

interface StageReportEditorProps {
  runId: string;
  stageId: string;
  stageName: string;
  initialContent: string;
  status: string;
}

export function StageReportEditor({
  runId,
  stageId,
  stageName,
  initialContent,
  status,
}: StageReportEditorProps) {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(initialContent);
  const [saving, setSaving] = useState(false);
  const [savedVersion, setSavedVersion] = useState<number | null>(null);

  const [showRegenerate, setShowRegenerate] = useState(false);
  const [guidance, setGuidance] = useState('');
  const [regenerating, setRegenerating] = useState(false);

  const [showHistory, setShowHistory] = useState(false);
  const [versions, setVersions] = useState<ReportVersion[]>([]);
  const [loadingVersions, setLoadingVersions] = useState(false);

  const canEdit = status === 'succeeded' || status === 'waiting_approval';

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const res = await fetch(
        `/api/v1/pipelines/${runId}/stages/${stageId}/report`,
        {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content, editor: 'user' }),
        },
      );
      if (res.ok) {
        const data = await res.json();
        setSavedVersion(data.version);
        setEditing(false);
      }
    } finally {
      setSaving(false);
    }
  }, [runId, stageId, content]);

  const handleRegenerate = useCallback(async () => {
    setRegenerating(true);
    try {
      await fetch(
        `/api/v1/pipelines/${runId}/stages/${stageId}/regenerate`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ guidance }),
        },
      );
      setShowRegenerate(false);
      setGuidance('');
    } finally {
      setRegenerating(false);
    }
  }, [runId, stageId, guidance]);

  const handleLoadVersions = useCallback(async () => {
    if (showHistory) {
      setShowHistory(false);
      return;
    }
    setLoadingVersions(true);
    try {
      const res = await fetch(
        `/api/v1/pipelines/${runId}/stages/${stageId}/report/versions`,
      );
      if (res.ok) {
        setVersions(await res.json());
      }
    } finally {
      setLoadingVersions(false);
      setShowHistory(true);
    }
  }, [runId, stageId, showHistory]);

  return (
    <Stack gap="sm">
      <Group justify="space-between">
        <Text size="sm" fw={600}>
          {stageName.includes('research') ? 'Research Report' : 'Plan'}
        </Text>
        <Group gap="xs">
          {savedVersion && (
            <Badge size="sm" variant="light" color="teal">v{savedVersion}</Badge>
          )}
          {canEdit && !editing && (
            <Button
              variant="light"
              size="compact-xs"
              leftSection={<IconPencil size={12} />}
              onClick={() => setEditing(true)}
            >
              Edit
            </Button>
          )}
          {canEdit && (
            <Button
              variant="light"
              size="compact-xs"
              leftSection={<IconRefresh size={12} />}
              onClick={() => setShowRegenerate((v) => !v)}
            >
              Regenerate
            </Button>
          )}
          <Button
            variant="subtle"
            size="compact-xs"
            leftSection={<IconHistory size={12} />}
            loading={loadingVersions}
            onClick={handleLoadVersions}
          >
            History
          </Button>
        </Group>
      </Group>

      {editing ? (
        <Stack gap="xs">
          <Textarea
            value={content}
            onChange={(e) => setContent(e.currentTarget.value)}
            autosize
            minRows={8}
            maxRows={30}
            styles={{ input: { fontFamily: 'monospace', fontSize: 13 } }}
          />
          <Group gap="xs">
            <Button
              size="compact-sm"
              leftSection={<IconDeviceFloppy size={14} />}
              loading={saving}
              onClick={handleSave}
            >
              Save
            </Button>
            <Button
              variant="subtle"
              size="compact-sm"
              leftSection={<IconX size={14} />}
              onClick={() => {
                setContent(initialContent);
                setEditing(false);
              }}
            >
              Cancel
            </Button>
          </Group>
        </Stack>
      ) : (
        <Paper withBorder p="sm">
          <ScrollArea.Autosize mah={500}>
            <div className="chat-markdown" style={{ fontSize: 13 }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {content}
              </ReactMarkdown>
            </div>
          </ScrollArea.Autosize>
        </Paper>
      )}

      {/* Regenerate section */}
      <Collapse in={showRegenerate}>
        <Paper withBorder p="sm">
          <Stack gap="xs">
            <Text size="sm" fw={500}>Regenerate with guidance</Text>
            <TextInput
              placeholder="e.g. Focus more on security considerations..."
              value={guidance}
              onChange={(e) => setGuidance(e.currentTarget.value)}
            />
            <Group gap="xs">
              <Button
                size="compact-sm"
                color="orange"
                loading={regenerating}
                onClick={handleRegenerate}
              >
                Regenerate
              </Button>
              <Button
                variant="subtle"
                size="compact-sm"
                onClick={() => setShowRegenerate(false)}
              >
                Cancel
              </Button>
            </Group>
          </Stack>
        </Paper>
      </Collapse>

      {/* Version history */}
      <Collapse in={showHistory}>
        <Paper withBorder p="sm">
          <Stack gap="xs">
            <Text size="sm" fw={500}>Version History</Text>
            {versions.length === 0 ? (
              <Text size="xs" c="dimmed">No versions recorded yet</Text>
            ) : (
              versions.map((v) => (
                <Group key={v.version} justify="space-between" gap="xs">
                  <Group gap="xs">
                    <Badge size="xs" variant="light">v{v.version}</Badge>
                    <Badge size="xs" variant="dot" color={v.type === 'regenerate' ? 'orange' : 'blue'}>
                      {v.type}
                    </Badge>
                    <Text size="xs" c="dimmed">{v.editor}</Text>
                  </Group>
                  <TimeAgo date={v.timestamp} size="xs" c="dimmed" />
                </Group>
              ))
            )}
          </Stack>
        </Paper>
      </Collapse>
    </Stack>
  );
}
