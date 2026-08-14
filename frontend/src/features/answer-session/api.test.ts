import { afterEach, describe, expect, it, vi } from 'vitest'
import { streamCoachingQuestion } from './api'

describe('streamCoachingQuestion', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('combines validated SSE question deltas', async () => {
    const body = [
      'event: meta\ndata: {"round_number":2}\n\n',
      'event: delta\ndata: {"text":"你能"}\n\n',
      'event: delta\ndata: {"text":"举例吗？"}\n\n',
      'event: done\ndata: {}\n\n',
    ].join('')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(body, {
      status: 200, headers: { 'Content-Type': 'text/event-stream' },
    })))
    let question = ''
    await streamCoachingQuestion('token', 'session-1', 'turn-2', (delta) => { question += delta })
    expect(question).toBe('你能举例吗？')
  })
})
