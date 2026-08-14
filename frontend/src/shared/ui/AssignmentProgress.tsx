import { ArrowLeft, ArrowRight, Check } from 'lucide-react'
import { Link } from 'react-router-dom'

export type AssignmentProgressStep =
  | 'understand'
  | 'initial-answer'
  | 'diagnosis'
  | 'coaching'
  | 'final-answer'
  | 'result'

const steps: Array<{ id: AssignmentProgressStep; label: string }> = [
  { id: 'understand', label: '理解题目' },
  { id: 'initial-answer', label: '独立初答' },
  { id: 'diagnosis', label: '思考诊断' },
  { id: 'coaching', label: 'AI 追问' },
  { id: 'final-answer', label: '独立整理' },
  { id: 'result', label: '成果反馈' },
]

interface AssignmentProgressProps {
  current: AssignmentProgressStep
  previousHref?: string
  resumeHref?: string
}

export function AssignmentProgress({ current, previousHref, resumeHref }: AssignmentProgressProps) {
  const currentIndex = steps.findIndex((step) => step.id === current)
  const currentStep = steps[currentIndex]
  const nextStep = steps[currentIndex + 1]

  return (
    <div className="assignment-progress-band">
      <nav
        className="assignment-progress"
        aria-label={`作业进度，第 ${currentIndex + 1} / ${steps.length} 阶段，当前为${currentStep.label}`}
      >
        <div className="assignment-progress-summary">
          <span>作业进度</span>
          <b>{currentIndex + 1} / {steps.length}</b>
        </div>
        <div className="assignment-progress-current">
          <strong>{currentStep.label}</strong>
          <span>{nextStep ? `下一步：${nextStep.label}` : '本次作业已完成'}</span>
        </div>
        <ol className="assignment-progress-steps">
          {steps.map((step, index) => {
            const state = index < currentIndex ? 'complete' : index === currentIndex ? 'current' : 'upcoming'
            const stateLabel = state === 'complete' ? '已完成' : state === 'current' ? '当前阶段' : '未开始'
            return (
              <li
                className={`assignment-progress-step assignment-progress-step--${state}`}
                aria-current={state === 'current' ? 'step' : undefined}
                key={step.id}
              >
                <span className="assignment-progress-marker" aria-hidden="true">
                  {state === 'complete' ? <Check size={14} /> : index + 1}
                </span>
                <span className="assignment-progress-copy">
                  <b>{step.label}</b>
                  <small>{stateLabel}</small>
                </span>
              </li>
            )
          })}
        </ol>
        <div className="assignment-progress-track" aria-hidden="true">
          {steps.map((step, index) => (
            <i className={index <= currentIndex ? 'active' : ''} key={step.id} />
          ))}
        </div>
        <div className="assignment-progress-actions">
          {previousHref && currentIndex > 0 && (
            <Link className="assignment-progress-back" to={previousHref}>
              <ArrowLeft size={15} aria-hidden="true" />
              查看上一步：{steps[currentIndex - 1].label}
            </Link>
          )}
          {resumeHref && (
            <Link className="assignment-progress-resume" to={resumeHref}>
              返回当前步骤<ArrowRight size={15} aria-hidden="true" />
            </Link>
          )}
        </div>
      </nav>
    </div>
  )
}
