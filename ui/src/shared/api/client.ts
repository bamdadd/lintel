export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;
  readonly correlationId?: string;

  constructor(status: number, detail: string, correlationId?: string) {
    super(detail);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.correlationId = correlationId;
  }
}

function getBaseUrl(): string {
  if (typeof window === 'undefined') return '';
  const { hostname, protocol } = window.location;
  // In dev, if not on localhost, talk to the API on port 8000 directly
  if (hostname !== 'localhost' && hostname !== '127.0.0.1') {
    return `${protocol}//${hostname}:8000`;
  }
  return '';
}

export async function customInstance<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(`${getBaseUrl()}${url}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Correlation-ID': globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2),
      ...options?.headers,
    },
  });

  const correlationId =
    response.headers.get('X-Correlation-ID') ?? undefined;

  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new ApiError(
      response.status,
      (body as { detail?: string }).detail ?? response.statusText,
      correlationId,
    );
  }

  if (response.status === 204) return undefined as T;

  const data = await response.json();
  return { data, status: response.status, headers: response.headers } as T;
}
