import { useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertCircle, CheckCircle2, LoaderCircle, RotateCcw } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import type { AuthSession } from '../auth/auth'
import { AppShell } from '../../shared/ui/AppShell'
import { getSession, retryFinalEvaluation } from './api'
import { sessionRoute } from './navigation'

interface Props { auth: AuthSession; onLogout: () => void }

export function EvaluationPendingPage({ auth, onLogout }: Props) {
  const { sessionId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['session', auth.student.id, sessionId], queryFn: () => getSession(auth.token, sessionId), refetchInterval: 5000 })
  const session = query.data
  const job = session?.jobs.final_evaluation
  const failed = job?.status === 'FAILED_RETRYABLE' || job?.status === 'FAILED_FINAL'
  const retry = useMutation({
    mutationFn: () => retryFinalEvaluation(auth.token, sessionId, session!.version, crypto.randomUUID()),
    onSuccess: (snapshot) => {
      queryClient.setQueryData(['session', auth.student.id, sessionId], snapshot)
      navigate(sessionRoute(snapshot), { replace: true })
    },
  })
  useEffect(() => { if (session?.next_view === 'RESULT') navigate(sessionRoute(session), { replace: true }) }, [navigate, session])
  return <AppShell auth={auth} onLogout={onLogout} progressStep="result" progressPreviousHref={`/sessions/${sessionId}/final-answer?review=1`}>
    <main id="main-content" className="page-content pending-page">
      <div className={`pending-icon${failed ? ' pending-icon--error' : ''}`} aria-hidden="true">{failed ? <AlertCircle size={30} /> : <LoaderCircle size={30} />}</div>
      <p className="eyebrow">第 4 步 · 完成评价</p><h1>{failed ? '这次评价没有完成' : '修改稿已经提交'}</h1>
      <p className="pending-lead">{failed ? '你的终稿已经安全保存，不会重复提交。可以稍后重新生成评价。' : '你的终稿已保存为不可修改的版本。系统正在准备初答与终稿的对比评价。'}</p>
      <div className={`progress-line${failed ? ' progress-line--error' : ''}`} role="status" aria-live="polite"><span className="progress-dot" />当前状态：{job?.status === 'RUNNING' ? '正在评价' : failed ? (job.status === 'FAILED_FINAL' ? '多次尝试后仍未完成' : '等待你重新尝试') : '等待评价'}</div>
      {job?.status === 'FAILED_RETRYABLE' && <button className="button button--primary retry-button" type="button" onClick={() => retry.mutate()} disabled={retry.isPending}><RotateCcw size={18} />{retry.isPending ? '正在重新排队…' : '重新评价'}</button>}
      {retry.isError && <p className="inline-alert" role="alert">暂时无法重新排队，请稍后再试。</p>}
      <div className="saved-answer"><h2><CheckCircle2 size={19} />你的修改稿</h2><blockquote>{query.data?.final_answer ?? '正在读取…'}</blockquote></div>
      <Link className="button button--quiet" to="/assignments">返回作业列表</Link>
    </main>
  </AppShell>
}
