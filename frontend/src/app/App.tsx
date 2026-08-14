import { useState } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import type { AuthSession } from '../features/auth/auth'
import { clearAuthSession, readAuthSession, saveAuthSession } from '../features/auth/auth'
import { AssignmentsPage } from '../features/assignments/AssignmentsPage'
import { AssignmentDetailPage } from '../features/assignments/AssignmentDetailPage'
import { AnalysisPendingPage } from '../features/answer-session/AnalysisPendingPage'
import { InitialAnswerPage } from '../features/answer-session/InitialAnswerPage'
import { InitialAnalysisPage } from '../features/answer-session/InitialAnalysisPage'
import { FinalDraftPage } from '../features/answer-session/FinalDraftPage'
import { EvaluationPendingPage } from '../features/answer-session/EvaluationPendingPage'
import { CoachingPage } from '../features/answer-session/CoachingPage'
import { ResultPage } from '../features/answer-session/ResultPage'
import { LoginPage } from '../features/auth/LoginPage'
import { GrowthPage } from '../features/growth/GrowthPage'
import { QuestionManagementPage } from '../features/question-management/QuestionManagementPage'

export function App() {
  const [auth, setAuth] = useState<AuthSession | null>(() => readAuthSession())

  function handleLogin(nextAuth: AuthSession) {
    saveAuthSession(nextAuth)
    setAuth(nextAuth)
  }

  function handleLogout() {
    clearAuthSession()
    setAuth(null)
  }

  return (
    <Routes>
      <Route
        path="/login"
        element={auth ? <Navigate to="/assignments" replace /> : <LoginPage onLogin={handleLogin} />}
      />
      <Route path="/question-management" element={<QuestionManagementPage />} />
      <Route path="/sessions/:sessionId/coaching-pending" element={auth ? <CoachingPage auth={auth} onLogout={handleLogout} /> : <Navigate to="/login" replace />} />
      <Route path="/sessions/:sessionId/coaching" element={auth ? <CoachingPage auth={auth} onLogout={handleLogout} /> : <Navigate to="/login" replace />} />
      <Route
        path="/assignments"
        element={
          auth ? (
            <AssignmentsPage auth={auth} onLogout={handleLogout} />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />
      <Route
        path="/assignments/:assignmentId"
        element={auth ? <AssignmentDetailPage auth={auth} onLogout={handleLogout} /> : <Navigate to="/login" replace />}
      />
      <Route path="/growth" element={auth ? <GrowthPage auth={auth} onLogout={handleLogout} /> : <Navigate to="/login" replace />} />
      <Route
        path="/sessions/:sessionId/initial-answer"
        element={auth ? <InitialAnswerPage auth={auth} onLogout={handleLogout} /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/sessions/:sessionId/analysis-pending"
        element={auth ? <AnalysisPendingPage auth={auth} onLogout={handleLogout} /> : <Navigate to="/login" replace />}
      />
      <Route
        path="/sessions/:sessionId/initial-analysis"
        element={auth ? <InitialAnalysisPage auth={auth} onLogout={handleLogout} /> : <Navigate to="/login" replace />}
      />
      <Route path="/sessions/:sessionId/final-answer" element={auth ? <FinalDraftPage auth={auth} onLogout={handleLogout} /> : <Navigate to="/login" replace />} />
      <Route path="/sessions/:sessionId/evaluation-pending" element={auth ? <EvaluationPendingPage auth={auth} onLogout={handleLogout} /> : <Navigate to="/login" replace />} />
      <Route path="/sessions/:sessionId/result" element={auth ? <ResultPage auth={auth} onLogout={handleLogout} /> : <Navigate to="/login" replace />} />
      <Route path="*" element={<Navigate to={auth ? '/assignments' : '/login'} replace />} />
    </Routes>
  )
}
