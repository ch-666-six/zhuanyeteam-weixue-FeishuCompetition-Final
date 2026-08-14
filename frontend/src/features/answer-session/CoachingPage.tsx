import { useEffect, useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BrainCircuit, CheckCircle2, MessageSquareText, RotateCcw, Send, StopCircle } from 'lucide-react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import type { AuthSession } from '../auth/auth'
import { AppShell } from '../../shared/ui/AppShell'
import { Button } from '../../shared/ui/Button'
import { endCoaching, getCoaching, getSession, retryCoachingQuestion, streamCoachingQuestion, submitCoachingResponse } from './api'
import { sessionRoute } from './navigation'

interface Props { auth: AuthSession; onLogout: () => void }

export function CoachingPage({ auth, onLogout }: Props) {
  const { sessionId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const review = searchParams.get('review') === '1'
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [answer, setAnswer] = useState('')
  const [streamedQuestion, setStreamedQuestion] = useState('')
  const [streamedTurnId, setStreamedTurnId] = useState<string | null>(null)
  const [streamError, setStreamError] = useState(false)
  const responseKey = useRef(crypto.randomUUID())
  const sessionQuery = useQuery({
    queryKey: ['session', auth.student.id, sessionId], queryFn: () => getSession(auth.token, sessionId),
    refetchInterval: (query) => query.state.data?.next_view === 'COACHING_PENDING' ? 1500 : false,
  })
  const recordQuery = useQuery({
    queryKey: ['coaching', auth.student.id, sessionId], queryFn: () => getCoaching(auth.token, sessionId),
    refetchInterval: (query) => {
      const latestTurn = query.state.data?.turns.at(-1)
      return sessionQuery.data?.next_view === 'COACHING_PENDING' || latestTurn?.status === 'WAITING' ? 1500 : false
    },
  })
  const currentTurn = useMemo(() => recordQuery.data?.turns.at(-1), [recordQuery.data])

  useEffect(() => {
    const session = sessionQuery.data
    if (!review && session && !['COACHING', 'COACHING_PENDING'].includes(session.next_view)) {
      navigate(sessionRoute(session), { replace: true })
    }
  }, [navigate, review, sessionQuery.data])

  useEffect(() => {
    if (!currentTurn?.question_text || currentTurn.id === streamedTurnId || currentTurn.status === 'WAITING') return
    const controller = new AbortController()
    setStreamedTurnId(currentTurn.id)
    setStreamedQuestion('')
    setStreamError(false)
    streamCoachingQuestion(auth.token, sessionId, currentTurn.id, (text) => setStreamedQuestion((value) => value + text), controller.signal)
      .catch(() => { setStreamError(true); setStreamedQuestion(currentTurn.question_text ?? '') })
    return () => controller.abort()
  }, [auth.token, currentTurn?.id, currentTurn?.question_text, currentTurn?.status, sessionId])

  const submit = useMutation({
    mutationFn: () => submitCoachingResponse(auth.token, sessionId, currentTurn!.id, answer, sessionQuery.data!.version, responseKey.current),
    onSuccess: (snapshot) => {
      setAnswer(''); responseKey.current = crypto.randomUUID(); setStreamedTurnId(null); setStreamedQuestion('')
      queryClient.setQueryData(['session', auth.student.id, sessionId], snapshot)
      queryClient.invalidateQueries({ queryKey: ['coaching', auth.student.id, sessionId] })
      navigate(sessionRoute(snapshot), { replace: true })
    },
  })
  const end = useMutation({
    mutationFn: () => endCoaching(auth.token, sessionId, sessionQuery.data!.version, crypto.randomUUID()),
    onSuccess: (snapshot) => { queryClient.setQueryData(['session', auth.student.id, sessionId], snapshot); navigate(sessionRoute(snapshot), { replace: true }) },
  })
  const retry = useMutation({
    mutationFn: () => retryCoachingQuestion(auth.token, sessionId, sessionQuery.data!.version, crypto.randomUUID()),
    onSuccess: (snapshot) => { queryClient.setQueryData(['session', auth.student.id, sessionId], snapshot); sessionQuery.refetch(); recordQuery.refetch() },
  })
  const pending = sessionQuery.data?.next_view === 'COACHING_PENDING'
  const canSubmit = Boolean(answer.trim() && currentTurn && sessionQuery.data?.allowed_actions.includes('SUBMIT_COACHING_RESPONSE'))

  return <AppShell auth={auth} onLogout={onLogout} progressStep="coaching" progressPreviousHref={`/sessions/${sessionId}/initial-analysis?review=1`} progressResumeHref={review && sessionQuery.data ? sessionRoute(sessionQuery.data) : undefined}>
    <main id="main-content" className="page-content coaching-page">
      <header className="coaching-header">
        <div><p className="eyebrow">第 3 步 · {review ? '查看 AI 追问' : 'AI 辅导'}</p><h1>{review ? '回看你的思考过程' : '把想法再往前推进一步'}</h1><p>{review ? '这里保留了已经完成的 AI 提问和你的回答。' : '每次只回答一个问题。答案由你自己决定，随时可以结束辅导。'}</p></div>
        <div className="round-counter" aria-label={`已完成 ${sessionQuery.data?.coaching.completed_rounds ?? 0} 轮，共 20 轮`}>
          <strong>{sessionQuery.data?.coaching.completed_rounds ?? 0}</strong><span>/ 20 轮</span>
        </div>
      </header>

      {recordQuery.data?.turns.filter((turn) => turn.student_response).map((turn) => <article className="coaching-turn" key={turn.id}>
        <div className="coach-question"><BrainCircuit size={19} /><div><span>第 {turn.round_number} 轮 · AI 提问</span><p>{turn.question_text}</p></div></div>
        <div className="student-response"><CheckCircle2 size={19} /><div><span>我的回答</span><p>{turn.student_response}</p></div></div>
      </article>)}

      {!review && <section className="current-question" aria-labelledby="current-question-title">
        <div className="current-question-label"><MessageSquareText size={20} /><span>第 {currentTurn?.round_number ?? sessionQuery.data?.coaching.current_round ?? 1} 轮</span></div>
        <h2 id="current-question-title" className="sr-only">当前问题</h2>
        {pending ? <div className="question-pending" role="status" aria-live="polite"><span className="progress-dot" />AI 正在根据你的回答准备下一个问题…</div>
          : <p className="streaming-question" aria-live="polite">{streamedQuestion || currentTurn?.question_text || '正在读取问题…'}<span className="stream-caret" aria-hidden="true" /></p>}
        {streamError && <p className="muted">流式连接已恢复为完整显示，内容没有丢失。</p>}
      </section>}

      {!review && sessionQuery.data?.jobs.coaching_question.status === 'FAILED_RETRYABLE' && <div className="inline-alert" role="alert">
        <p>下一个问题暂时没有生成，你刚才的回答已经保存。</p>
        <Button onClick={() => retry.mutate()} disabled={retry.isPending}><RotateCcw size={18} />重新生成问题</Button>
      </div>}

      {!review && !pending && <form className="coaching-composer" onSubmit={(event) => { event.preventDefault(); if (canSubmit) submit.mutate() }}>
        <label htmlFor="coaching-answer">我的回答</label>
        <textarea id="coaching-answer" value={answer} onChange={(event) => setAnswer(event.target.value)} maxLength={12000} rows={6} placeholder="先写下你自己的思考…" />
        <div className="field-footer"><span>{answer.length} / 12000 字</span><span>提交后会根据这段回答继续追问</span></div>
        {submit.isError && <p className="field-error" role="alert">回答提交失败或状态已经变化，请刷新后查看。</p>}
        <div className="coaching-actions">
          <Button type="button" variant="quiet" onClick={() => end.mutate()} disabled={end.isPending || !sessionQuery.data?.allowed_actions.includes('END_COACHING')}><StopCircle size={18} />结束辅导，准备终稿</Button>
          <Button type="submit" disabled={!canSubmit || submit.isPending}>{submit.isPending ? '正在提交…' : '提交本轮回答'}<Send size={18} /></Button>
        </div>
      </form>}
      {!review && pending && <div className="coaching-actions coaching-actions--pending"><Button variant="quiet" onClick={() => end.mutate()} disabled={end.isPending || !sessionQuery.data?.allowed_actions.includes('END_COACHING')}><StopCircle size={18} />结束辅导，准备终稿</Button></div>}
    </main>
  </AppShell>
}
