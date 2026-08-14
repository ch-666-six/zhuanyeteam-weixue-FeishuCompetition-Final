import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CalendarDays, FileText, RefreshCw } from 'lucide-react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useRef } from 'react'
import type { AuthSession } from '../auth/auth'
import { createSession } from '../answer-session/api'
import { sessionRoute } from '../answer-session/navigation'
import { AppShell } from '../../shared/ui/AppShell'
import { Button } from '../../shared/ui/Button'
import { getAssignment } from './api'

interface AssignmentDetailPageProps {
  auth: AuthSession
  onLogout: () => void
}

export function AssignmentDetailPage({ auth, onLogout }: AssignmentDetailPageProps) {
  const { assignmentId = '' } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const createKey = useRef(crypto.randomUUID())
  const query = useQuery({
    queryKey: ['assignment', auth.student.id, assignmentId],
    queryFn: () => getAssignment(auth.token, assignmentId),
    enabled: Boolean(assignmentId),
  })
  const startMutation = useMutation({
    mutationFn: () => createSession(auth.token, assignmentId, createKey.current),
    onSuccess: (snapshot) => {
      queryClient.invalidateQueries({ queryKey: ['assignments', auth.student.id] })
      navigate(sessionRoute(snapshot))
    },
  })

  const assignment = query.data
  const existingSession = assignment?.session
  const closed = assignment?.availability === 'CLOSED'

  return (
    <AppShell auth={auth} onLogout={onLogout} progressStep="understand">
      <main id="main-content" className="page-content page-content--reading">
        <Link className="back-link" to="/assignments"><ArrowLeft size={17} />返回作业列表</Link>
        {query.isPending && <p className="status-line" aria-live="polite">正在读取题目…</p>}
        {query.isError && (
          <div className="empty-state" role="alert">
            <RefreshCw size={28} />
            <h1>暂时无法读取题目</h1>
            <Button onClick={() => query.refetch()}>重新加载</Button>
          </div>
        )}
        {assignment && (
          <article className="assignment-detail">
            <header>
              <p className="eyebrow">{assignment.grade} 年级 · 思辨表达</p>
              <h1>{assignment.title}</h1>
              <div className="detail-meta">
                <span><CalendarDays size={17} />{assignment.deadline ? `${new Date(assignment.deadline).toLocaleDateString('zh-CN')} 截止` : '长期有效'}</span>
                <span><FileText size={17} />文字作答</span>
              </div>
            </header>
            <section className="prompt-section" aria-labelledby="prompt-title">
              <h2 id="prompt-title">题目</h2>
              <p>{assignment.prompt}</p>
            </section>
            <section className="requirements-section" aria-labelledby="requirements-title">
              <h2 id="requirements-title">作答要求</h2>
              <ul>
                <li>先独立写下自己的观点。</li>
                <li>至少说明一个支持观点的理由。</li>
                <li>可以结合经历、观察或设想来解释。</li>
              </ul>
            </section>
            {startMutation.isError && <div className="inline-alert" role="alert">{startMutation.error.message}</div>}
            <div className="detail-action">
              <div>
                <strong>{closed ? '这项作业已经截止' : existingSession ? '继续上次的作答' : '准备好后开始独立作答'}</strong>
                <p>{closed ? '仍可查看题目，但不能再提交。' : '你的草稿会保存在当前浏览器中。'}</p>
              </div>
              {!closed && (
                <Button
                  onClick={() => existingSession ? navigate(sessionRoute(existingSession)) : startMutation.mutate()}
                  disabled={startMutation.isPending}
                >
                  {startMutation.isPending ? '正在开始…' : existingSession ? '继续作答' : '开始作答'}
                </Button>
              )}
            </div>
          </article>
        )}
      </main>
    </AppShell>
  )
}
