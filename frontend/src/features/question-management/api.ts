import type { ManagedAssignment } from '../../shared/api/types'
import { request } from '../../shared/api/http'

export function listManagedAssignments(): Promise<ManagedAssignment[]> {
  return request('/question-management')
}

export function createManagedAssignment(input: { title: string; prompt: string; grades: number[] }): Promise<ManagedAssignment[]> {
  return request('/question-management', { method: 'POST', body: JSON.stringify(input) })
}

export function updateManagedAssignment(id: string, input: { title: string; prompt: string; grade: number }): Promise<ManagedAssignment> {
  return request(`/question-management/${id}`, { method: 'PUT', body: JSON.stringify(input) })
}

export interface BulkDeleteResult {
  deleted_ids: string[]
  blocked_ids: string[]
  not_found_ids: string[]
}

export function bulkDeleteManagedAssignments(ids: string[]): Promise<BulkDeleteResult> {
  return request('/question-management/bulk-delete', { method: 'POST', body: JSON.stringify({ ids }) })
}

export function deleteManagedAssignment(id: string): Promise<{ deleted: true }> {
  return request(`/question-management/${id}`, { method: 'DELETE' })
}
