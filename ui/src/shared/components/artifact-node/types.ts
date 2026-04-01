export interface ArtifactNodeData {
  label: string;
  mimeType?: string;
  sizeBytes?: number;
  storageBackend?: 'postgres' | 's3';
  previewUrl?: string;
  downloadUrl?: string;
  [key: string]: unknown;
}
