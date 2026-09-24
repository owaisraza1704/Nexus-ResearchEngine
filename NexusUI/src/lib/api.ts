import useSWR from 'swr';

export const API_BASE = '/api/backend';
export class ApiError extends Error {
  constructor(
    message: string,
    public code: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(API_BASE + path, {
      ...init,
      headers: {
        ...(init?.body && !(init.body instanceof FormData)
          ? { 'Content-Type': 'application/json' }
          : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      'Cannot reach the local backend. Check that the API is running.',
      'BACKEND_UNAVAILABLE',
      0,
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = Array.isArray(body?.detail)
      ? body.detail.map((item: { msg: string }) => item.msg).join('; ')
      : null;
    throw new ApiError(
      body?.error?.message || detail || 'The local backend could not complete this request.',
      body?.error?.code || 'REQUEST_FAILED',
      response.status,
    );
  }
  return response.json();
}
export function useApi<T>(path: string | null, refreshInterval = 0) {
  return useSWR<T, ApiError>(path, api<T>, {
    refreshInterval,
    shouldRetryOnError: false,
    revalidateOnFocus: true,
  });
}
