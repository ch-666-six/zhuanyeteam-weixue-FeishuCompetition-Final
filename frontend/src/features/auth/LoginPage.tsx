import { useQuery } from '@tanstack/react-query'
import { ArrowRight, BookOpen, Check, Settings2 } from 'lucide-react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../../shared/ui/Button'
import type { AuthSession } from './auth'
import { listDemoStudents, loginDemoStudent } from './auth'

interface LoginPageProps {
  onLogin: (auth: AuthSession) => void
}

export function LoginPage({ onLogin }: LoginPageProps) {
  const navigate = useNavigate()
  const [selectedId, setSelectedId] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const studentsQuery = useQuery({ queryKey: ['demo-students'], queryFn: listDemoStudents })

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!selectedId) {
      setError('请先选择一个年级。')
      return
    }
    setSubmitting(true)
    setError('')
    try {
      const auth = await loginDemoStudent(selectedId)
      onLogin(auth)
      navigate('/assignments', { replace: true })
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : '登录失败，请稍后重试。')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="login-page">
      <section className="login-intro" aria-labelledby="product-name">
        <div className="brand-mark" aria-hidden="true"><BookOpen size={24} /></div>
        <p className="eyebrow">思辨表达 AI 助教</p>
        <h1 id="product-name">维学</h1>
        <p className="login-lead">先说出自己的想法，再一步一步把理由讲清楚。</p>
        <ol className="process-list" aria-label="学习过程">
          <li><span>1</span>独立写下观点</li>
          <li><span>2</span>查看表达线索</li>
          <li><span>3</span>整理最终答案</li>
        </ol>
      </section>

      <section className="login-panel" aria-labelledby="login-title">
        <div className="login-form-wrap">
          <p className="eyebrow">演示入口</p>
          <h2 id="login-title">选择你的年级</h2>
          <p className="muted">进入后只会看到本年级的学习任务。</p>

          {studentsQuery.isPending && <p className="status-line" aria-live="polite">正在准备年级列表…</p>}
          {studentsQuery.isError && (
            <div className="inline-alert" role="alert">
              无法连接服务，请确认后端已经启动。
            </div>
          )}

          {studentsQuery.data && (
            <form onSubmit={handleSubmit}>
              <fieldset className="grade-picker">
                <legend className="sr-only">选择年级</legend>
                {studentsQuery.data.map((student) => (
                  <label className="grade-option" key={student.id}>
                    <input
                      type="radio"
                      name="grade"
                      value={student.id}
                      checked={selectedId === student.id}
                      onChange={() => {
                        setSelectedId(student.id)
                        setError('')
                      }}
                    />
                    <span className="grade-number">{student.grade}</span>
                    <span className="grade-label">年级</span>
                    <Check className="grade-check" size={18} aria-hidden="true" />
                  </label>
                ))}
                <Link className="question-management-link" to="/question-management">
                  <Settings2 size={22} aria-hidden="true" />
                  <span>题目管理</span>
                  <small>查看与维护题目</small>
                </Link>
              </fieldset>
              {error && <p className="field-error" role="alert">{error}</p>}
              <Button type="submit" disabled={submitting || studentsQuery.data.length === 0}>
                {submitting ? '正在进入…' : '进入学习空间'}
                {!submitting && <ArrowRight size={18} aria-hidden="true" />}
              </Button>
            </form>
          )}
        </div>
      </section>
    </main>
  )
}
