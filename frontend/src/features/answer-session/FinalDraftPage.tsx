import { useEffect, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { BookOpenText, CheckCircle2, Lightbulb, MessageSquareText, Save } from 'lucide-react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import type { AuthSession } from '../auth/auth'
import { AppShell } from '../../shared/ui/AppShell'
import { Button } from '../../shared/ui/Button'
import { getCoaching, getInitialAnalysis, getSession, submitFinalAnswer } from './api'
import { getAssignment } from '../assignments/api'
import { sessionRoute } from './navigation'
import { useAnswerDraft } from './useAnswerDraft'
import { ApiError } from '../../shared/api/http'
import { VoiceAnswerRecorder } from './VoiceAnswerRecorder'

interface Props { auth: AuthSession; onLogout: () => void }

export function FinalDraftPage({ auth, onLogout }: Props) {
  const { sessionId = '' } = useParams()
  const [searchParams] = useSearchParams()
  const review = searchParams.get('review') === '1'
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const submitKey = useRef(crypto.randomUUID())
  const sessionQuery = useQuery({ queryKey: ['session', auth.student.id, sessionId], queryFn: () => getSession(auth.token, sessionId) })
  const analysisQuery = useQuery({ queryKey: ['initial-analysis', auth.student.id, sessionId], queryFn: () => getInitialAnalysis(auth.token, sessionId) })
  const session = sessionQuery.data
  const assignmentQuery = useQuery({ queryKey: ['assignment', auth.student.id, session?.assignment_id], queryFn: () => getAssignment(auth.token, session!.assignment_id), enabled: Boolean(session?.assignment_id) })
  const coachingQuery = useQuery({ queryKey: ['coaching', auth.student.id, sessionId], queryFn: () => getCoaching(auth.token, sessionId), enabled: Boolean(session?.coaching && session.coaching.status !== 'NOT_STARTED') })
  const draft = useAnswerDraft(auth.student.id, session?.assignment_id ?? 'pending', sessionId, 'FINAL_DRAFT', analysisQuery.data?.input_version ?? 0)
  const answer = review ? session?.final_answer ?? '' : draft.value
  const voiceInput = assignmentQuery.data?.input_type === 'VOICE'
  const answerError = answer.trim() ? '' : '请先完成你的修改稿。'

  useEffect(() => {
    if (!review && session && session.next_view !== 'FINAL_DRAFT') navigate(sessionRoute(session), { replace: true })
  }, [navigate, review, session])
  useEffect(() => {
    if (!review && assignmentQuery.data?.input_type === 'TEXT' && !draft.value && analysisQuery.data?.initial_answer) draft.setValue(analysisQuery.data.initial_answer)
  }, [analysisQuery.data?.initial_answer, assignmentQuery.data?.input_type, review])

  const submit = useMutation({
    mutationFn: () => submitFinalAnswer(auth.token, sessionId, answer, session!.version, submitKey.current),
    onSuccess: (snapshot) => {
      draft.clear()
      queryClient.setQueryData(['session', auth.student.id, sessionId], snapshot)
      queryClient.invalidateQueries({ queryKey: ['assignments', auth.student.id] })
      navigate(sessionRoute(snapshot), { replace: true })
    },
    onError: (error) => {
      if (error instanceof ApiError && error.snapshot) navigate(sessionRoute(error.snapshot), { replace: true })
    },
  })
  const priority = analysisQuery.data?.analysis.priority_improvement

  const previousHref = session?.coaching.status === 'NOT_STARTED' || session?.coaching.status === 'SKIPPED'
    ? `/sessions/${sessionId}/initial-analysis?review=1`
    : `/sessions/${sessionId}/coaching?review=1`

  return <AppShell auth={auth} onLogout={onLogout} progressStep="final-answer" progressPreviousHref={previousHref} progressResumeHref={review && session ? sessionRoute(session) : undefined}>
    <main id="main-content" className="page-content revision-layout">
      <section className="revision-main">
        <header className="answer-heading"><p className="eyebrow">第 4 步 · {review ? '查看独立整理' : '最终提交'}</p><h1>{review ? '已提交的最终答案' : '独立整理最终答案'}</h1><p>{review ? '这是已经提交并用于成果反馈的版本。' : '回看题目、初答和辅导记录，用自己的语言完成最终答案。'}</p></header>
        <section className="final-topic"><BookOpenText size={19} /><div><span>题目</span><p>{assignmentQuery.data?.prompt ?? '正在读取题目…'}</p></div></section>
        <form className="answer-form" onSubmit={(event) => { event.preventDefault(); if (!review && !answerError && session) submit.mutate() }}>
          <label htmlFor="final-answer">{voiceInput ? '语音转写稿' : '我的修改稿'}</label>
          {!review && voiceInput && <VoiceAnswerRecorder token={auth.token} sessionId={sessionId} stage="final" value={answer} onTranscription={draft.setValue} disabled={!session} />}
          <textarea id="final-answer" value={answer} onChange={(event) => draft.setValue(event.target.value)} readOnly={review || voiceInput} placeholder={voiceInput ? '请重新录制终稿，转写文字会显示在这里。' : undefined} maxLength={12000} rows={14} aria-describedby="final-help final-count final-error" />
          <div className="field-footer"><span id="final-help">{review ? <><CheckCircle2 size={15} />已提交版本，仅供查看</> : voiceInput ? <><Save size={15} />转写稿已保存在本机</> : <><Save size={15} />草稿已保存在本机</>}</span><span id="final-count">{answer.length} / 12000 字</span></div>
          {submit.isError && <p id="final-error" className="field-error" role="alert">提交失败或状态已变化。你的本地草稿仍然保留，请刷新后查看。</p>}
          {!review && <div className="answer-actions"><p>{answerError || '提交后将生成不可修改的终稿版本。'}</p><Button type="submit" disabled={Boolean(answerError) || submit.isPending || !session}>{submit.isPending ? '正在提交…' : '提交修改稿'}</Button></div>}
        </form>
      </section>
      <aside className="revision-aside" aria-label="修改参考">
        {priority && <section className="revision-guide"><Lightbulb size={21} /><p className="eyebrow">优先修改</p><h2>{priority.suggestion}</h2></section>}
        <section className="original-reference"><h2><CheckCircle2 size={18} />你的初答</h2><blockquote>{analysisQuery.data?.initial_answer ?? '正在读取…'}</blockquote></section>
        {coachingQuery.data && coachingQuery.data.turns.some((turn) => turn.student_response) && <section className="coaching-reference"><h2><MessageSquareText size={18} />辅导记录</h2>{coachingQuery.data.turns.filter((turn) => turn.student_response).map((turn) => <div key={turn.id}><strong>第 {turn.round_number} 轮</strong><p>{turn.question_text}</p><blockquote>{turn.student_response}</blockquote></div>)}</section>}
      </aside>
    </main>
  </AppShell>
}
