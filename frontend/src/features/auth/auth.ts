import type { DemoLoginResponse, DemoStudent } from '../../shared/api/types'
import { request } from '../../shared/api/http'

const AUTH_STORAGE_KEY = 'weixue-demo-auth'

export interface AuthSession {
  token: string
  student: DemoStudent
}

export function listDemoStudents(): Promise<DemoStudent[]> {
  return request('/demo/students')
}

export async function loginDemoStudent(studentId: string): Promise<AuthSession> {
  const response = await request<DemoLoginResponse>('/demo/login', {
    method: 'POST',
    body: JSON.stringify({ student_id: studentId }),
  })
  return { token: response.access_token, student: response.student }
}

export function readAuthSession(): AuthSession | null {
  try {
    const value = sessionStorage.getItem(AUTH_STORAGE_KEY)
    return value ? (JSON.parse(value) as AuthSession) : null
  } catch {
    sessionStorage.removeItem(AUTH_STORAGE_KEY)
    return null
  }
}

export function saveAuthSession(session: AuthSession): void {
  sessionStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(session))
}

export function clearAuthSession(): void {
  sessionStorage.removeItem(AUTH_STORAGE_KEY)
}

