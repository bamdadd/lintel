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

export async function customInstance<T>({
  url,
  method,
  params,
  data,
  headers,
}: {
  url: string;
  method: string;
  params?: Record<string, string>;
  data?: unknown;
  headers?: Record<string, string>;
}): Promise<T> {
  const searchParams = params ? `?${new URLSearchParams(params)}` : '';
  const response = await fetch(`${url}${searchParams}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      'X-Correlation-ID': crypto.randomUUID(),
      ...headers,
    },
    ...(data ? { body: JSON.stringify(data) } : {}),
  });

  const correlationId =
    response.headers.get('X-Correlation-ID') ?? undefined;

  if (!response.ok) {
    const body = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new ApiError(
      response.status,
      body.detail ?? response.statusText,
      correlationId,
    );
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
