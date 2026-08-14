import { BookOpenCheck, LogOut, TrendingUp } from 'lucide-react'
import type { ReactNode } from 'react'
import { Link, NavLink } from 'react-router-dom'
import type { AuthSession } from '../../features/auth/auth'
import { Button } from './Button'
import { AssignmentProgress, type AssignmentProgressStep } from './AssignmentProgress'

interface AppShellProps {
  auth: AuthSession
  onLogout: () => void
  children: ReactNode
  progressStep?: AssignmentProgressStep
  progressPreviousHref?: string
  progressResumeHref?: string
}

export function AppShell({ auth, onLogout, children, progressStep, progressPreviousHref, progressResumeHref }: AppShellProps) {
  return (
    <div className={`app-shell${progressStep ? ' app-shell--progress' : ''}`}>
      <a className="skip-link" href="#main-content">跳到主要内容</a>
      <header className="topbar">
        <Link className="wordmark" to="/assignments" aria-label="维学作业首页">
          <span className="wordmark-icon" aria-hidden="true"><BookOpenCheck size={20} /></span>
          <span>维学</span>
        </Link>
        <nav className="primary-nav" aria-label="主要导航">
          <NavLink to="/assignments"><BookOpenCheck size={17} aria-hidden="true" />我的作业</NavLink>
          <NavLink to="/growth"><TrendingUp size={17} aria-hidden="true" />思考成长</NavLink>
        </nav>
        <div className="student-menu">
          <span className="student-identity">{auth.student.display_name}</span>
          <Button variant="quiet" onClick={onLogout} aria-label="切换年级">
            <LogOut size={17} aria-hidden="true" />
            <span>切换年级</span>
          </Button>
        </div>
      </header>
      {progressStep && <AssignmentProgress current={progressStep} previousHref={progressPreviousHref} resumeHref={progressResumeHref} />}
      {children}
    </div>
  )
}
