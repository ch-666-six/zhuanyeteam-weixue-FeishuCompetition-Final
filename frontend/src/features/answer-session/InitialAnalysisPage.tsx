import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRight, BrainCircuit, CheckCircle2, CircleDashed, Quote } from 'lucide-react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import type { AuthSession } from '../auth/auth'
import { AppShell } from '../../shared/ui/AppShell'
import { getInitialAnalysis, getSession, startCoaching, startFinalDraft } from './api'
import { sessionRoute } from './navigation'
import { ApiError } from '../../shared/api/http'

interface Props { auth: AuthSession; onLogout: () => void }

const labels = {
  viewpoint: '观点', reasons: '理由', evidence: '证据或例子', counterpoint: '不同看法', response: '回应', conditions: '条件与边界',
}
const statuses = { present: '已经写出', emerging: '正在形成', missing: '下一步可补充' }

export function InitialAnalysisPage({ auth, onLogout }: Props) {
  const { sessionId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const review = searchParams.get('review') === '1'
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['initial-analysis', auth.student.id, sessionId], queryFn: () => getInitialAnalysis(auth.token, sessionId) })
  const sessionQuery = useQuery({ queryKey: ['session', auth.student.id, sessionId], queryFn: () => getSession(auth.token, sessionId) })
  const skipMutation = useMutation({
    mutationFn: () => startFinalDraft(auth.token, sessionId, sessionQuery.data!.version, crypto.randomUUID()),
    onSuccess: (snapshot) => {
      queryClient.setQueryData(['session', auth.student.id, sessionId], snapshot)
      navigate(sessionRoute(snapshot))
    },
    onError: (error) => {
      if (error instanceof ApiError && error.snapshot) navigate(sessionRoute(error.snapshot), { replace: true })
    },
  })
  const coachingMutation = useMutation({
    mutationFn: () => startCoaching(auth.token, sessionId, sessionQuery.data!.version, crypto.randomUUID()),
    onSuccess: (snapshot) => {
      queryClient.setQueryData(['session', auth.student.id, sessionId], snapshot)
      navigate(sessionRoute(snapshot))
    },
    onError: (error) => {
      if (error instanceof ApiError && error.snapshot) navigate(sessionRoute(error.snapshot), { replace: true })
    },
  })

  return (
    <AppShell auth={auth} onLogout={onLogout} progressStep="diagnosis" progressPreviousHref={`/sessions/${sessionId}/initial-answer?review=1`} progressResumeHref={review && sessionQuery.data ? sessionRoute(sessionQuery.data) : undefined}>
      <main id="main-content" className="page-content analysis-page">
        <header className="analysis-header">
          <p className="eyebrow">第 2 步 · 表达分析</p>
          <h1>看看你已经表达清楚了什么</h1>
          <p>这不是评分。先从原文证据出发，再选择一个最值得补充的地方。</p>
        </header>
        {query.isLoading && <p role="status">正在读取分析结果…</p>}
        {query.isError && <p className="inline-alert" role="alert">分析结果暂时无法读取，请稍后再试。</p>}
        {query.data && <>
          <section className="analysis-source" aria-labelledby="source-title">
            <h2 id="source-title"><Quote size={19} />你的初答</h2>
            <blockquote>{query.data.initial_answer}</blockquote>
          </section>
          <section className="elements-section" aria-labelledby="elements-title">
            <h2 id="elements-title">表达要素</h2>
            <div className="element-list">
              {query.data.analysis.elements.map((item) => (
                <article className="element-row" key={item.element}>
                  <div className="element-status" aria-hidden="true">{item.status === 'present' ? <CheckCircle2 size={20} /> : <CircleDashed size={20} />}</div>
                  <div><div className="element-title"><h3>{labels[item.element]}</h3><span>{statuses[item.status]}</span></div><p>{item.summary}</p>
                    {item.quotes.map((quote) => <blockquote key={quote}>“{quote}”</blockquote>)}
                  </div>
                </article>
              ))}
            </div>
          </section>
          {query.data.analysis.priority_improvement && <section className="priority-section" aria-labelledby="priority-title">
            <p className="eyebrow">优先修改一处</p><h2 id="priority-title">先补充{labels[query.data.analysis.priority_improvement.element]}</h2>
            <p>{query.data.analysis.priority_improvement.suggestion}</p>
          </section>}
          {query.data.analysis.opening_question && <section className="opening-question" aria-labelledby="opening-question-title">
            <BrainCircuit size={22} /><div><p className="eyebrow">先想一想</p><h2 id="opening-question-title">{query.data.analysis.opening_question.question}</h2></div>
          </section>}
          {!review && (skipMutation.isError || coachingMutation.isError) && <p className="inline-alert" role="alert">状态可能已经变化，请刷新后查看最新步骤。</p>}
          {!review && <div className="analysis-actions analysis-actions--choice">
            <button className="button button--quiet" type="button" onClick={() => skipMutation.mutate()} disabled={skipMutation.isPending || coachingMutation.isPending || !sessionQuery.data?.allowed_actions.includes('START_FINAL_DRAFT')}>结束辅导，准备最终提交</button>
            <button className="button button--primary" type="button" onClick={() => coachingMutation.mutate()} disabled={coachingMutation.isPending || skipMutation.isPending || !sessionQuery.data?.allowed_actions.includes('START_COACHING')}>{coachingMutation.isPending ? '正在开始…' : '开始 AI 辅导'} <ArrowRight size={18} /></button>
          </div>}
          <div className="analysis-back"><Link to="/assignments">暂时离开，稍后继续</Link></div>
        </>}
      </main>
    </AppShell>
  )
}
