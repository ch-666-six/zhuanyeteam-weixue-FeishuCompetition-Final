import type { SessionNextView, SessionSnapshot } from '../../shared/api/types'

const viewRoutes: Record<SessionNextView, (sessionId: string) => string> = {
  INITIAL_DRAFT: (sessionId) => `/sessions/${sessionId}/initial-answer`,
  INITIAL_ANALYSIS_PENDING: (sessionId) => `/sessions/${sessionId}/analysis-pending`,
  INITIAL_ANALYSIS: (sessionId) => `/sessions/${sessionId}/initial-analysis`,
  COACHING_PENDING: (sessionId) => `/sessions/${sessionId}/coaching-pending`,
  COACHING: (sessionId) => `/sessions/${sessionId}/coaching`,
  FINAL_DRAFT: (sessionId) => `/sessions/${sessionId}/final-answer`,
  FINAL_EVALUATION_PENDING: (sessionId) => `/sessions/${sessionId}/evaluation-pending`,
  RESULT: (sessionId) => `/sessions/${sessionId}/result`,
}

export function sessionRoute(snapshot: SessionSnapshot): string {
  return viewRoutes[snapshot.next_view](snapshot.id)
}
