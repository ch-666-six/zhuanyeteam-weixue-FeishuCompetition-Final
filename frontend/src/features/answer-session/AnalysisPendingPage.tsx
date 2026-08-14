import { useEffect } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { AlertCircle, BrainCircuit, CheckCircle2, RotateCcw } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import type { AuthSession } from '../auth/auth'
import { AppShell } from '../../shared/ui/AppShell'
import { getSession, retryInitialAnalysis } from './api'
import { sessionRoute } from './navigation'

interface AnalysisPendingPageProps {
  auth: AuthSession
  onLogout: () => void
}

export function AnalysisPendingPage({ auth, onLogout }: AnalysisPendingPageProps) {
  const { sessionId = '' } = useParams()
  const navigate = useNavigate()
  const query = useQuery({
    queryKey: ['session', auth.student.id, sessionId],
    queryFn: () => getSession(auth.token, sessionId),
    refetchInterval: 5000,
  })
  const retry = useMutation({
    mutationFn: () => retryInitialAnalysis(auth.token, sessionId, crypto.randomUUID()),
    onSuccess: (snapshot) => {
      query.refetch()
      navigate(sessionRoute(snapshot), { replace: true })
    },
  })
  const job = query.data?.jobs.initial_analysis
  useEffect(() => {
    if (query.data?.next_view === 'INITIAL_ANALYSIS') navigate(sessionRoute(query.data), { replace: true })
  }, [navigate, query.data])
  const failed = job?.status === 'FAILED_RETRYABLE' || job?.status === 'FAILED_FINAL'

  return (
    <AppShell auth={auth} onLogout={onLogout} progressStep="diagnosis" progressPreviousHref={`/sessions/${sessionId}/initial-answer?review=1`}>
      <main id="main-content" className="page-content pending-page">
        <div className={`pending-icon${failed ? ' pending-icon--error' : ''}`} aria-hidden="true">
          {failed ? <AlertCircle size={30} /> : <BrainCircuit size={30} />}
        </div>
        <p className="eyebrow">第 2 步 · 表达分析</p>
        <h1>{failed ? '这次分析没有完成' : '初答已经保存'}</h1>
        <p className="pending-lead">
          {failed ? '你的初答已安全保存。分析服务暂时遇到问题，不会影响已经写下的内容。' : '系统正在分析你已经写出的观点和理由。你可以稍后再回来查看。'}
        </p>
        <div className={`progress-line${failed ? ' progress-line--error' : ''}`} role="status" aria-live="polite">
          <span className="progress-dot" />
          当前状态：{job?.status === 'RUNNING' ? '正在分析' : failed ? (job.status === 'FAILED_FINAL' ? '多次尝试后仍未完成' : '等待你重新尝试') : '等待分析'}
        </div>
        {job?.status === 'FAILED_RETRYABLE' && (
          <button className="button button--primary retry-button" type="button" onClick={() => retry.mutate()} disabled={retry.isPending}>
            <RotateCcw size={18} />{retry.isPending ? '正在重新排队…' : '重新分析'}
          </button>
        )}
        {retry.isError && <p className="inline-alert" role="alert">暂时无法重新排队，请稍后再试。</p>}
        <div className="saved-answer">
          <h2><CheckCircle2 size={19} />你的初答</h2>
          <blockquote>{query.data?.initial_answer ?? '正在读取…'}</blockquote>
        </div>
        <Link className="button button--quiet" to="/assignments">返回作业列表</Link>
      </main>
    </AppShell>
  )
}
