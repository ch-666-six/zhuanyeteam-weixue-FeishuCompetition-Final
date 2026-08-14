export interface DemoStudent {
  id: string
  display_name: string
  grade: number
}

export interface DemoLoginResponse {
  access_token: string
  token_type: 'bearer'
  student: DemoStudent
}

export interface AssignmentSummary {
  id: string
  title: string
  prompt: string
  grade: number
  deadline: string | null
  availability: 'OPEN' | 'CLOSED'
  session: SessionSnapshot | null
}

export interface AssignmentDetail extends AssignmentSummary {
  published_at: string | null
}

export interface ManagedAssignment {
  id: string
  title: string
  prompt: string
  grade: number
  published_at: string | null
  created_at: string
}

export type SessionPhase = 'INITIAL_DRAFT' | 'INITIAL_ANALYSIS' | 'COACHING' | 'FINAL_DRAFT' | 'RESULT'
export type SessionNextView =
  | 'INITIAL_DRAFT'
  | 'INITIAL_ANALYSIS_PENDING'
  | 'INITIAL_ANALYSIS'
  | 'COACHING_PENDING'
  | 'COACHING'
  | 'FINAL_DRAFT'
  | 'FINAL_EVALUATION_PENDING'
  | 'RESULT'

export interface SessionSnapshot {
  id: string
  assignment_id: string
  student_id: string
  version: number
  phase: SessionPhase
  mode: 'INITIAL'
  submission_status: 'DRAFT' | 'SUBMITTED'
  allowed_actions: string[]
  next_view: SessionNextView
  jobs: {
    initial_analysis: {
      status: 'IDLE' | 'QUEUED' | 'RUNNING' | 'FAILED_RETRYABLE' | 'FAILED_FINAL' | 'SUCCEEDED'
      error_code: string | null
    }
    final_evaluation: {
      status: 'IDLE' | 'QUEUED' | 'RUNNING' | 'FAILED_RETRYABLE' | 'FAILED_FINAL' | 'SUCCEEDED'
      error_code: string | null
    }
    coaching_question: {
      status: 'IDLE' | 'QUEUED' | 'RUNNING' | 'FAILED_RETRYABLE' | 'FAILED_FINAL' | 'SUCCEEDED'
      error_code: string | null
    }
  }
  coaching: {
    status: 'NOT_STARTED' | 'ACTIVE' | 'ENDED_BY_STUDENT' | 'ENDED_BY_LIMIT' | 'SKIPPED'
    current_round: number
    completed_rounds: number
    max_rounds: number
    current_turn_id: string | null
  }
  initial_answer: string | null
  current_submission_id: string | null
  final_answer: string | null
  deadline: string | null
  server_time: string
}

export type AnalysisElementName = 'viewpoint' | 'reasons' | 'evidence' | 'counterpoint' | 'response' | 'conditions'

export interface InitialAnalysisResult {
  session_id: string
  input_version: number
  initial_answer: string
  analysis: {
    schema_version: 'initial-analysis-v1' | 'initial-analysis-v2'
    elements: Array<{
      element: AnalysisElementName
      status: 'present' | 'emerging' | 'missing'
      summary: string
      quotes: string[]
    }>
    priority_improvement: { element: AnalysisElementName; suggestion: string } | null
    opening_question?: {
      question: string
      focus_element: AnalysisElementName
      scaffold_type: string
    }
  }
}

export interface CoachingTurn {
  id: string
  round_number: number
  question_text: string | null
  focus_element: AnalysisElementName | null
  scaffold_type: string | null
  student_response: string | null
  status: 'WAITING' | 'READY' | 'ANSWERED' | 'FAILED'
}

export interface CoachingRecord {
  session_id: string
  status: 'ACTIVE' | 'ENDED_BY_STUDENT' | 'ENDED_BY_LIMIT' | 'SKIPPED'
  current_round: number
  max_rounds: number
  turns: CoachingTurn[]
}

export type EvaluationDimensionName = 'idea' | 'material' | 'structure' | 'language' | 'perspective'

export interface FinalEvaluationResult {
  session_id: string
  submission_id: string
  initial_answer: string
  final_answer: string
  evaluation: {
    schema_version: 'final-evaluation-v1'
    rubric_version: 'argument-writing-v1'
    summary: string
    strengths: Array<{ title: string; explanation: string; quotes: string[] }>
    next_step: { dimension: EvaluationDimensionName; suggestion: string }
    dimensions: Array<{
      dimension: EvaluationDimensionName
      status: 'clear' | 'developing' | 'not_yet_visible'
      observation: string
      quotes: string[]
    }>
    revision_evidence: Array<{ change: string; initial_quote: string; final_quote: string }>
  }
}

export type GrowthLevel = '暂未体现' | '正在发展' | '表达清楚'

export interface GrowthPoint {
  session_id: string
  assignment_id: string
  assignment_title: string
  submitted_at: string
  grade: number
  level: GrowthLevel
  level_value: 1 | 2 | 3
  eligible: boolean
  quote: string | null
  observation: string
}

export interface GrowthReport {
  selected_grade: number | null
  student_grade: number
  coverage: {
    completed_assignments: number
    trend_eligible_assignments: number
    available_grades: number[]
  }
  dimensions: Array<{
    key: 'attitude' | 'information' | 'reasoning' | 'argument' | 'expression'
    name: string
    current_level: GrowthLevel | null
    current_value: 1 | 2 | 3 | null
    stable_level: GrowthLevel | null
    evidence_count: number
    summary: string
    points: GrowthPoint[]
  }>
  timeline: Array<{
    session_id: string
    assignment_id: string
    assignment_title: string
    submitted_at: string
    grade: number
    used_coaching: boolean
    coaching_rounds: number
    status: 'INCLUDED' | 'EVIDENCE_INCOMPLETE'
    representative_dimensions: string[]
    quote: string | null
  }>
  thinking_moves: Array<{
    key: string
    name: string
    student_label: string
    count: number
    evidence: Array<{ session_id: string; assignment_title: string; quote: string }>
  }>
  narrative: string
  teacher_confirmation: {
    available: boolean
    confirmed_count: number
    total_count: number
  }
}
