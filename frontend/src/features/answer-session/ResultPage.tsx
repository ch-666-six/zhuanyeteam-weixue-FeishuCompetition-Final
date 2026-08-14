import { useQuery } from '@tanstack/react-query'
import { ArrowRight, CheckCircle2, GitCompareArrows, Quote } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import type { AuthSession } from '../auth/auth'
import { AppShell } from '../../shared/ui/AppShell'
import { getFinalEvaluation } from './api'

interface Props { auth: AuthSession; onLogout: () => void }
const dimensionLabels = { idea: '立意', material: '选材', structure: '结构', language: '语言', perspective: '视角' }
const statusLabels = { clear: '表达清楚', developing: '正在发展', not_yet_visible: '暂未体现' }

export function ResultPage({ auth, onLogout }: Props) {
  const { sessionId = '' } = useParams()
  const query = useQuery({ queryKey: ['final-evaluation', auth.student.id, sessionId], queryFn: () => getFinalEvaluation(auth.token, sessionId) })
  const data = query.data
  return <AppShell auth={auth} onLogout={onLogout} progressStep="result" progressPreviousHref={`/sessions/${sessionId}/final-answer?review=1`}>
    <main id="main-content" className="page-content result-page">
      <header className="result-header"><p className="eyebrow">已完成 · 表达回顾</p><h1>这一次，你把想法说得更完整了</h1>{data && <p>{data.evaluation.summary}</p>}</header>
      {query.isLoading && <p role="status">正在读取评价结果…</p>}
      {query.isError && <p className="inline-alert" role="alert">评价结果暂时无法读取，请稍后再试。</p>}
      {data && <>
        <section className="strengths-section" aria-labelledby="strengths-title"><h2 id="strengths-title"><CheckCircle2 size={21} />做得好的</h2><div className="strength-list">{data.evaluation.strengths.map((item) => <article key={item.title}><h3>{item.title}</h3><p>{item.explanation}</p>{item.quotes.map((quote) => <blockquote key={quote}>“{quote}”</blockquote>)}</article>)}</div></section>
        <section className="result-next" aria-labelledby="next-title"><p className="eyebrow">下一次试一试</p><h2 id="next-title">继续关注{dimensionLabels[data.evaluation.next_step.dimension]}</h2><p>{data.evaluation.next_step.suggestion}</p></section>
        <section className="revision-section" aria-labelledby="revision-title"><h2 id="revision-title"><GitCompareArrows size={21} />从初答到终稿</h2>{data.evaluation.revision_evidence.length ? data.evaluation.revision_evidence.map((item) => <article className="revision-evidence" key={`${item.initial_quote}:${item.final_quote}`}><h3>{item.change}</h3><div><blockquote><span>初答</span>{item.initial_quote}</blockquote><ArrowRight aria-hidden="true" /><blockquote><span>终稿</span>{item.final_quote}</blockquote></div></article>) : <p className="muted">这次暂时没有找到适合直接对比的原文片段。</p>}</section>
        <section className="dimensions-section" aria-labelledby="dimensions-title"><h2 id="dimensions-title">五个表达维度</h2><div className="dimension-list">{data.evaluation.dimensions.map((item) => <article key={item.dimension}><div><h3>{dimensionLabels[item.dimension]}</h3><span>{statusLabels[item.status]}</span></div><p>{item.observation}</p>{item.quotes.map((quote) => <blockquote key={quote}><Quote size={15} />{quote}</blockquote>)}</article>)}</div></section>
        <div className="result-actions"><Link className="button button--quiet" to="/growth">查看思考成长</Link><Link className="button button--primary" to="/assignments">完成并返回作业列表</Link></div>
      </>}
    </main>
  </AppShell>
}
