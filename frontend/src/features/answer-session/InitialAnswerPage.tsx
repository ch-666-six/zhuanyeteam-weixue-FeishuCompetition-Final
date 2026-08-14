import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle2, Lightbulb, Save } from 'lucide-react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { useEffect, useRef } from 'react'
import type { AuthSession } from '../auth/auth'
import { getAssignment } from '../assignments/api'
import { AppShell } from '../../shared/ui/AppShell'
import { Button } from '../../shared/ui/Button'
import { getSession, submitInitialAnswer } from './api'
import { sessionRoute } from './navigation'
import { useAnswerDraft } from './useAnswerDraft'

interface InitialAnswerPageProps {
  auth: AuthSession
  onLogout: () => void
}

export function InitialAnswerPage({ auth, onLogout }: InitialAnswerPageProps) {
  const { sessionId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const review = searchParams.get('review') === '1'
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const submitKey = useRef(crypto.randomUUID())
  const sessionQuery = useQuery({
    queryKey: ['session', auth.student.id, sessionId],
    queryFn: () => getSession(auth.token, sessionId),
    enabled: Boolean(sessionId),
  })
  const assignmentId = sessionQuery.data?.assignment_id ?? ''
  const assignmentQuery = useQuery({
    queryKey: ['assignment', auth.student.id, assignmentId],
    queryFn: () => getAssignment(auth.token, assignmentId),
    enabled: Boolean(assignmentId),
  })
  const draft = useAnswerDraft(auth.student.id, assignmentId || 'pending', sessionId, 'INITIAL_DRAFT', sessionQuery.data?.version ?? 1)
  const answer = review ? sessionQuery.data?.initial_answer ?? '' : draft.value
  const answerError = answer.trim().length === 0 ? '请先写下你的观点和理由。' : ''

  const submitMutation = useMutation({
    mutationFn: () => submitInitialAnswer(auth.token, sessionId, answer, sessionQuery.data!.version, submitKey.current),
    onSuccess: (snapshot) => {
      draft.clear()
      queryClient.setQueryData(['session', auth.student.id, sessionId], snapshot)
      queryClient.invalidateQueries({ queryKey: ['assignments', auth.student.id] })
      navigate(sessionRoute(snapshot), { replace: true })
    },
  })

  const session = sessionQuery.data
  useEffect(() => {
    if (!review && session && session.next_view !== 'INITIAL_DRAFT') {
      navigate(sessionRoute(session), { replace: true })
    }
  }, [navigate, review, session])

  return (
    <AppShell auth={auth} onLogout={onLogout} progressStep="initial-answer" progressPreviousHref={assignmentId ? `/assignments/${assignmentId}` : undefined} progressResumeHref={review && session ? sessionRoute(session) : undefined}>
      <main id="main-content" className="page-content answer-layout">
        <section className="answer-main">
          <Link className="back-link" to={`/assignments/${assignmentId}`}><ArrowLeft size={17} />返回题目</Link>
          <header className="answer-heading">
            <p className="eyebrow">第 1 步 · {review ? '查看独立初答' : '独立初答'}</p>
            <h1>{assignmentQuery.data?.title ?? '写下你的想法'}</h1>
            <p>先按自己的理解表达。提交后，AI 只会帮你看清已有的观点和理由。</p>
          </header>
          <form
            className="answer-form"
            onSubmit={(event) => {
              event.preventDefault()
              if (!review && !answerError && session) submitMutation.mutate()
            }}
          >
            <label htmlFor="initial-answer">我的初答</label>
            <textarea
              id="initial-answer"
              value={answer}
              onChange={(event) => draft.setValue(event.target.value)}
              readOnly={review}
              placeholder="我认为……因为……"
              maxLength={12000}
              rows={12}
              aria-invalid={Boolean(submitMutation.isError)}
              aria-describedby="answer-help answer-count answer-error"
            />
            <div className="field-footer">
              <span id="answer-help">{review ? <><CheckCircle2 size={15} />已提交版本，仅供查看</> : <><Save size={15} />草稿已保存在本机</>}</span>
              <span id="answer-count">{answer.length} / 12000 字</span>
            </div>
            {submitMutation.isError && <p id="answer-error" className="field-error" role="alert">{submitMutation.error.message}</p>}
            {!review && <div className="answer-actions">
              <p>{answerError || '提交后会进入表达分析，初答将不能修改。'}</p>
              <Button type="submit" disabled={Boolean(answerError) || submitMutation.isPending || !session}>
                {submitMutation.isPending ? '正在提交…' : '提交初答'}
              </Button>
            </div>}
          </form>
        </section>
        <aside className="answer-aside" aria-labelledby="tip-title">
          <Lightbulb size={22} aria-hidden="true" />
          <h2 id="tip-title">写作提示</h2>
          <p>先回答“我怎么看”，再解释“为什么”。不用追求一次写得完美。</p>
        </aside>
      </main>
    </AppShell>
  )
}
