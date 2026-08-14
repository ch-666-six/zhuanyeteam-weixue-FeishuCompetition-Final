# 思辨表达 AI 助教：会话状态与动作规范

> 状态：MVP 领域契约  
> 更新日期：2026-08-14  
> 关联文档：[产品范围](./product-scope.md) · [架构决策](./architecture-decisions.md)

## 1. 目的

本文定义作答会话的服务端事实来源。后端据此判断允许动作、状态迁移和下一视图；前端只能消费会话快照，不得用本地标记另建一套流程。

本规范只覆盖 MVP 文字闭环。辅导、修订和语音在进入对应增量前，通过更新本文显式加入。

## 2. 状态不是一个枚举

一个会话由多个正交维度组成，避免把业务阶段、提交结果和异步任务压进同一个状态枚举。

### 2.1 学习阶段 `phase`

| 值 | 含义 |
|---|---|
| `INITIAL_DRAFT` | 等待学生提交初答 |
| `INITIAL_ANALYSIS` | 初答已提交，等待或查看初析 |
| `COACHING` | 学生选择参加启发式辅导，等待问题或回答当前问题 |
| `FINAL_DRAFT` | 学生独立编写终答 |
| `RESULT` | 终答已提交，等待或查看评价 |

### 2.2 流程模式 `mode`

MVP 只允许 `INITIAL`。后续版本可以加入 `REVISION_DIRECT` 和 `REVISION_WITH_AI`，但不能用 JSON 元数据或浏览器存储表达模式。

### 2.3 提交状态 `submissionStatus`

| 值 | 含义 |
|---|---|
| `DRAFT` | 尚无最终提交版本 |
| `SUBMITTED` | 已存在当前最终答案版本 |

### 2.4 AI 任务状态

初析和最终评价分别表达，不设置含义模糊的单一 `jobStatus`。

| 值 | 含义 |
|---|---|
| `IDLE` | 尚未创建任务 |
| `QUEUED` | 已持久化，等待 worker 认领 |
| `RUNNING` | worker 已持有有效租约 |
| `FAILED_RETRYABLE` | 失败且允许用户或系统重试 |
| `FAILED_FINAL` | 达到最大次数或错误不可重试 |
| `SUCCEEDED` | 已保存通过校验的领域结果 |

## 3. 服务端会话快照

所有读取会话和写操作成功响应都返回同一结构的 `SessionSnapshot`：

```json
{
  "id": "8e455a57-83ef-43b1-ae3c-8d15bcf99fcc",
  "assignmentId": "c37af460-e165-4e76-af8c-555dcdedc242",
  "studentId": "0f853574-48a7-4c1f-9ace-2f19fbde728a",
  "version": 3,
  "phase": "INITIAL_ANALYSIS",
  "mode": "INITIAL",
  "submissionStatus": "DRAFT",
  "allowedActions": ["RETRY_INITIAL_ANALYSIS"],
  "nextView": "INITIAL_ANALYSIS",
  "jobs": {
    "initialAnalysis": {
      "status": "FAILED_RETRYABLE",
      "errorCode": "AI_TEMPORARILY_UNAVAILABLE"
    },
    "finalEvaluation": {
      "status": "IDLE",
      "errorCode": null
    }
  },
  "currentSubmissionId": null,
  "deadline": "2026-09-01T08:00:00Z",
  "serverTime": "2026-08-14T06:00:00Z"
}
```

约束：

- 枚举由 OpenAPI 导出给前端，不使用宽泛 `string`。
- `nextView` 是稳定的产品视图标识，不是 React URL。
- 前端维护唯一一处 `nextView -> route` 映射；页面本身不判断状态到路径。
- `allowedActions` 决定按钮是否出现及是否可用，但后端仍需再次校验。
- `version` 每次业务可见状态变化后递增，用于乐观并发控制。
- 所有时间使用带时区的 UTC ISO 8601 值，截止判断以 `serverTime` 为准。

## 4. 动作定义

| 动作 | 前置条件 | 成功结果 |
|---|---|---|
| `CREATE_SESSION` | 作业已发布、未截止、学生有权限且无现存会话 | 创建会话，进入 `INITIAL_DRAFT` |
| `SUBMIT_INITIAL_ANSWER` | `INITIAL_DRAFT`，初答有效 | 保存初答，创建初析任务，进入 `INITIAL_ANALYSIS` |
| `RETRY_INITIAL_ANALYSIS` | 初析为 `FAILED_RETRYABLE` | 创建或重新排队同一逻辑任务 |
| `OPEN_INITIAL_ANALYSIS` | 初析为 `SUCCEEDED` | 保持阶段，返回已验证分析 |
| `START_FINAL_DRAFT` | 初析为 `SUCCEEDED` | 进入 `FINAL_DRAFT` |
| `START_COACHING` | 初析为 `SUCCEEDED` 且辅导未开始 | 激活首问并进入 `COACHING` |
| `SUBMIT_COACHING_RESPONSE` | `COACHING`、当前问题已就绪且未回答 | 保存回答；未满 20 轮时创建下一问任务，否则进入 `FINAL_DRAFT` |
| `END_COACHING` | `COACHING` | 结束辅导并进入 `FINAL_DRAFT` |
| `SUBMIT_FINAL_ANSWER` | `FINAL_DRAFT`，终答有效且未截止 | 创建不可变提交版本与评价任务，进入 `RESULT` |
| `RETRY_FINAL_EVALUATION` | 评价为 `FAILED_RETRYABLE` | 创建或重新排队同一逻辑任务 |
| `OPEN_RESULT` | 评价为 `SUCCEEDED` | 保持 `RESULT`，返回已验证评价 |

`OPEN_*` 是读取权限语义，不必实现为写接口。它们出现在 `allowedActions` 中，用于明确结果是否已经可展示。

## 5. 状态迁移

```text
CREATE_SESSION
  -> INITIAL_DRAFT

INITIAL_DRAFT
  -- SUBMIT_INITIAL_ANSWER --> INITIAL_ANALYSIS / QUEUED

INITIAL_ANALYSIS
  -- worker succeeds ------> INITIAL_ANALYSIS / SUCCEEDED
  -- worker retryable fail -> INITIAL_ANALYSIS / FAILED_RETRYABLE
  -- START_FINAL_DRAFT ----> FINAL_DRAFT（跳过辅导）
  -- START_COACHING -------> COACHING

COACHING
  -- SUBMIT_COACHING_RESPONSE / round < 20 --> COACHING / next question QUEUED
  -- SUBMIT_COACHING_RESPONSE / round = 20 --> FINAL_DRAFT / ENDED_BY_LIMIT
  -- END_COACHING --------------------------> FINAL_DRAFT / ENDED_BY_STUDENT

FINAL_DRAFT
  -- SUBMIT_FINAL_ANSWER --> RESULT / evaluation QUEUED / SUBMITTED

RESULT
  -- worker succeeds ------> RESULT / evaluation SUCCEEDED
  -- worker retryable fail -> RESULT / evaluation FAILED_RETRYABLE
```

阶段迁移只允许通过领域函数执行，例如：

```python
apply_action(snapshot, action, command) -> DomainEvents
```

API、worker、数据迁移和管理脚本均不得直接给 `phase` 赋值。Worker 只推进与其任务对应的任务状态和结果，不改变学生学习阶段。

## 6. `nextView` 规则

| 条件 | `nextView` |
|---|---|
| `phase = INITIAL_DRAFT` | `INITIAL_DRAFT` |
| `phase = INITIAL_ANALYSIS` 且任务未成功 | `INITIAL_ANALYSIS_PENDING` |
| `phase = INITIAL_ANALYSIS` 且任务成功 | `INITIAL_ANALYSIS` |
| `phase = COACHING` 且问题未成功 | `COACHING_PENDING` |
| `phase = COACHING` 且问题成功 | `COACHING` |
| `phase = FINAL_DRAFT` | `FINAL_DRAFT` |
| `phase = RESULT` 且评价未成功 | `FINAL_EVALUATION_PENDING` |
| `phase = RESULT` 且评价成功 | `RESULT` |

规则优先级和返回值由一个纯函数维护，并以表驱动测试覆盖所有组合。若数据库出现无法解释的组合，接口返回可诊断的 `INCONSISTENT_SESSION_STATE`，不得猜测路径。

## 7. 幂等与并发

### 7.1 写请求格式

每个写请求必须包含：

- `Idempotency-Key`：由客户端为一次用户意图生成 UUID。
- `expectedVersion`：客户端最后读取到的会话版本；创建会话除外。
- 经过 Schema 校验的请求体。

### 7.2 幂等行为

- 相同学生、端点和幂等键，且请求摘要相同：返回第一次已提交的响应。
- 相同键但请求摘要不同：返回 `409 IDEMPOTENCY_KEY_REUSED`。
- 创建会话时若该学生与作业已有会话：返回既有会话快照；只有命中相同幂等键时才视为同一次请求重放。
- 幂等记录和业务写入必须在同一事务中提交。
- AI 任务以业务实体、任务类型和输入版本组成逻辑唯一键，重复请求不得产生两个有效任务。

### 7.3 版本冲突

- `expectedVersion` 不等于数据库当前版本时返回 `409 SESSION_VERSION_CONFLICT` 和最新快照。
- 前端必须展示状态已经变化，并以最新快照恢复；不得静默覆盖或自动重复非幂等操作。
- 数据库使用条件更新或 SQLAlchemy 版本列保证原子性，不能只在应用内先读后写。

## 8. AI 任务规则

1. 学生答案和任务记录在短事务中持久化，模型调用发生在事务外。
2. Worker 通过原子认领取得限时租约；运行中定期续租。
3. 租约过期的任务可重新认领，但保存结果必须幂等。
4. 同一逻辑任务最多有一个当前有效结果。
5. 模型响应依次经过 Schema 校验、原文证据校验和安全校验。
6. 未通过校验的响应只记录为失败的 AI run，不写入分析或评价结果表。
7. 重试使用相同的输入版本；学生答案改变时必须创建新的逻辑任务。
8. 达到最大尝试次数、输入本身非法或安全规则拒绝时进入 `FAILED_FINAL`。

## 9. 截止、权限与删除

- 创建会话和提交学生答案前均重新检查学生、作业权限和服务端截止时间。
- 已提交的数据在截止后仍可读取。
- AI 任务可以在截止后完成，因为学生答案已在截止前提交。
- MVP 不提供学生删除会话或答案的动作。
- 身份不匹配时返回 `404`，避免泄露其他学生会话是否存在。

## 10. 领域错误

| HTTP | 错误码 | 含义 |
|---|---|---|
| 400 | `INVALID_ANSWER` | 内容为空、超长或不符合输入规则 |
| 401 | `AUTHENTICATION_REQUIRED` | 未登录或令牌无效 |
| 404 | `SESSION_NOT_FOUND` | 会话不存在或不属于当前学生 |
| 409 | `ACTION_NOT_ALLOWED` | 当前状态不允许该动作 |
| 409 | `SESSION_VERSION_CONFLICT` | 会话已被其他请求更新 |
| 409 | `IDEMPOTENCY_KEY_REUSED` | 同一键对应了不同请求 |
| 410 | `ASSIGNMENT_CLOSED` | 作业已截止或关闭 |
| 422 | `AI_OUTPUT_INVALID` | 模型输出无法形成合法结果；通常仅作为任务内部错误 |
| 503 | `AI_TEMPORARILY_UNAVAILABLE` | AI 暂时不可用且可以重试 |
| 500 | `INCONSISTENT_SESSION_STATE` | 持久化状态违反领域不变量 |

API 错误响应统一包含 `code`、适龄的 `message`、`requestId`，可恢复冲突可额外包含最新 `snapshot`。内部堆栈、模型原文和密钥不得返回前端。

## 11. 必须保持的不变量

- 一个学生和一项作业最多有一个作答会话。
- 一个会话最多有一个当前最终提交版本。
- `submissionStatus = SUBMITTED` 时 `currentSubmissionId` 必须存在。
- `phase = RESULT` 时必须存在当前最终提交版本和对应评价逻辑任务。
- 初析成功时必须存在通过校验的初析结果。
- 评价成功时必须存在与当前提交版本绑定的通过校验结果。
- 同一会话的辅导轮次号唯一，且只能位于 1 至 20。
- 一个辅导轮次最多保存一次学生回答。
- 第 20 次回答后不得创建第 21 个辅导任务。
- 辅导结束后的晚到 AI 结果不得重新激活会话。
- 任务成功状态和领域结果在同一事务中提交。
- 所有展示引用都能逐字定位到对应版本的学生原文。

这些不变量同时由领域测试、数据库唯一约束或事务逻辑保护。不能只依赖前端按钮是否可见。
