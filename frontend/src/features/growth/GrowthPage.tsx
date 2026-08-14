import { useQuery } from '@tanstack/react-query'
import { AlertCircle, FileText, Route, TrendingUp } from 'lucide-react'
import { Link } from 'react-router-dom'
import type { GrowthPoint, GrowthReport } from '../../shared/api/types'
import { AppShell } from '../../shared/ui/AppShell'
import { Button } from '../../shared/ui/Button'
import type { AuthSession } from '../auth/auth'
import { getGrowthReport } from './api'

interface GrowthPageProps {
  auth: AuthSession
  onLogout: () => void
}

const DIMENSION_STYLE = {
  attitude: { color: '#3f8075', dash: undefined, offset: -8 },
  information: { color: '#4f78a4', dash: '10 5', offset: -4 },
  reasoning: { color: '#ad6d5c', dash: '3 4', offset: 0 },
  argument: { color: '#a38435', dash: '13 4 3 4', offset: 4 },
  expression: { color: '#657294', dash: '2 3', offset: 8 },
} as const

const ABILITY_BANDS = ['综合比较', '稳定论证', '形成理由', '表达想法'] as const

function formatMonth(value: string) {
  const date = new Date(value)
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}`
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' }).format(new Date(value))
}

function shortPhrase(point: GrowthPoint) {
  const clean = point.observation.replace(/[。！？!?]/g, '').trim()
  return clean.length > 14 ? `${clean.slice(0, 14)}…` : clean
}

function wrapObservation(value: string, lineLength = 22) {
  const clean = value.trim()
  const lines: string[] = []
  for (let index = 0; index < clean.length; index += lineLength) lines.push(clean.slice(index, index + lineLength))
  return lines.slice(0, 3)
}

function CompleteTrajectory({ report }: { report: GrowthReport }) {
  const eligibleDates = report.dimensions.flatMap((dimension) => dimension.points.filter((point) => point.eligible).map((point) => new Date(point.submitted_at).getTime()))
  const uniqueDates = [...new Set(eligibleDates)].sort((a, b) => a - b)
  const width = Math.max(920, uniqueDates.length * 128)
  const left = 126
  const right = 44
  const plotTop = 218
  const plotBottom = 430
  const minDate = uniqueDates[0] ?? Date.now()
  const maxDate = uniqueDates.at(-1) ?? minDate
  const xFor = (value: string) => left + ((new Date(value).getTime() - minDate) / Math.max(1, maxDate - minDate)) * (width - left - right)
  const yFor = (level: number, offset: number) => plotBottom - (level - 1) * ((plotBottom - plotTop) / 3) + offset
  const tickDates = uniqueDates.filter((_, index) => uniqueDates.length <= 6 || index === 0 || index === uniqueDates.length - 1 || index % Math.ceil(uniqueDates.length / 5) === 0)

  return <>
    <section className="growth-coverage" aria-label="档案覆盖度">
      <div><strong>{report.coverage.completed_assignments}</strong><span>已完成记录</span></div>
      <div><strong>{report.coverage.trend_eligible_assignments}</strong><span>可用于观察</span></div>
      <div><strong>{report.teacher_confirmation.confirmed_count}</strong><span>老师已确认</span></div>
    </section>

    <section className="trajectory-section" aria-labelledby="trajectory-title">
      <header className="trajectory-header">
        <div><p className="eyebrow">完整学习轨迹</p><h2 id="trajectory-title">按日期的五维成长折线图</h2></div>
        <ul className="trajectory-legend" aria-label="五维图例">
          {report.dimensions.map((dimension) => <li key={dimension.key} style={{ '--dimension-color': DIMENSION_STYLE[dimension.key].color } as React.CSSProperties}><i /><span>{dimension.name}</span></li>)}
        </ul>
      </header>
      <div className="trajectory-scroll" tabIndex={0} aria-label="五维成长图，可横向滚动">
        <svg className="trajectory-chart" style={{ width }} viewBox={`0 0 ${width} 510`} role="img" aria-labelledby="trajectory-title trajectory-desc">
          <desc id="trajectory-desc">横轴为实际完成日期，纵轴为四个能力表现带，五条线分别表示五个思维维度。</desc>
          {report.dimensions.map((dimension, index) => <g key={`band-${dimension.key}`} className="trajectory-label-band">
            <text x="8" y={28 + index * 31}>{dimension.name}</text>
            <line x1={left} y1={34 + index * 31} x2={width - right} y2={34 + index * 31} />
          </g>)}
          {ABILITY_BANDS.map((label, index) => {
            const y = plotTop + index * ((plotBottom - plotTop) / 3)
            return <g key={label} className="trajectory-ability-band"><text x={left - 14} y={y + 4}>{label}</text><line x1={left} y1={y} x2={width - right} y2={y} /></g>
          })}
          {tickDates.map((date) => {
            const x = left + ((date - minDate) / Math.max(1, maxDate - minDate)) * (width - left - right)
            return <g key={date} className="trajectory-date-tick"><line x1={x} y1={plotTop} x2={x} y2={plotBottom} /><text x={x} y="459">{formatMonth(new Date(date).toISOString())}</text></g>
          })}
          <text className="trajectory-axis-caption" x={width - right} y="490">实际完成日期</text>
          {report.dimensions.map((dimension, dimensionIndex) => {
            const style = DIMENSION_STYLE[dimension.key]
            const eligible = dimension.points.filter((point) => point.eligible)
            const coordinates = eligible.map((point) => ({ point, x: xFor(point.submitted_at), y: yFor(point.level_value, style.offset) }))
            const annotated = [...coordinates].reverse().filter((coordinate, index, selected) => index < 3 && selected.slice(0, index).every((item) => Math.abs(item.x - coordinate.x) > 115))
            return <g key={dimension.key} style={{ color: style.color }}>
              {coordinates.length > 1 && <polyline className="trajectory-line" stroke={style.color} strokeDasharray={style.dash} points={coordinates.map(({ x, y }) => `${x},${y}`).join(' ')} />}
              {annotated.map(({ point, x, y }) => {
                const labelY = 27 + dimensionIndex * 31
                const anchor = x > width - 230 ? 'end' : 'start'
                const labelX = anchor === 'end' ? x - 7 : x + 7
                return <g key={`label-${point.session_id}`} className="trajectory-annotation"><line stroke={style.color} x1={x} y1={labelY + 6} x2={x} y2={y - 8} /><text fill={style.color} x={labelX} y={labelY} textAnchor={anchor}>{shortPhrase(point)}</text></g>
              })}
              {coordinates.map(({ point, x, y }, index) => {
                const tooltipLines = wrapObservation(point.observation)
                const tooltipWidth = 286
                const tooltipHeight = 43 + tooltipLines.length * 18
                const tooltipX = x > width - tooltipWidth - right ? x - tooltipWidth - 14 : x + 14
                const tooltipY = Math.max(158, y - tooltipHeight - 16)
                const accessibleLabel = `${formatDate(point.submitted_at)} · ${dimension.name}：${point.observation}`
                return <g key={point.session_id} className="trajectory-node-group">
                  <circle className={index >= 2 ? 'trajectory-node is-stable' : 'trajectory-node'} tabIndex={0} role="img" aria-label={accessibleLabel} cx={x} cy={y} r="6" fill={index >= 2 ? style.color : '#fff'} stroke={style.color} />
                  <g className="trajectory-tooltip" transform={`translate(${tooltipX} ${tooltipY})`} aria-hidden="true">
                    <rect width={tooltipWidth} height={tooltipHeight} rx="6" />
                    <circle cx="17" cy="18" r="4" fill={style.color} />
                    <text className="trajectory-tooltip-meta" x="29" y="22">{formatDate(point.submitted_at)} · {dimension.name}</text>
                    <text className="trajectory-tooltip-copy" x="14" y="45">{tooltipLines.map((line, lineIndex) => <tspan key={lineIndex} x="14" dy={lineIndex === 0 ? 0 : 18}>{line}</tspan>)}</text>
                  </g>
                </g>
              })}
            </g>
          })}
        </svg>
      </div>
      <p className="trajectory-note">每个圆点对应一份可用于观察的记录；日期反映记录顺序。图中不显示分数、排名或年级阶段结论。</p>
    </section>

    <section className="growth-summaries" aria-labelledby="growth-summaries-title">
      <div className="growth-section-heading"><p className="eyebrow">五维综合描述</p><h2 id="growth-summaries-title">跨全部记录的整体观察</h2></div>
      <dl>{report.dimensions.map((dimension) => <div key={dimension.key}><dt style={{ '--dimension-color': DIMENSION_STYLE[dimension.key].color } as React.CSSProperties}>{dimension.name}</dt><dd>{dimension.summary}</dd></div>)}</dl>
    </section>

    <section className="growth-method" aria-labelledby="growth-method-title"><h2 id="growth-method-title">这份档案如何形成</h2><p>五个维度并列呈现。每个学习阶段使用对应年级的标准；记录不足时只显示积累状态，不对变化作判断。AI 对话和作答方式不参与评价。</p></section>
    <div className="growth-footer-action"><Link className="button button--secondary" to="/assignments"><FileText size={17} aria-hidden="true" />返回我的作业</Link></div>
  </>
}

export function GrowthPage({ auth, onLogout }: GrowthPageProps) {
  const query = useQuery({ queryKey: ['growth', auth.student.id, 'all'], queryFn: () => getGrowthReport(auth.token, null) })
  const report = query.data

  return <AppShell auth={auth} onLogout={onLogout}>
    <main id="main-content" className="page-content growth-page">
      <header className="growth-heading"><div><p className="eyebrow"><Route size={15} aria-hidden="true" />成长报告</p><h1>我的思考成长</h1><p className="growth-heading-copy">从学习开始到现在，五种思维能力留下的发展轨迹。不同阶段使用对应年级标准，不计算总分。</p></div></header>
      {report && <p className="growth-record-status">{report.coverage.completed_assignments < 3 ? '你的成长档案正在积累' : '这是根据已完成作业汇总的成长档案'}</p>}
      {query.isPending && <p className="status-line" aria-live="polite">正在整理成长记录…</p>}
      {query.isError && <div className="empty-state" role="alert"><AlertCircle size={30} aria-hidden="true" /><h2>暂时无法读取成长记录</h2><p>已有作业不会丢失，可以重新加载。</p><Button onClick={() => query.refetch()}>重新加载</Button></div>}
      {report?.coverage.completed_assignments === 0 && <div className="empty-state"><TrendingUp size={32} aria-hidden="true" /><h2>成长记录从第一份作业开始</h2><p>完成作业并生成评价后，这里会留下五维学习轨迹。</p><Link className="button button--primary" to="/assignments">去看作业</Link></div>}
      {report && report.coverage.completed_assignments > 0 && <CompleteTrajectory report={report} />}
    </main>
  </AppShell>
}
