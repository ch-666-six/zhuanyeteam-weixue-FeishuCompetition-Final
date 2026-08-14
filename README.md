# 思辨表达 AI 助教

这是按照 `product-scope.md`、`session-state.md` 和 `architecture-decisions.md` 重新建立的项目。当前已完成工程骨架、演示身份、作业列表与详情、创建会话、文字初答、可恢复的 AI 初步分析、不可变终稿、五维辅助评价，以及跨作业思考成长报告。

## 使用 Codex 一键启动（新手推荐）

在 Codex 中打开本项目根目录，将下面整段文字作为**一条指令**发送给 Codex。Codex 会完成本地开发环境初始化，并在最后给出可以直接打开的前端网址：

```text
请在当前项目根目录实际启动本项目，不要只告诉我启动步骤。请先阅读 README.md 和项目配置，然后依次检查并完成以下工作：保留已有的 .env；如果没有 .env，就从 .env.example 复制一份用于本地开发；检查 Python 3.9+、Node.js 20+ 和 Docker 是否可用；通过 Docker Compose 启动 PostgreSQL；在 backend 目录创建或复用 .venv，安装后端开发依赖，执行数据库迁移并写入演示数据；以后台进程分别启动 FastAPI（127.0.0.1:8000）和 AI Worker；在 frontend 目录安装依赖并以后台进程启动 Vite。默认使用项目内置的 Mock AI，不需要任何模型 API Key。启动后请实际检查后端 /health/live、/health/ready 和前端页面是否可访问；保持所有服务继续运行，并在最终回复中明确给出可点击的本地前端网址（通常是 http://127.0.0.1:5173）、已启动的服务和停止方法。如果默认端口被本项目之前遗留的进程占用，请只终止属于本项目的旧进程后重试；如果缺少系统级软件或需要权限，请直接向我说明并请求授权。
```

看到 Codex 回复健康检查通过后，直接点击它给出的前端网址即可体验和调试完整功能。首次启动需要下载依赖和 PostgreSQL 镜像，耗时会比后续启动更长。

## 环境要求

- Python 3.9+
- Node.js 20+
- PostgreSQL 16（推荐通过 Docker Compose 启动）

## 首次启动

复制 `.env.example` 为 `.env`，并替换 `APP_SECRET_KEY`。

```powershell
docker compose up -d postgres

cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
alembic upgrade head
python -m app.scripts.seed_demo
uvicorn app.main:app --reload --port 8000
```

再开一个后端终端运行持久化 Worker：

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python -m app.scripts.run_ai_worker
```

另开一个终端：

```powershell
cd frontend
npm install
npm run dev
```

访问 <http://localhost:5173>。开发服务器会将 `/api` 代理到 <http://localhost:8000>。

当前机器没有 Docker 时，可以安装本地 PostgreSQL，并令 `DATABASE_URL` 指向该实例。SQLite 只用于快速测试，不作为共享或生产环境数据库。

## 验证命令

```powershell
cd backend
python -m pytest -q

cd ..\frontend
npm test -- --run
npm run build
npx playwright test
```

常规测试使用 Mock AI，不访问真实模型服务。

本地默认使用确定性 Mock。接入 DeepSeek 时，将 `AI_PROVIDER` 改为 `deepseek`，并仅在后端进程环境配置 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL` 和 `DEEPSEEK_MODEL`。密钥不得使用 `VITE_` 前缀，也不得提交进仓库。

## 当前 API

- `GET /health/live`：进程存活检查。
- `GET /health/ready`：数据库就绪检查。
- `GET /api/v1/demo/students`：演示学生列表。
- `POST /api/v1/demo/login`：签发演示访问令牌。
- `GET /api/v1/assignments`：读取当前学生所属年级的作业列表和会话摘要。
- `GET /api/v1/assignments/{id}`：读取所属年级的作业详情。
- `POST /api/v1/sessions`：幂等创建或返回作答会话。
- `GET /api/v1/sessions/{id}`：读取服务端会话快照。
- `POST /api/v1/sessions/{id}/initial-answer`：按预期版本提交文字初答并创建初析任务。
- `GET /api/v1/sessions/{id}/initial-analysis`：读取通过协议与原文证据校验的初析结果。
- `POST /api/v1/sessions/{id}/initial-analysis/retry`：幂等重试可恢复失败的初析任务。
- `POST /api/v1/sessions/{id}/final-draft`：按预期版本进入修改稿阶段。
- `POST /api/v1/sessions/{id}/final-answer`：按预期版本提交不可变终稿并创建评价任务。
- `GET /api/v1/sessions/{id}/final-evaluation`：读取绑定当前终稿版本的已验证评价。
- `POST /api/v1/sessions/{id}/final-evaluation/retry`：幂等重试同一终稿的可恢复评价任务。
- `GET /api/v1/growth`：读取当前学生的五维趋势、思考动作证据和逐作业学习轨迹，支持 `grade=all|1..7` 筛选。

初析与最终评价由同一个可恢复 Worker 管线处理。

所有写请求使用 `Idempotency-Key`，会话写入同时提交 `expected_version`。AI 调用和调试约定见 [backend/app/ai/README.md](backend/app/ai/README.md)。
