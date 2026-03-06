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

export async function customInstance<T>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-Correlation-ID': crypto.randomUUID(),
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
