# AI 调用与调试约定

所有模型能力必须通过 `AiGateway` 调用。业务模块、API 路由和 worker 不得直接调用具体 Provider。

统一链路：

```text
业务动作
  -> 创建 ai_jobs
  -> AiGateway.record_queued() 创建 ai_runs
  -> worker 认领任务
  -> AiGateway.execute() 调用 Provider
  -> Schema / 证据 / 安全校验
  -> 保存领域结果并完成任务
```

## 调试字段

每次运行至少记录：

- `request_id`：触发业务动作的 HTTP 请求。
- `job_id`：可恢复的业务任务。
- `ai_run.id`：一次具体模型尝试。
- `operation`：稳定的能力名称，例如 `INITIAL_ANALYSIS`。
- `provider`、`model`。
- `prompt_version`、`schema_version`。
- `status`、`duration_ms`、`error_code`。
- `input_summary`、`output_summary`：只保存摘要、字段名和哈希，不保存正文。

定位一次初析任务：

```sql
SELECT
  j.id AS job_id,
  j.status AS job_status,
  j.attempts,
  r.id AS run_id,
  r.request_id,
  r.provider,
  r.model,
  r.operation,
  r.prompt_version,
  r.schema_version,
  r.status AS run_status,
  r.duration_ms,
  r.error_code
FROM ai_jobs j
JOIN ai_runs r ON r.job_id = j.id
WHERE j.session_id = :session_id
ORDER BY r.started_at;
```

## 约束

- 常规日志不输出学生完整答案、模型完整响应、Token 或密钥。
- Provider 异常统一映射为稳定错误码，原始堆栈只留在受控服务端日志。
- Gateway 只负责调用与运行元数据，不负责会话阶段迁移。
- 模型 JSON 必须通过版本化 Schema 和业务校验后才能成为领域结果。
- 重试创建新的 `ai_runs`，但复用同一个逻辑 `ai_jobs`。
- 常规 CI 只使用确定性的 Mock Provider。
- Worker 是独立进程，通过 `python -m app.scripts.run_ai_worker` 启动；不要在每个 Web worker 内重复启动后台循环。
- 模型调用发生在数据库事务之外；认领时写入租约，进程退出后由其他 Worker 在租约过期后接管。
- `FAILED_RETRYABLE` 只允许用户显式重试；达到最大尝试次数后进入 `FAILED_FINAL`。
