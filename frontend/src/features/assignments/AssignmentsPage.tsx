import { useQuery } from '@tanstack/react-query'
import { ArrowRight, BookOpenCheck, Clock3, RefreshCw } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { AuthSession } from '../auth/auth'
import { AppShell } from '../../shared/ui/AppShell'
import { Button } from '../../shared/ui/Button'
import type { AssignmentSummary } from '../../shared/api/types'
import { listAssignments } from './api'

interface AssignmentsPageProps {
  auth: AuthSession
  onLogout: () => void
}

function assignmentStatus(assignment: AssignmentSummary): { label: string; tone: string } {
  if (assignment.availability === 'CLOSED') return { label: '已截止', tone: 'neutral' }
  if (!assignment.session) return { label: '待开始', tone: 'info' }
  if (assignment.session.phase === 'INITIAL_DRAFT') return { label: '继续初答', tone: 'warning' }
  if (assignment.session.phase === 'INITIAL_ANALYSIS') return { label: '分析中', tone: 'ai' }
  return { label: '进行中', tone: 'success' }
}

function deadlineLabel(deadline: string | null): string {
  if (!deadline) return '长期有效'
  return `${new Intl.DateTimeFormat('zh-CN', { month: 'long', day: 'numeric' }).format(new Date(deadline))}截止`
}

export function AssignmentsPage({ auth, onLogout }: AssignmentsPageProps) {
  const assignmentsQuery = useQuery({
    queryKey: ['assignments', auth.student.id],
    queryFn: () => listAssignments(auth.token),
  })

  const assignments = assignmentsQuery.data ?? []
  const activeCount = assignments.filter((item) => item.session && item.availability === 'OPEN').length

  return (
    <AppShell auth={auth} onLogout={onLogout}>
      <main id="main-content" className="page-content">
        <header className="page-heading">
          <div>
            <p className="eyebrow">学习任务</p>
            <h1>我的作业</h1>
          </div>
          <p className="page-summary">
            {activeCount > 0 ? `有 ${activeCount} 项任务正在进行` : '清楚表达，从自己的想法开始。'}
          </p>
        </header>

        {assignmentsQuery.isPending && <p className="status-line" aria-live="polite">正在读取作业…</p>}
        {assignmentsQuery.isError && (
          <div className="empty-state" role="alert">
            <RefreshCw size={28} aria-hidden="true" />
            <h2>暂时无法读取作业</h2>
            <p>请检查网络连接后再试一次。</p>
            <Button onClick={() => assignmentsQuery.refetch()}>重新加载</Button>
          </div>
        )}
        {assignmentsQuery.data?.length === 0 && (
          <div className="empty-state">
            <BookOpenCheck size={32} aria-hidden="true" />
            <h2>新作业正在准备中</h2>
            <p>这里会显示老师发布的学习任务。现在可以先休息一下。</p>
          </div>
        )}
        {assignments.length > 0 && (
          <ul className="assignment-list" aria-label="作业列表">
            {assignments.map((assignment) => {
              const status = assignmentStatus(assignment)
              return (
                <li key={assignment.id}>
                  <Link className="assignment-row" to={`/assignments/${assignment.id}`}>
                    <div className="assignment-main">
                      <div className="assignment-meta">
                        <span className={`status-badge status-badge--${status.tone}`}>{status.label}</span>
                        <span><Clock3 size={15} aria-hidden="true" />{deadlineLabel(assignment.deadline)}</span>
                      </div>
                      <h2>{assignment.title}</h2>
                      <p>{assignment.prompt}</p>
                    </div>
                    <ArrowRight className="assignment-arrow" aria-hidden="true" />
                  </Link>
                </li>
              )
            })}
          </ul>
        )}
      </main>
    </AppShell>
  )
}

