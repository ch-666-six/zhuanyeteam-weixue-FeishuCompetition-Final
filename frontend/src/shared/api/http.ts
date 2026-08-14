export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly snapshot?: SessionSnapshot,
  ) {
    super(message)
  }
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init.headers,
    },
  })

  if (!response.ok) {
    const body = await response.json().catch(() => null)
    const detail = body?.detail ?? body
    throw new ApiError(
      detail?.message ?? '暂时无法完成请求，请稍后重试。',
      response.status,
      detail?.code ?? 'UNKNOWN_ERROR',
      detail?.snapshot,
    )
  }
  return response.json() as Promise<T>
}
import type { SessionSnapshot } from './types'
