import { expect, test } from '@playwright/test'

test('shows the demo login shell', async ({ page }, testInfo) => {
  await page.route('**/api/v1/demo/students', async (route) => {
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify([
        { id: 'student-1', display_name: '1年级体验学生', grade: 1 },
        { id: 'student-2', display_name: '2年级体验学生', grade: 2 },
      ]),
    })
  })
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: '维学' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '选择你的年级' })).toBeVisible()
  await expect(page.getByRole('radio')).toHaveCount(2)
  await page.screenshot({ path: testInfo.outputPath('login.png'), fullPage: true })
})

test('enters the empty assignments workspace', async ({ page }) => {
  const student = { id: 'student-1', display_name: '1年级体验学生', grade: 1 }
  await page.route('**/api/v1/demo/students', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify([student]) }),
  )
  await page.route('**/api/v1/demo/login', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'demo-token', token_type: 'bearer', student }),
    }),
  )
  await page.route('**/api/v1/assignments', (route) =>
    route.fulfill({ contentType: 'application/json', body: '[]' }),
  )

  await page.goto('/login')
  await page.locator('label.grade-option').first().click()
  await page.getByRole('button', { name: /进入学习空间/ }).click()

  await expect(page).toHaveURL(/\/assignments$/)
  await expect(page.getByRole('heading', { name: '我的作业' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '新作业正在准备中' })).toBeVisible()
})

test('opens an assignment and submits an initial answer', async ({ page }, testInfo) => {
  const student = { id: 'student-3', display_name: '3年级体验学生', grade: 3 }
  const assignment = {
    id: 'assignment-3-1',
    title: '校园里的安静角落',
    prompt: '学校里是否应该设置一个安静角落？请说清楚你的观点和理由。',
    grade: 3,
    published_at: '2026-01-01T00:00:00Z',
    deadline: '2027-07-01T00:00:00Z',
    availability: 'OPEN',
    session: null,
  }
  const draftSnapshot = {
    id: 'session-1',
    assignment_id: assignment.id,
    student_id: student.id,
    version: 1,
    phase: 'INITIAL_DRAFT',
    mode: 'INITIAL',
    submission_status: 'DRAFT',
    allowed_actions: ['SUBMIT_INITIAL_ANSWER'],
    next_view: 'INITIAL_DRAFT',
    jobs: { initial_analysis: { status: 'IDLE', error_code: null } },
    initial_answer: null,
    deadline: assignment.deadline,
    server_time: '2026-08-14T00:00:00Z',
  }
  let currentSnapshot: typeof draftSnapshot | null = null

  await page.route('**/api/v1/demo/students', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify([student]) }),
  )
  await page.route('**/api/v1/demo/login', (route) =>
    route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({ access_token: 'demo-token', token_type: 'bearer', student }),
    }),
  )
  await page.route('**/api/v1/assignments', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify([{ ...assignment, session: currentSnapshot }]) }),
  )
  await page.route(`**/api/v1/assignments/${assignment.id}`, (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ...assignment, session: currentSnapshot }) }),
  )
  await page.route('**/api/v1/sessions', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    expect(route.request().headers()['idempotency-key']).toMatch(/^[0-9a-f-]{36}$/)
    currentSnapshot = draftSnapshot
    await route.fulfill({ status: 201, contentType: 'application/json', body: JSON.stringify(draftSnapshot) })
  })
  await page.route('**/api/v1/sessions/session-1', (route) =>
    route.fulfill({ contentType: 'application/json', body: JSON.stringify(currentSnapshot ?? draftSnapshot) }),
  )
  await page.route('**/api/v1/sessions/session-1/initial-answer', async (route) => {
    const body = route.request().postDataJSON()
    expect(body.expected_version).toBe(1)
    expect(body.answer).toContain('应该设置安静角落')
    expect(route.request().headers()['idempotency-key']).toMatch(/^[0-9a-f-]{36}$/)
    currentSnapshot = {
      ...draftSnapshot,
      version: 2,
      phase: 'INITIAL_ANALYSIS',
      allowed_actions: [],
      next_view: 'INITIAL_ANALYSIS_PENDING',
      jobs: { initial_analysis: { status: 'QUEUED', error_code: null } },
      initial_answer: body.answer,
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(currentSnapshot) })
  })

  await page.goto('/login')
  await page.locator('label.grade-option').click()
  await page.getByRole('button', { name: /进入学习空间/ }).click()
  await page.getByRole('link', { name: /校园里的安静角落/ }).click()
  await expect(page.getByRole('heading', { name: '校园里的安静角落' })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('assignment-detail.png'), fullPage: true })
  await page.getByRole('button', { name: '开始作答' }).click()

  const textarea = page.getByLabel('我的初答')
  await textarea.fill('我认为学校应该设置安静角落，因为想阅读的同学需要一个不被打扰的地方。')
  await page.getByRole('button', { name: '提交初答' }).click()

  await expect(page).toHaveURL(/\/sessions\/session-1\/analysis-pending$/)
  await expect(page.getByRole('heading', { name: '初答已经保存' })).toBeVisible()
  await expect(page.getByText(/学校应该设置安静角落/)).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('analysis-pending.png'), fullPage: true })
})

test('shows the completed initial analysis', async ({ page }, testInfo) => {
  const student = { id: 'student-3', display_name: '3年级体验学生', grade: 3 }
  const token = 'demo-token'
  const snapshot = {
    id: 'session-result', assignment_id: 'assignment-3-1', student_id: student.id, version: 2,
    phase: 'INITIAL_ANALYSIS', mode: 'INITIAL', submission_status: 'DRAFT', allowed_actions: ['START_FINAL_DRAFT'],
    next_view: 'INITIAL_ANALYSIS', jobs: { initial_analysis: { status: 'SUCCEEDED', error_code: null }, final_evaluation: { status: 'IDLE', error_code: null } },
    initial_answer: '我认为学校应该设置安静角落，因为有些同学需要一个不被打扰的地方阅读。',
    current_submission_id: null, final_answer: null,
    deadline: '2027-07-01T00:00:00Z', server_time: '2026-08-14T00:00:00Z',
  }
  const elements = ['viewpoint', 'reasons', 'evidence', 'counterpoint', 'response', 'conditions'].map((element, index) => ({
    element, status: index === 0 ? 'present' : index === 1 ? 'emerging' : 'missing',
    summary: index === 0 ? '已经表达了自己的主要看法。' : '这里还可以继续补充。',
    quotes: index === 0 ? ['我认为学校应该设置安静角落'] : [],
  }))
  await page.addInitScript(({ token, student }) => sessionStorage.setItem('weixue-demo-auth', JSON.stringify({ token, student })), { token, student })
  await page.route('**/api/v1/sessions/session-result', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(snapshot) }))
  await page.route('**/api/v1/sessions/session-result/initial-analysis', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({
    session_id: snapshot.id, input_version: 2, initial_answer: snapshot.initial_answer,
    analysis: { schema_version: 'initial-analysis-v1', elements, priority_improvement: { element: 'evidence', suggestion: '补充一个校园里的具体例子，说明这个理由为什么成立。' } },
  }) }))
  let currentSnapshot = snapshot
  await page.route('**/api/v1/sessions/session-result/final-draft', async (route) => {
    const body = route.request().postDataJSON()
    expect(body.expected_version).toBe(2)
    expect(route.request().headers()['idempotency-key']).toMatch(/^[0-9a-f-]{36}$/)
    currentSnapshot = { ...snapshot, version: 3, phase: 'FINAL_DRAFT', allowed_actions: ['SUBMIT_FINAL_ANSWER'], next_view: 'FINAL_DRAFT' }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(currentSnapshot) })
  })
  await page.route('**/api/v1/sessions/session-result/final-answer', async (route) => {
    const body = route.request().postDataJSON()
    expect(body.expected_version).toBe(3)
    expect(body.answer).toContain('例如图书角')
    expect(route.request().headers()['idempotency-key']).toMatch(/^[0-9a-f-]{36}$/)
    currentSnapshot = {
      ...currentSnapshot, version: 4, phase: 'RESULT', submission_status: 'SUBMITTED', allowed_actions: [],
      next_view: 'FINAL_EVALUATION_PENDING', current_submission_id: 'submission-1', final_answer: body.answer,
      jobs: { ...snapshot.jobs, final_evaluation: { status: 'QUEUED', error_code: null } },
    }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(currentSnapshot) })
  })
  await page.route('**/api/v1/sessions/session-result', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(currentSnapshot) }))

  await page.goto('/sessions/session-result/analysis-pending')
  await expect(page).toHaveURL(/\/sessions\/session-result\/initial-analysis$/)
  await expect(page.getByRole('heading', { name: '看看你已经表达清楚了什么' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '表达要素' })).toBeVisible()
  await expect(page.locator('.element-row')).toHaveCount(6)
  await expect(page.getByText('补充一个校园里的具体例子')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('initial-analysis.png'), fullPage: true })
  await page.getByRole('button', { name: '结束辅导，准备最终提交' }).click()
  await expect(page).toHaveURL(/\/sessions\/session-result\/final-answer$/)
  const finalAnswer = page.getByLabel('我的修改稿')
  await expect(finalAnswer).toHaveValue(snapshot.initial_answer)
  await finalAnswer.fill('我赞成学校设置安静角落。例如图书角在课间常有人阅读，减少谈话声能让他们更专心。')
  await page.screenshot({ path: testInfo.outputPath('final-draft.png'), fullPage: true })
  await page.getByRole('button', { name: '提交修改稿' }).click()
  await expect(page).toHaveURL(/\/sessions\/session-result\/evaluation-pending$/)
  await expect(page.getByRole('heading', { name: '修改稿已经提交' })).toBeVisible()
  await expect(page.getByText(/例如图书角/)).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('evaluation-pending.png'), fullPage: true })
})

test('shows the completed final evaluation report', async ({ page }, testInfo) => {
  const student = { id: 'student-3', display_name: '3年级体验学生', grade: 3 }
  const snapshot = {
    id: 'session-evaluated', assignment_id: 'assignment-3-1', student_id: student.id, version: 4,
    phase: 'RESULT', mode: 'INITIAL', submission_status: 'SUBMITTED', allowed_actions: [], next_view: 'RESULT',
    jobs: { initial_analysis: { status: 'SUCCEEDED', error_code: null }, final_evaluation: { status: 'SUCCEEDED', error_code: null } },
    initial_answer: '我认为学校应该设置安静角落，因为有些同学需要一个不被打扰的地方阅读。', current_submission_id: 'submission-1',
    final_answer: '我赞成学校设置安静角落。例如图书角在课间常有人阅读，减少谈话声能让他们更专心。',
    deadline: '2027-07-01T00:00:00Z', server_time: '2026-08-14T00:00:00Z',
  }
  const dimensions = ['idea', 'material', 'structure', 'language', 'perspective'].map((dimension, index) => ({
    dimension, status: index === 0 ? 'clear' : index === 4 ? 'not_yet_visible' : 'developing',
    observation: index === 0 ? '主要观点清楚。' : '这里还可以继续发展。', quotes: index === 0 ? ['我赞成学校设置安静角落'] : [],
  }))
  await page.addInitScript(({ student }) => sessionStorage.setItem('weixue-demo-auth', JSON.stringify({ token: 'demo-token', student })), { student })
  await page.route('**/api/v1/sessions/session-evaluated', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(snapshot) }))
  await page.route('**/api/v1/sessions/session-evaluated/final-evaluation', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({
    session_id: snapshot.id, submission_id: 'submission-1', initial_answer: snapshot.initial_answer, final_answer: snapshot.final_answer,
    evaluation: {
      schema_version: 'final-evaluation-v1', rubric_version: 'argument-writing-v1', summary: '终稿保留了原来的观点，并用更具体的内容支持了表达。',
      strengths: [{ title: '观点清楚', explanation: '开头直接说明了自己的看法。', quotes: ['我赞成学校设置安静角落'] }],
      next_step: { dimension: 'perspective', suggestion: '下一次可以想一想持不同看法的人会担心什么，并作出回应。' },
      dimensions, revision_evidence: [{ change: '终稿补充了具体例子。', initial_quote: '需要一个不被打扰的地方阅读', final_quote: '例如图书角在课间常有人阅读' }],
    },
  }) }))
  await page.goto('/sessions/session-evaluated/evaluation-pending')
  await expect(page).toHaveURL(/\/sessions\/session-evaluated\/result$/)
  await expect(page.getByRole('heading', { name: '这一次，你把想法说得更完整了' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '做得好的' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '从初答到终稿' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '五个表达维度' })).toBeVisible()
  await expect(page.getByText('终稿补充了具体例子。')).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath('result.png'), fullPage: true })
})

test('retries a recoverable final evaluation failure', async ({ page }) => {
  const student = { id: 'student-3', display_name: '3年级体验学生', grade: 3 }
  const failed = {
    id: 'session-retry', assignment_id: 'assignment-3-1', student_id: student.id, version: 4,
    phase: 'RESULT', mode: 'INITIAL', submission_status: 'SUBMITTED', allowed_actions: ['RETRY_FINAL_EVALUATION'],
    next_view: 'FINAL_EVALUATION_PENDING', jobs: { initial_analysis: { status: 'SUCCEEDED', error_code: null }, final_evaluation: { status: 'FAILED_RETRYABLE', error_code: 'AI_PROVIDER_ERROR' } },
    initial_answer: '初答', current_submission_id: 'submission-1', final_answer: '已经安全保存的终稿',
    deadline: '2027-07-01T00:00:00Z', server_time: '2026-08-14T00:00:00Z',
  }
  const queued = { ...failed, version: 5, allowed_actions: [], jobs: { ...failed.jobs, final_evaluation: { status: 'QUEUED', error_code: null } } }
  await page.addInitScript(({ student }) => sessionStorage.setItem('weixue-demo-auth', JSON.stringify({ token: 'demo-token', student })), { student })
  await page.route('**/api/v1/sessions/session-retry', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(failed) }))
  await page.route('**/api/v1/sessions/session-retry/final-evaluation/retry', async (route) => {
    expect(route.request().postDataJSON().expected_version).toBe(4)
    expect(route.request().headers()['idempotency-key']).toMatch(/^[0-9a-f-]{36}$/)
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(queued) })
  })
  await page.goto('/sessions/session-retry/evaluation-pending')
  await expect(page.getByRole('heading', { name: '这次评价没有完成' })).toBeVisible()
  await page.getByRole('button', { name: '重新评价' }).click()
  await expect(page.getByText('当前状态：等待评价')).toBeVisible()
  await expect(page.getByRole('button', { name: '重新评价' })).toHaveCount(0)
})

test('shows the complete thinking growth report without viewport overflow', async ({ page }, testInfo) => {
  const student = { id: 'student-3', display_name: '3年级体验学生', grade: 3 }
  const names = ['思辨态度', '信息判别', '逻辑推理', '论证建构', '思辨表达']
  const keys = ['attitude', 'information', 'reasoning', 'argument', 'expression']
  const points = [1, 2, 3].map((level, index) => ({
    session_id: `growth-session-${index}`, assignment_id: `growth-assignment-${index}`,
    assignment_title: `校园思考任务 ${index + 1}`, submitted_at: `2026-0${index + 2}-01T00:00:00Z`,
    grade: index === 0 ? 2 : 3, level: ['暂未体现', '正在发展', '表达清楚'][level - 1],
    level_value: level, eligible: true, quote: `这是第 ${index + 1} 份作业中可以定位的学生原话。`, observation: '能够找到对应原文。',
  }))
  const report = {
    selected_grade: null, student_grade: 3,
    coverage: { completed_assignments: 3, trend_eligible_assignments: 3, available_grades: [2, 3] },
    dimensions: names.map((name, index) => ({ key: keys[index], name, current_level: '表达清楚', current_value: 3, stable_level: '正在发展', evidence_count: 3, points })),
    timeline: [...points].reverse().map((point, index) => ({
      session_id: point.session_id, assignment_id: point.assignment_id, assignment_title: point.assignment_title,
      submitted_at: point.submitted_at, grade: point.grade, used_coaching: index !== 2, coaching_rounds: index !== 2 ? 2 : 0,
      status: 'INCLUDED', representative_dimensions: ['思辨态度', '论证建构'], quote: point.quote,
    })),
    thinking_moves: ['说出看法', '说出为什么', '用材料支撑', '看见别的想法', '回应不同想法', '说清条件'].map((name, index) => ({
      key: `move-${index}`, name, student_label: `我会${name}`, count: index < 4 ? 2 : 1,
      evidence: [{ session_id: 'growth-session-2', assignment_title: '校园思考任务 3', quote: '可以定位的学生原话。' }],
    })),
    narrative: '已经根据 3 份已完成作业整理五维成长证据。思辨态度和论证建构正在形成稳定表现。',
    teacher_confirmation: { available: false, confirmed_count: 0, total_count: 3 },
  }

  await page.addInitScript(({ student }) => sessionStorage.setItem('weixue-demo-auth', JSON.stringify({ token: 'demo-token', student })), { student })
  await page.route('**/api/v1/growth?grade=*', (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(report) }))
  await page.goto('/growth')

  await expect(page.getByRole('heading', { name: '我的思考成长' })).toBeVisible()
  await expect(page.getByRole('img', { name: '最近一次作业的五维表现图' })).toBeVisible()
  await expect(page.getByRole('img', { name: /趋势，共 3 个可比较节点/ })).toHaveCount(5)
  await expect(page.getByRole('heading', { name: '思考动作积累' })).toBeVisible()
  await expect(page.getByRole('progressbar')).toHaveCount(6)
  await expect(page.getByRole('heading', { name: '作业学习轨迹' })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('growth-report.png'), fullPage: true })
})
