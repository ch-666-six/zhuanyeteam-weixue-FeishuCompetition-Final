import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, BookOpen, Check, Pencil, Plus, RefreshCw, Trash2, X } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { ManagedAssignment } from '../../shared/api/types'
import { ApiError } from '../../shared/api/http'
import { Button } from '../../shared/ui/Button'
import { bulkDeleteManagedAssignments, createManagedAssignment, listManagedAssignments, updateManagedAssignment } from './api'

const GRADES = [1, 2, 3, 4, 5, 6, 7]

export function QuestionManagementPage() {
  const queryClient = useQueryClient()
  const [grades, setGrades] = useState<number[]>([1])
  const [title, setTitle] = useState('')
  const [prompt, setPrompt] = useState('')
  const [editingId, setEditingId] = useState<string | null>(null)
  const [filterGrade, setFilterGrade] = useState<'all' | number>('all')
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [confirmBulkDelete, setConfirmBulkDelete] = useState(false)
  const [message, setMessage] = useState('')
  const assignmentsQuery = useQuery({ queryKey: ['managed-assignments'], queryFn: listManagedAssignments })

  async function refreshAssignments() {
    await queryClient.invalidateQueries({ queryKey: ['managed-assignments'] })
    await queryClient.invalidateQueries({ queryKey: ['assignments'] })
  }

  function resetForm() {
    setEditingId(null)
    setGrades([1])
    setTitle('')
    setPrompt('')
  }

  const createMutation = useMutation({
    mutationFn: createManagedAssignment,
    onSuccess: async (created) => {
      resetForm()
      setMessage(`题目已发布到 ${created.length} 个年级。`)
      await refreshAssignments()
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : '题目添加失败。'),
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, input }: { id: string; input: { title: string; prompt: string; grade: number } }) => updateManagedAssignment(id, input),
    onSuccess: async () => {
      resetForm()
      setMessage('题目修改已保存。')
      await refreshAssignments()
    },
    onError: (error) => setMessage(error instanceof Error ? error.message : '题目修改失败。'),
  })
  const bulkDeleteMutation = useMutation({
    mutationFn: bulkDeleteManagedAssignments,
    onSuccess: async (result) => {
      setSelectedIds(result.blocked_ids)
      setConfirmBulkDelete(false)
      const parts = [`已删除 ${result.deleted_ids.length} 道题目`]
      if (result.blocked_ids.length) parts.push(`${result.blocked_ids.length} 道因已有学习记录而保留`)
      if (result.not_found_ids.length) parts.push(`${result.not_found_ids.length} 道已不存在`)
      setMessage(`${parts.join('，')}。`)
      await refreshAssignments()
    },
    onError: (error) => {
      setConfirmBulkDelete(false)
      setMessage(error instanceof ApiError ? error.message : '批量删除失败。')
    },
  })

  function toggleGrade(grade: number) {
    setGrades((current) => current.includes(grade) ? current.filter((item) => item !== grade) : [...current, grade].sort())
  }

  function beginEdit(assignment: ManagedAssignment) {
    setEditingId(assignment.id)
    setGrades([assignment.grade])
    setTitle(assignment.title)
    setPrompt(assignment.prompt)
    setMessage('')
  }

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setMessage('')
    if (editingId) {
      updateMutation.mutate({ id: editingId, input: { grade: grades[0], title: title.trim(), prompt: prompt.trim() } })
    } else {
      createMutation.mutate({ grades, title: title.trim(), prompt: prompt.trim() })
    }
  }

  const assignments = assignmentsQuery.data ?? []
  const visibleAssignments = filterGrade === 'all' ? assignments : assignments.filter((item) => item.grade === filterGrade)
  const visibleIds = visibleAssignments.map((item) => item.id)
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id))
  const pendingSave = createMutation.isPending || updateMutation.isPending

  return <main className="question-management-page">
    <header className="management-topbar">
      <Link className="management-brand" to="/login"><span><BookOpen size={20} aria-hidden="true" /></span>维学</Link>
      <Link className="button button--quiet" to="/login"><ArrowLeft size={17} aria-hidden="true" />返回登录</Link>
    </header>
    <div className="management-content">
      <header className="management-heading"><div><p className="eyebrow">内容管理</p><h1>题目管理</h1><p>按年级发布、筛选和维护学生学习空间中的题目。</p></div><strong>{assignments.length}<span>道题目</span></strong></header>
      {message && <p className="management-message" role="status">{message}</p>}
      <div className="management-layout">
        <section className="management-form-section" aria-labelledby="question-form-title">
          <div className="management-section-heading">{editingId ? <Pencil size={19} aria-hidden="true" /> : <Plus size={19} aria-hidden="true" />}<div><p className="eyebrow">{editingId ? '编辑' : '新增'}</p><h2 id="question-form-title">{editingId ? '修改题目' : '批量发布题目'}</h2></div></div>
          <form onSubmit={handleSubmit} className="management-form">
            {editingId ? <label>适用年级<select value={grades[0]} onChange={(event) => setGrades([Number(event.target.value)])}>{GRADES.map((grade) => <option key={grade} value={grade}>{grade} 年级</option>)}</select></label> : <fieldset className="management-grade-fieldset"><legend>适用年级（可多选）</legend><div className="management-grade-options">{GRADES.map((grade) => <label key={grade}><input type="checkbox" checked={grades.includes(grade)} onChange={() => toggleGrade(grade)} /><span>{grade} 年级</span><Check size={14} aria-hidden="true" /></label>)}</div></fieldset>}
            <label>题目名称<input required minLength={2} maxLength={160} value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如：校园里的安静角落" /></label>
            <label>题目内容<textarea required minLength={5} maxLength={3000} rows={7} value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="写下学生需要思考和回答的完整问题。" /></label>
            <div className="management-form-actions"><Button type="submit" disabled={pendingSave || grades.length === 0 || title.trim().length < 2 || prompt.trim().length < 5}>{editingId ? <Pencil size={17} aria-hidden="true" /> : <Plus size={17} aria-hidden="true" />}{pendingSave ? '正在保存…' : editingId ? '保存修改' : `发布到 ${grades.length} 个年级`}</Button>{editingId && <Button type="button" variant="quiet" onClick={resetForm}><X size={17} aria-hidden="true" />取消编辑</Button>}</div>
          </form>
        </section>
        <section className="management-list-section" aria-labelledby="question-list-title">
          <div className="management-list-header"><div className="management-section-heading"><BookOpen size={19} aria-hidden="true" /><div><p className="eyebrow">题库</p><h2 id="question-list-title">题目列表</h2></div></div><label className="management-filter">筛选年级<select value={filterGrade} onChange={(event) => { setFilterGrade(event.target.value === 'all' ? 'all' : Number(event.target.value)); setSelectedIds([]); setConfirmBulkDelete(false) }}><option value="all">全部年级</option>{GRADES.map((grade) => <option key={grade} value={grade}>{grade} 年级</option>)}</select></label></div>
          {assignmentsQuery.isPending && <p className="status-line" aria-live="polite">正在读取题目…</p>}
          {assignmentsQuery.isError && <div className="management-load-error" role="alert"><p>暂时无法读取题目。</p><Button variant="quiet" onClick={() => assignmentsQuery.refetch()}><RefreshCw size={16} aria-hidden="true" />重新加载</Button></div>}
          {assignmentsQuery.data && visibleAssignments.length === 0 && <p className="management-empty">当前筛选下还没有题目。</p>}
          {visibleAssignments.length > 0 && <div className="management-bulk-toolbar"><label><input type="checkbox" checked={allVisibleSelected} onChange={() => setSelectedIds((current) => allVisibleSelected ? current.filter((id) => !visibleIds.includes(id)) : [...new Set([...current, ...visibleIds])])} />全选当前 {visibleAssignments.length} 道</label><span>{selectedIds.length} 道已选择</span>{selectedIds.length > 0 && (confirmBulkDelete ? <div><span>确认批量删除？</span><Button variant="quiet" onClick={() => bulkDeleteMutation.mutate(selectedIds)} disabled={bulkDeleteMutation.isPending}><Trash2 size={16} aria-hidden="true" />{bulkDeleteMutation.isPending ? '正在删除…' : '确认删除'}</Button><button type="button" onClick={() => setConfirmBulkDelete(false)}>取消</button></div> : <button type="button" className="managed-bulk-delete" onClick={() => setConfirmBulkDelete(true)}><Trash2 size={16} aria-hidden="true" />批量删除</button>)}</div>}
          <ol className="managed-question-list">
            {visibleAssignments.map((assignment) => <li key={assignment.id} className={selectedIds.includes(assignment.id) ? 'is-selected' : undefined}>
              <label className="managed-select"><input type="checkbox" checked={selectedIds.includes(assignment.id)} onChange={() => { setSelectedIds((current) => current.includes(assignment.id) ? current.filter((id) => id !== assignment.id) : [...current, assignment.id]); setConfirmBulkDelete(false) }} /><span className="sr-only">选择题目：{assignment.title}</span></label>
              <div className="managed-question-grade">{assignment.grade}<span>年级</span></div>
              <div className="managed-question-copy"><h3>{assignment.title}</h3><p>{assignment.prompt}</p></div>
              <div className="managed-question-actions"><button type="button" className="managed-edit" onClick={() => beginEdit(assignment)} aria-label={`修改题目：${assignment.title}`}><Pencil size={17} aria-hidden="true" /></button><button type="button" className="managed-delete" onClick={() => { setSelectedIds([assignment.id]); setConfirmBulkDelete(true); setMessage('') }} aria-label={`删除题目：${assignment.title}`}><Trash2 size={17} aria-hidden="true" /></button></div>
            </li>)}
          </ol>
        </section>
      </div>
    </div>
  </main>
}
