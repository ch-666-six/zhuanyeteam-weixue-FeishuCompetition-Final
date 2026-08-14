import { request } from '../../shared/api/http'
import type { GrowthReport } from '../../shared/api/types'

export function getGrowthReport(token: string, grade: number | null): Promise<GrowthReport> {
  return request(`/growth?grade=${grade ?? 'all'}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
}
