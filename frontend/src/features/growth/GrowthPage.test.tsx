import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { GrowthReport } from '../../shared/api/types'
import type { AuthSession } from '../auth/auth'
import { GrowthPage } from './GrowthPage'


const auth: AuthSession = {
  token: 'demo-token',
  student: { id: 'student-3', display_name: '3年级体验学生', grade: 3 },
}

const report: GrowthReport = {
  selected_grade: null,
  student_grade: 3,
  coverage: { completed_assignments: 3, trend_eligible_assignments: 3, available_grades: [2, 3] },
  dimensions: ['思辨态度', '信息判别', '逻辑推理', '论证建构', '思辨表达'].map((name, index) => ({
    key: ['attitude', 'information', 'reasoning', 'argument', 'expression'][index] as GrowthReport['dimensions'][number]['key'],
    name,
    current_level: '表达清楚',
    current_value: 3,
    stable_level: '正在发展',
    evidence_count: 3,
    summary: `已在多份可比较记录中形成${name}的连续观察。`,
    points: [1, 2, 3].map((level, pointIndex) => ({
      session_id: `session-${index}-${pointIndex}`,
      assignment_id: `assignment-${pointIndex}`,
      assignment_title: `成长作业 ${pointIndex + 1}`,
      submitted_at: `2026-0${pointIndex + 2}-01T00:00:00Z`,
      grade: pointIndex === 0 ? 2 : 3,
      level: (['暂未体现', '正在发展', '表达清楚'] as const)[level - 1],
      level_value: level as 1 | 2 | 3,
      eligible: true,
      quote: `第 ${pointIndex + 1} 份原文证据`,
      observation: '能够找到对应原文。',
    })),
  })),
  timeline: [{
    session_id: 'session-0-2', assignment_id: 'assignment-2', assignment_title: '成长作业 3',
    submitted_at: '2026-04-01T00:00:00Z', grade: 3, used_coaching: true, coaching_rounds: 2,
    status: 'INCLUDED', representative_dimensions: ['思辨态度', '论证建构'], quote: '第 3 份原文证据',
  }],
  thinking_moves: ['说出看法', '说出为什么', '用材料支撑', '看见别的想法', '回应不同想法', '说清条件'].map((name, index) => ({
    key: `move-${index}`, name, student_label: `我会${name}`, count: index < 3 ? 2 : 0,
    evidence: index < 3 ? [{ session_id: 'session-0-2', assignment_title: '成长作业 3', quote: '第 3 份原文证据' }] : [],
  })),
  narrative: '已经根据 3 份已完成作业整理五维成长证据。',
  teacher_confirmation: { available: false, confirmed_count: 0, total_count: 3 },
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/growth']}>
        <GrowthPage auth={auth} onLogout={vi.fn()} />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('GrowthPage', () => {
  afterEach(() => cleanup())

  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => report }))
  })

  it('shows the complete date trajectory without assignment details', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: '按日期的五维成长折线图' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /横轴为实际完成日期/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '跨全部记录的整体观察' })).toBeInTheDocument()
    expect(screen.getByText('已完成记录')).toBeInTheDocument()
    expect(screen.queryByText('成长作业 3')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '作业学习轨迹' })).not.toBeInTheDocument()
  })

  it('always requests the complete trajectory', async () => {
    renderPage()
    await screen.findByRole('heading', { name: '按日期的五维成长折线图' })
    await waitFor(() => expect(fetch).toHaveBeenCalledWith('/api/v1/growth?grade=all', expect.anything()))
    expect(screen.queryByText('按年级查看')).not.toBeInTheDocument()
    expect(screen.queryByRole('combobox', { name: '年级' })).not.toBeInTheDocument()
  })
})
