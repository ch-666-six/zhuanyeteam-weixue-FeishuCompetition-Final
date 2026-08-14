import { useEffect, useState } from 'react'

function draftKey(studentId: string, assignmentId: string, sessionId: string, phase: string, inputVersion: number): string {
  return `weixue-draft:${studentId}:${assignmentId}:${sessionId}:${phase}:${inputVersion}`
}

export function useAnswerDraft(
  studentId: string, assignmentId: string, sessionId: string, phase = 'INITIAL_DRAFT', inputVersion = 1,
) {
  const key = draftKey(studentId, assignmentId, sessionId, phase, inputVersion)
  const [value, setValue] = useState(() => localStorage.getItem(key) ?? '')

  useEffect(() => {
    setValue(localStorage.getItem(key) ?? '')
  }, [key])

  useEffect(() => {
    if (value) localStorage.setItem(key, value)
    else localStorage.removeItem(key)
  }, [key, value])

  return {
    value,
    setValue,
    clear: () => {
      localStorage.removeItem(key)
      setValue('')
    },
  }
}
