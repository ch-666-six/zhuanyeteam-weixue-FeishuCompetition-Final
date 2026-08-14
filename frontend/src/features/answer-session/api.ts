import type { CoachingRecord, FinalEvaluationResult, InitialAnalysisResult, SessionSnapshot } from '../../shared/api/types'
import { API_BASE_URL, request } from '../../shared/api/http'

export function createSession(token: string, assignmentId: string, idempotencyKey: string): Promise<SessionSnapshot> {
  return request('/sessions', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({ assignment_id: assignmentId }),
  })
}

export function getInitialAnalysis(token: string, sessionId: string): Promise<InitialAnalysisResult> {
  return request(`/sessions/${sessionId}/initial-analysis`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

export function retryInitialAnalysis(token: string, sessionId: string, idempotencyKey: string): Promise<SessionSnapshot> {
  return request(`/sessions/${sessionId}/initial-analysis/retry`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Idempotency-Key': idempotencyKey },
  })
}

export function startFinalDraft(
  token: string, sessionId: string, expectedVersion: number, idempotencyKey: string,
): Promise<SessionSnapshot> {
  return request(`/sessions/${sessionId}/final-draft`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ expected_version: expectedVersion }),
  })
}

export function startCoaching(token: string, sessionId: string, expectedVersion: number, idempotencyKey: string): Promise<SessionSnapshot> {
  return request(`/sessions/${sessionId}/coaching/start`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ expected_version: expectedVersion }),
  })
}

export function getCoaching(token: string, sessionId: string): Promise<CoachingRecord> {
  return request(`/sessions/${sessionId}/coaching`, { headers: { Authorization: `Bearer ${token}` } })
}

export function submitCoachingResponse(token: string, sessionId: string, turnId: string, answer: string, expectedVersion: number, idempotencyKey: string): Promise<SessionSnapshot> {
  return request(`/sessions/${sessionId}/coaching/turns/${turnId}/response`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ answer, expected_version: expectedVersion }),
  })
}

export function endCoaching(token: string, sessionId: string, expectedVersion: number, idempotencyKey: string): Promise<SessionSnapshot> {
  return request(`/sessions/${sessionId}/coaching/end`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ expected_version: expectedVersion }),
  })
}

export function retryCoachingQuestion(token: string, sessionId: string, expectedVersion: number, idempotencyKey: string): Promise<SessionSnapshot> {
  return request(`/sessions/${sessionId}/coaching/question/retry`, {
    method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ expected_version: expectedVersion }),
  })
}

export async function streamCoachingQuestion(token: string, sessionId: string, turnId: string, onDelta: (text: string) => void, signal?: AbortSignal): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/sessions/${sessionId}/coaching/turns/${turnId}/stream`, {
    headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' }, signal,
  })
  if (!response.ok || !response.body) throw new Error('辅导问题暂时无法读取。')
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value, { stream: !done })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() ?? ''
    for (const block of blocks) {
      const event = block.split('\n').find((line) => line.startsWith('event:'))?.slice(6).trim()
      const data = block.split('\n').find((line) => line.startsWith('data:'))?.slice(5).trim()
      if (event === 'delta' && data) onDelta(JSON.parse(data).text)
    }
    if (done) break
  }
}

export function submitFinalAnswer(
  token: string, sessionId: string, answer: string, expectedVersion: number, idempotencyKey: string,
): Promise<SessionSnapshot> {
  return request(`/sessions/${sessionId}/final-answer`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ answer, expected_version: expectedVersion }),
  })
}

export function getFinalEvaluation(token: string, sessionId: string): Promise<FinalEvaluationResult> {
  return request(`/sessions/${sessionId}/final-evaluation`, { headers: { Authorization: `Bearer ${token}` } })
}

export function retryFinalEvaluation(
  token: string, sessionId: string, expectedVersion: number, idempotencyKey: string,
): Promise<SessionSnapshot> {
  return request(`/sessions/${sessionId}/final-evaluation/retry`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify({ expected_version: expectedVersion }),
  })
}

export function getSession(token: string, sessionId: string): Promise<SessionSnapshot> {
  return request(`/sessions/${sessionId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

export function submitInitialAnswer(
  token: string,
  sessionId: string,
  answer: string,
  expectedVersion: number,
  idempotencyKey: string,
): Promise<SessionSnapshot> {
  return request(`/sessions/${sessionId}/initial-answer`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Idempotency-Key': idempotencyKey,
    },
    body: JSON.stringify({ answer, expected_version: expectedVersion }),
  })
}
