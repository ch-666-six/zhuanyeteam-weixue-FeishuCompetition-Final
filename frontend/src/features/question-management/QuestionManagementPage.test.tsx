import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { QuestionManagementPage } from './QuestionManagementPage'

const question = {
  id: 'assignment-1', title: '校园里的安静角落', prompt: '学校里是否应该设置一个安静角落？',
  grade: 3, published_at: '2026-01-01T00:00:00Z', created_at: '2026-01-01T00:00:00Z',
}

describe('QuestionManagementPage', () => {
  afterEach(() => cleanup())

  it('lists and creates questions', async () => {
    const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => Promise.resolve({
      ok: true,
      json: async () => init?.method === 'POST' ? [{ ...question, id: 'assignment-2', title: '新的题目' }, { ...question, id: 'assignment-3', grade: 2, title: '新的题目' }] : [question],
    }))
    vi.stubGlobal('fetch', fetchMock)
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
    render(<QueryClientProvider client={queryClient}><MemoryRouter><QuestionManagementPage /></MemoryRouter></QueryClientProvider>)

    expect(await screen.findByRole('heading', { name: '校园里的安静角落' })).toBeInTheDocument()
    fireEvent.change(screen.getByRole('textbox', { name: '题目名称' }), { target: { value: '新的题目' } })
    fireEvent.change(screen.getByRole('textbox', { name: '题目内容' }), { target: { value: '请说明你对这件事的看法和理由。' } })
    fireEvent.click(screen.getByRole('checkbox', { name: /2 年级/ }))
    fireEvent.click(screen.getByRole('button', { name: '发布到 2 个年级' }))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/v1/question-management', expect.objectContaining({ method: 'POST' })))
    expect(await screen.findByText('题目已发布到 2 个年级。')).toBeInTheDocument()
  })

  it('filters and opens a question for editing', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => [question, { ...question, id: 'assignment-2', grade: 5 }] }))
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={queryClient}><MemoryRouter><QuestionManagementPage /></MemoryRouter></QueryClientProvider>)

    expect(await screen.findAllByRole('heading', { name: '校园里的安静角落' })).toHaveLength(2)
    fireEvent.change(screen.getByRole('combobox', { name: '筛选年级' }), { target: { value: '3' } })
    expect(screen.getAllByRole('heading', { name: '校园里的安静角落' })).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: /修改题目/ }))
    expect(screen.getByRole('heading', { name: '修改题目' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '保存修改' })).toBeEnabled()
  })
})
