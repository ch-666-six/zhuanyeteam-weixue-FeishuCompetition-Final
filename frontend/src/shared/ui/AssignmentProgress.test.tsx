import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { AssignmentProgress } from './AssignmentProgress'

describe('AssignmentProgress', () => {
  it('shows all six stages and identifies the current stage', () => {
    render(
      <MemoryRouter>
        <AssignmentProgress
          current="coaching"
          previousHref="/sessions/session-1/initial-analysis?review=1"
          resumeHref="/sessions/session-1/final-answer"
        />
      </MemoryRouter>,
    )

    const progress = screen.getByRole('navigation', { name: /第 4 \/ 6 阶段，当前为AI 追问/ })
    const stepList = within(progress).getByRole('list')
    expect(within(stepList).getByText('理解题目')).toBeInTheDocument()
    expect(within(stepList).getByText('独立初答')).toBeInTheDocument()
    expect(within(stepList).getByText('思考诊断')).toBeInTheDocument()
    expect(within(stepList).getByText('AI 追问')).toBeInTheDocument()
    expect(within(stepList).getByText('独立整理')).toBeInTheDocument()
    expect(within(stepList).getByText('成果反馈')).toBeInTheDocument()

    const currentStep = within(stepList).getByText('AI 追问').closest('li')
    expect(currentStep).toHaveAttribute('aria-current', 'step')
    expect(within(currentStep!).getByText('当前阶段')).toBeInTheDocument()
    expect(within(stepList).getAllByText('已完成')).toHaveLength(3)
    expect(within(progress).getByRole('link', { name: '查看上一步：思考诊断' })).toHaveAttribute(
      'href',
      '/sessions/session-1/initial-analysis?review=1',
    )
    expect(within(progress).getByRole('link', { name: '返回当前步骤' })).toHaveAttribute(
      'href',
      '/sessions/session-1/final-answer',
    )
  })
})
