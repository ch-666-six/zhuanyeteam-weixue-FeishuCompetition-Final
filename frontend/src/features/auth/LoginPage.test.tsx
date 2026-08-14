import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { LoginPage } from './LoginPage'

describe('LoginPage', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        { id: 'student-1', display_name: '1年级体验学生', grade: 1 },
        { id: 'student-2', display_name: '2年级体验学生', grade: 2 },
      ],
    }))
  })

  it('shows grade choices returned by the API', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <LoginPage onLogin={vi.fn()} />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    expect(await screen.findAllByRole('radio')).toHaveLength(2)
    expect(screen.getByRole('radio', { name: /1\s*年级/ })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /2\s*年级/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /题目管理/ })).toHaveAttribute('href', '/question-management')
    expect(screen.getByRole('button', { name: /进入学习空间/ })).toBeEnabled()
  })
})
