import type { AssignmentDetail, AssignmentSummary } from '../../shared/api/types'
import { request } from '../../shared/api/http'

export function listAssignments(token: string): Promise<AssignmentSummary[]> {
  return request('/assignments', {
    headers: { Authorization: `Bearer ${token}` },
  })
}

export function getAssignment(token: string, assignmentId: string): Promise<AssignmentDetail> {
  return request(`/assignments/${assignmentId}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}

