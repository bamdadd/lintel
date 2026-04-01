import { Handle, Position, type NodeProps } from '@xyflow/react';
import {
  IconFile, IconFileText, IconCode, IconPhoto, IconFileZip,
  IconDownload, IconDatabase, IconCloud,
} from '@tabler/icons-react';
import type { ArtifactNodeData } from './types';
import styles from './ArtifactNode.module.css';

const MIME_ICONS: Record<string, React.ElementType> = {
  'text/plain': IconFileText,
  'text/markdown': IconFileText,
  'application/json': IconCode,
  'text/x-diff': IconCode,
  'image/png': IconPhoto,
  'image/jpeg': IconPhoto,
  'application/zip': IconFileZip,
};

function getMimeIcon(mimeType?: string): React.ElementType {
  if (!mimeType) return IconFile;
  return MIME_ICONS[mimeType] ?? IconFile;
}

function formatSize(bytes?: number): string | null {
  if (bytes == null) return null;
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ArtifactNode({ data }: NodeProps & { data: ArtifactNodeData }) {
  const MimeIcon = getMimeIcon(data.mimeType);
  const StorageIcon = data.storageBackend === 's3' ? IconCloud : IconDatabase;
  const size = formatSize(data.sizeBytes);

  return (
    <div className={styles.artifact}>
      <Handle type="target" position={Position.Left} className={styles.handle} />
      <div className={styles.content}>
        <div className={styles.header}>
          <MimeIcon size={14} color="#a78bfa" stroke={1.8} />
          <span className={styles.name}>{data.label}</span>
        </div>
        <div className={styles.meta}>
          {data.mimeType && (
            <span className={styles.mimeType}>{data.mimeType}</span>
          )}
          {size && <span className={styles.size}>{size}</span>}
          <StorageIcon size={10} color="#6b7280" stroke={1.5} />
        </div>
        {data.previewUrl ? (
          <img src={data.previewUrl} alt={data.label} className={styles.preview} />
        ) : data.downloadUrl ? (
          <a
            href={data.downloadUrl}
            className={styles.download}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
          >
            <IconDownload size={10} stroke={1.5} />
            Download
          </a>
        ) : null}
      </div>
      <Handle type="source" position={Position.Right} className={styles.handle} />
    </div>
  );
}
