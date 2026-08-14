import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.sessions.models import AnswerSubmission, AiJob, AiRun, AnswerSession, CoachingSession, CoachingTurn, FinalEvaluation, IdempotencyRecord, InitialAnalysis
from app.ai.gateway import AiGateway
from app.ai.provider import MockAiProvider
from app.ai.initial_analysis import InvalidAnalysisOutput, validate_initial_analysis
from app.ai.final_evaluation import InvalidFinalEvaluationOutput, validate_final_evaluation
from app.ai.worker import AiWorker

pytestmark = pytest.mark.asyncio


async def test_live_health(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Request-ID"]


async def test_ready_health(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def login_grade_three(client: AsyncClient) -> str:
    response = await client.post(
        "/api/v1/demo/login",
        json={"student_id": "student-grade-3"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def test_demo_login_and_grade_filtered_assignments(client: AsyncClient) -> None:
    students_response = await client.get("/api/v1/demo/students")
    assert students_response.status_code == 200
    students = students_response.json()
    assert [student["grade"] for student in students] == [3, 4]

    login_response = await client.post(
        "/api/v1/demo/login",
        json={"student_id": students[0]["id"]},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    assignments_response = await client.get(
        "/api/v1/assignments",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert assignments_response.status_code == 200
    assignments = assignments_response.json()
    assert len(assignments) == 1
    assert assignments[0]["id"] == "assignment-grade-3"
    assert assignments[0]["availability"] == "OPEN"
    assert assignments[0]["session"] is None


async def test_assignments_require_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/assignments")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTHENTICATION_REQUIRED"


async def test_assignment_detail_is_grade_scoped(client: AsyncClient) -> None:
    token = await login_grade_three(client)
    headers = {"Authorization": f"Bearer {token}"}

    detail = await client.get("/api/v1/assignments/assignment-grade-3", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["title"] == "校园里的安静角落"

    forbidden = await client.get("/api/v1/assignments/assignment-grade-4", headers=headers)
    assert forbidden.status_code == 404
    assert forbidden.json()["detail"]["code"] == "ASSIGNMENT_NOT_FOUND"


async def test_create_session_is_idempotent(client: AsyncClient, session_factory: sessionmaker[Session]) -> None:
    token = await login_grade_three(client)
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": "a0832458-27f2-454b-9f97-f0b3a8090f48",
    }
    body = {"assignment_id": "assignment-grade-3"}

    first = await client.post("/api/v1/sessions", headers=headers, json=body)
    second = await client.post("/api/v1/sessions", headers=headers, json=body)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()
    assert first.json()["allowed_actions"] == ["SUBMIT_INITIAL_ANSWER"]
    assert first.json()["next_view"] == "INITIAL_DRAFT"

    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AnswerSession)) == 1
        assert db.scalar(select(func.count()).select_from(IdempotencyRecord)) == 1


async def test_submit_initial_answer_queues_traceable_ai_work(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    token = await login_grade_three(client)
    auth = {"Authorization": f"Bearer {token}"}
    create_headers = {**auth, "Idempotency-Key": "b64b931e-ec31-41f2-a93d-746d3cf5fa70"}
    created = await client.post(
        "/api/v1/sessions",
        headers=create_headers,
        json={"assignment_id": "assignment-grade-3"},
    )
    snapshot = created.json()
    answer = "我认为学校应该设置安静角落，因为有些同学在课间需要一个不被打扰的地方阅读。"
    submit_headers = {
        **auth,
        "Idempotency-Key": "17d4f20c-3591-42ca-bbd8-b21f0bacac5b",
        "X-Request-ID": "request-for-debugging",
    }
    body = {"answer": answer, "expected_version": snapshot["version"]}

    first = await client.post(
        f"/api/v1/sessions/{snapshot['id']}/initial-answer",
        headers=submit_headers,
        json=body,
    )
    replay = await client.post(
        f"/api/v1/sessions/{snapshot['id']}/initial-answer",
        headers=submit_headers,
        json=body,
    )
    assert first.status_code == 200
    assert replay.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["phase"] == "INITIAL_ANALYSIS"
    assert first.json()["jobs"]["initial_analysis"]["status"] == "QUEUED"
    assert first.json()["allowed_actions"] == []

    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AiJob)) == 1
        assert db.scalar(select(func.count()).select_from(AiRun)) == 1
        run = db.scalar(select(AiRun))
        assert run is not None
        assert run.request_id == "request-for-debugging"
        assert run.operation == "INITIAL_ANALYSIS"
        assert run.provider == "mock"
        assert run.prompt_version == "initial-analysis-v2"
        assert answer not in (run.input_summary or "")


async def test_stale_session_version_returns_latest_snapshot(client: AsyncClient) -> None:
    token = await login_grade_three(client)
    auth = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/sessions",
        headers={**auth, "Idempotency-Key": "6598d684-ddb2-4620-a6d2-74a8dbcf19ef"},
        json={"assignment_id": "assignment-grade-3"},
    )
    session_id = created.json()["id"]
    submitted = await client.post(
        f"/api/v1/sessions/{session_id}/initial-answer",
        headers={**auth, "Idempotency-Key": "acbeb23f-246d-4449-8a80-90b2b381329b"},
        json={"answer": "这是第一次提交的有效观点和理由。", "expected_version": 1},
    )
    assert submitted.status_code == 200

    stale = await client.post(
        f"/api/v1/sessions/{session_id}/initial-answer",
        headers={**auth, "Idempotency-Key": "e861b942-c8e9-4651-aee4-c1dfbed60f41"},
        json={"answer": "另一个标签页中的内容。", "expected_version": 1},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "SESSION_VERSION_CONFLICT"
    assert stale.json()["detail"]["snapshot"]["version"] == 2


async def test_ai_gateway_records_debug_metadata_without_payload_text() -> None:
    gateway = AiGateway(MockAiProvider())
    run = AiRun(
        id="run-1",
        job_id="job-1",
        provider="mock",
        model="deterministic-v1",
        operation="INITIAL_ANALYSIS",
        status="QUEUED",
    )
    payload = {"answer": "这段学生正文不应出现在摘要里", "sessionId": "session-1"}

    output = gateway.execute(run, payload)

    assert output["mock"] is True
    assert run.status == "SUCCEEDED"
    assert run.duration_ms is not None
    assert run.finished_at is not None
    assert "学生正文" not in (run.output_summary or "")


async def test_initial_analysis_rejects_non_exact_quote() -> None:
    raw = MockAiProvider().invoke("INITIAL_ANALYSIS", {"answer": "我支持这个建议，因为它能帮助同学。"})
    raw["elements"][0]["quotes"] = ["学生没有写过的话"]
    with pytest.raises(InvalidAnalysisOutput):
        validate_initial_analysis(raw, "我支持这个建议，因为它能帮助同学。")


async def test_worker_persists_valid_result_and_snapshot_routes_to_result(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    token = await login_grade_three(client)
    auth = {"Authorization": f"Bearer {token}"}
    created = await client.post("/api/v1/sessions", headers={**auth, "Idempotency-Key": "0e543568-d171-40e0-848c-ef256722ab42"}, json={"assignment_id": "assignment-grade-3"})
    session_id = created.json()["id"]
    await client.post(
        f"/api/v1/sessions/{session_id}/initial-answer",
        headers={**auth, "Idempotency-Key": "4a708113-d768-4f43-9c44-c3be4a7c5ad1"},
        json={"answer": "我认为学校应该设置安静角落，因为阅读需要安静的环境。", "expected_version": 1},
    )
    worker = AiWorker(session_factory, AiGateway(MockAiProvider()), "test-worker", max_attempts=3)
    assert worker.process_next() is True
    assert worker.process_next() is False

    snapshot = await client.get(f"/api/v1/sessions/{session_id}", headers=auth)
    assert snapshot.json()["next_view"] == "INITIAL_ANALYSIS"
    assert snapshot.json()["jobs"]["initial_analysis"]["status"] == "SUCCEEDED"
    result = await client.get(f"/api/v1/sessions/{session_id}/initial-analysis", headers=auth)
    assert result.status_code == 200
    assert result.json()["analysis"]["schema_version"] == "initial-analysis-v2"
    assert result.json()["analysis"]["opening_question"]["question"]
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(InitialAnalysis)) == 1


async def test_text_coaching_streams_questions_and_can_end_early(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    token = await login_grade_three(client)
    auth = {"Authorization": f"Bearer {token}"}
    created = await client.post(
        "/api/v1/sessions", headers={**auth, "Idempotency-Key": str(uuid4())},
        json={"assignment_id": "assignment-grade-3"},
    )
    session_id = created.json()["id"]
    await client.post(
        f"/api/v1/sessions/{session_id}/initial-answer",
        headers={**auth, "Idempotency-Key": str(uuid4())},
        json={"answer": "我赞成设置安静角，因为阅读需要安静的环境。", "expected_version": 1},
    )
    worker = AiWorker(session_factory, AiGateway(MockAiProvider()), "coaching-worker")
    assert worker.process_next() is True
    ready = (await client.get(f"/api/v1/sessions/{session_id}", headers=auth)).json()
    started = await client.post(
        f"/api/v1/sessions/{session_id}/coaching/start",
        headers={**auth, "Idempotency-Key": str(uuid4())}, json={"expected_version": ready["version"]},
    )
    assert started.status_code == 200
    assert started.json()["next_view"] == "COACHING"
    record = (await client.get(f"/api/v1/sessions/{session_id}/coaching", headers=auth)).json()
    turn = record["turns"][0]
    stream = await client.get(f"/api/v1/sessions/{session_id}/coaching/turns/{turn['id']}/stream", headers=auth)
    assert stream.status_code == 200
    assert "event: delta" in stream.text
    assert "你能举" in stream.text

    answered = await client.post(
        f"/api/v1/sessions/{session_id}/coaching/turns/{turn['id']}/response",
        headers={**auth, "Idempotency-Key": str(uuid4())},
        json={"answer": "例如午休时，图书角附近的谈话声会让我读不进去。", "expected_version": started.json()["version"]},
    )
    assert answered.json()["next_view"] == "COACHING_PENDING"
    assert worker.process_next() is True
    next_snapshot = (await client.get(f"/api/v1/sessions/{session_id}", headers=auth)).json()
    assert next_snapshot["next_view"] == "COACHING"
    ended = await client.post(
        f"/api/v1/sessions/{session_id}/coaching/end",
        headers={**auth, "Idempotency-Key": str(uuid4())},
        json={"expected_version": next_snapshot["version"]},
    )
    assert ended.json()["next_view"] == "FINAL_DRAFT"
    assert ended.json()["coaching"]["status"] == "ENDED_BY_STUDENT"


async def test_coaching_stops_after_twentieth_answer(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    token = await login_grade_three(client)
    auth = {"Authorization": f"Bearer {token}"}
    created = await client.post("/api/v1/sessions", headers={**auth, "Idempotency-Key": str(uuid4())}, json={"assignment_id": "assignment-grade-3"})
    session_id = created.json()["id"]
    await client.post(
        f"/api/v1/sessions/{session_id}/initial-answer", headers={**auth, "Idempotency-Key": str(uuid4())},
        json={"answer": "我认为学校需要安静角，因为同学们需要不同的课间活动空间。", "expected_version": 1},
    )
    worker = AiWorker(session_factory, AiGateway(MockAiProvider()), "limit-worker")
    assert worker.process_next() is True
    snapshot = (await client.get(f"/api/v1/sessions/{session_id}", headers=auth)).json()
    snapshot = (await client.post(
        f"/api/v1/sessions/{session_id}/coaching/start", headers={**auth, "Idempotency-Key": str(uuid4())},
        json={"expected_version": snapshot["version"]},
    )).json()
    for round_number in range(1, 21):
        record = (await client.get(f"/api/v1/sessions/{session_id}/coaching", headers=auth)).json()
        current = record["turns"][-1]
        response = await client.post(
            f"/api/v1/sessions/{session_id}/coaching/turns/{current['id']}/response",
            headers={**auth, "Idempotency-Key": str(uuid4())},
            json={"answer": f"这是我对第 {round_number} 个问题的独立回答。", "expected_version": snapshot["version"]},
        )
        assert response.status_code == 200
        snapshot = response.json()
        if round_number < 20:
            assert snapshot["next_view"] == "COACHING_PENDING"
            assert worker.process_next() is True
            snapshot = (await client.get(f"/api/v1/sessions/{session_id}", headers=auth)).json()
        else:
            assert snapshot["next_view"] == "FINAL_DRAFT"
            assert snapshot["coaching"]["status"] == "ENDED_BY_LIMIT"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CoachingTurn)) == 20
        assert db.scalar(select(func.count()).select_from(AiJob).where(AiJob.job_type == "COACHING_QUESTION")) == 19


class InvalidQuoteProvider(MockAiProvider):
    def invoke(self, operation, payload):
        result = super().invoke(operation, payload)
        result["elements"][0]["quotes"] = ["伪造引用"]
        return result


async def test_invalid_output_becomes_retryable_then_final(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    token = await login_grade_three(client)
    auth = {"Authorization": f"Bearer {token}"}
    created = await client.post("/api/v1/sessions", headers={**auth, "Idempotency-Key": "12ee08cc-a75a-482d-b7ee-2bf00fb69de6"}, json={"assignment_id": "assignment-grade-3"})
    session_id = created.json()["id"]
    await client.post(f"/api/v1/sessions/{session_id}/initial-answer", headers={**auth, "Idempotency-Key": "a77dc7e4-363b-4811-bf8b-e7ea9ddb3b55"}, json={"answer": "我赞成，因为这样更方便。", "expected_version": 1})
    worker = AiWorker(session_factory, AiGateway(InvalidQuoteProvider()), "failure-worker", max_attempts=2)
    assert worker.process_next() is True
    first = await client.get(f"/api/v1/sessions/{session_id}", headers=auth)
    assert first.json()["allowed_actions"] == ["RETRY_INITIAL_ANALYSIS"]
    retry = await client.post(f"/api/v1/sessions/{session_id}/initial-analysis/retry", headers={**auth, "Idempotency-Key": "ae5b0d05-e629-4693-b4ae-861bd925301e"})
    assert retry.status_code == 200
    assert worker.process_next() is True
    final = await client.get(f"/api/v1/sessions/{session_id}", headers=auth)
    assert final.json()["jobs"]["initial_analysis"]["status"] == "FAILED_FINAL"
    assert final.json()["allowed_actions"] == []
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(InitialAnalysis)) == 0


async def test_expired_worker_lease_is_recovered(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    token = await login_grade_three(client)
    auth = {"Authorization": f"Bearer {token}"}
    created = await client.post("/api/v1/sessions", headers={**auth, "Idempotency-Key": "37a162a1-17b6-41a4-b521-4b29ac8aa13d"}, json={"assignment_id": "assignment-grade-3"})
    session_id = created.json()["id"]
    await client.post(f"/api/v1/sessions/{session_id}/initial-answer", headers={**auth, "Idempotency-Key": "99976e79-65a8-4b62-b962-bd57c468fc5d"}, json={"answer": "我支持设置安静角落，因为阅读时需要少一些打扰。", "expected_version": 1})
    with session_factory() as db:
        job = db.scalar(select(AiJob).where(AiJob.session_id == session_id))
        assert job is not None
        job.status = "RUNNING"
        job.attempts = 1
        job.lease_owner = "stopped-worker"
        job.lease_expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        queued = db.scalar(select(AiRun).where(AiRun.job_id == job.id))
        assert queued is not None
        queued.status = "RUNNING"
        db.commit()

    replacement = AiWorker(session_factory, AiGateway(MockAiProvider()), "replacement-worker", max_attempts=3)
    assert replacement.process_next() is True
    with session_factory() as db:
        job = db.scalar(select(AiJob).where(AiJob.session_id == session_id))
        assert job is not None
        assert job.status == "SUCCEEDED"
        assert job.attempts == 2
        assert db.scalar(select(func.count()).select_from(AiRun).where(AiRun.job_id == job.id)) == 2
        assert db.scalar(select(func.count()).select_from(InitialAnalysis).where(InitialAnalysis.job_id == job.id)) == 1


async def complete_initial_analysis(
    client: AsyncClient, session_factory: sessionmaker[Session], auth: dict[str, str], session_id: str
) -> dict:
    worker = AiWorker(session_factory, AiGateway(MockAiProvider()), "final-draft-test-worker")
    assert worker.process_next() is True
    response = await client.get(f"/api/v1/sessions/{session_id}", headers=auth)
    assert response.json()["allowed_actions"] == ["START_COACHING", "START_FINAL_DRAFT"]
    return response.json()


async def test_start_final_draft_requires_success_and_is_idempotent(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    token = await login_grade_three(client)
    auth = {"Authorization": f"Bearer {token}"}
    created = await client.post("/api/v1/sessions", headers={**auth, "Idempotency-Key": "13c6a334-ab45-4635-bdc0-d3662ce27146"}, json={"assignment_id": "assignment-grade-3"})
    session_id = created.json()["id"]
    submitted = await client.post(f"/api/v1/sessions/{session_id}/initial-answer", headers={**auth, "Idempotency-Key": "27a80f33-b735-4a47-a449-f057a5713948"}, json={"answer": "我赞成设置安静角，因为这里能让想阅读的同学少受打扰。", "expected_version": 1})
    blocked = await client.post(f"/api/v1/sessions/{session_id}/final-draft", headers={**auth, "Idempotency-Key": "99be9fe6-f8d7-40fd-b4af-7a896c466758"}, json={"expected_version": submitted.json()["version"]})
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "ACTION_NOT_ALLOWED"

    analysis = await complete_initial_analysis(client, session_factory, auth, session_id)
    headers = {**auth, "Idempotency-Key": "c8d50af4-03d9-4c25-87a8-bb5e9176c6ad"}
    first = await client.post(f"/api/v1/sessions/{session_id}/final-draft", headers=headers, json={"expected_version": analysis["version"]})
    replay = await client.post(f"/api/v1/sessions/{session_id}/final-draft", headers=headers, json={"expected_version": analysis["version"]})
    assert first.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["phase"] == "FINAL_DRAFT"
    assert first.json()["version"] == analysis["version"] + 1
    assert first.json()["allowed_actions"] == ["SUBMIT_FINAL_ANSWER"]


async def test_submit_final_answer_is_immutable_idempotent_and_versioned(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    token = await login_grade_three(client)
    auth = {"Authorization": f"Bearer {token}"}
    created = await client.post("/api/v1/sessions", headers={**auth, "Idempotency-Key": "838cf8ba-124b-4a72-908f-9b2c746ee714"}, json={"assignment_id": "assignment-grade-3"})
    session_id = created.json()["id"]
    await client.post(f"/api/v1/sessions/{session_id}/initial-answer", headers={**auth, "Idempotency-Key": "9b451370-d134-49c6-afc8-f3bba3baadd2"}, json={"answer": "我赞成设置安静角，因为这里能让想阅读的同学少受打扰。", "expected_version": 1})
    analysis = await complete_initial_analysis(client, session_factory, auth, session_id)
    started = await client.post(f"/api/v1/sessions/{session_id}/final-draft", headers={**auth, "Idempotency-Key": "20fdb808-1ce0-4b85-86ad-bf8fef73fe0a"}, json={"expected_version": analysis["version"]})
    final_text = "我赞成学校设置安静角。例如图书角在课间常有人阅读，减少谈话声能让他们更专心。"
    headers = {**auth, "Idempotency-Key": "b18552ac-f3e9-4a8a-b686-023363397896", "X-Request-ID": "final-submit-request"}
    first = await client.post(f"/api/v1/sessions/{session_id}/final-answer", headers=headers, json={"answer": final_text, "expected_version": started.json()["version"]})
    replay = await client.post(f"/api/v1/sessions/{session_id}/final-answer", headers=headers, json={"answer": final_text, "expected_version": started.json()["version"]})
    assert first.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["phase"] == "RESULT"
    assert first.json()["next_view"] == "FINAL_EVALUATION_PENDING"
    assert first.json()["submission_status"] == "SUBMITTED"
    assert first.json()["final_answer"] == final_text
    assert first.json()["jobs"]["final_evaluation"]["status"] == "QUEUED"

    stale = await client.post(f"/api/v1/sessions/{session_id}/final-answer", headers={**auth, "Idempotency-Key": "b6081af3-1a18-4bc0-8b19-1db035588b06"}, json={"answer": "旧标签页内容", "expected_version": started.json()["version"]})
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "SESSION_VERSION_CONFLICT"
    assert stale.json()["detail"]["snapshot"]["phase"] == "RESULT"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AnswerSubmission)) == 1
        assert db.scalar(select(func.count()).select_from(AiJob).where(AiJob.job_type == "FINAL_EVALUATION")) == 1
        run = db.scalar(select(AiRun).join(AiJob).where(AiJob.job_type == "FINAL_EVALUATION"))
        assert run is not None
        assert run.request_id == "final-submit-request"
        assert final_text not in (run.input_summary or "")


async def test_legacy_idempotency_snapshot_defaults_new_evaluation_job() -> None:
    from app.modules.sessions.schemas import SessionSnapshotOut

    legacy = {
        "id": "session-legacy", "assignment_id": "assignment-grade-3", "student_id": "student-grade-3",
        "version": 2, "phase": "INITIAL_ANALYSIS", "mode": "INITIAL", "submission_status": "DRAFT",
        "allowed_actions": [], "next_view": "INITIAL_ANALYSIS_PENDING",
        "jobs": {"initial_analysis": {"status": "QUEUED", "error_code": None}},
        "initial_answer": "旧响应中的初答", "deadline": None,
        "server_time": datetime.now(timezone.utc).isoformat(),
    }
    snapshot = SessionSnapshotOut.model_validate(legacy)
    assert snapshot.jobs.final_evaluation.status == "IDLE"
    assert snapshot.current_submission_id is None


async def create_submitted_final(
    client: AsyncClient, session_factory: sessionmaker[Session], auth: dict[str, str], suffix: str
) -> tuple[str, dict]:
    created = await client.post("/api/v1/sessions", headers={**auth, "Idempotency-Key": f"00000000-0000-4000-8000-{suffix}01"}, json={"assignment_id": "assignment-grade-3"})
    session_id = created.json()["id"]
    await client.post(f"/api/v1/sessions/{session_id}/initial-answer", headers={**auth, "Idempotency-Key": f"00000000-0000-4000-8000-{suffix}02"}, json={"answer": "我赞成设置安静角，因为阅读需要少一些打扰。", "expected_version": 1})
    analysis = await complete_initial_analysis(client, session_factory, auth, session_id)
    started = await client.post(f"/api/v1/sessions/{session_id}/final-draft", headers={**auth, "Idempotency-Key": f"00000000-0000-4000-8000-{suffix}03"}, json={"expected_version": analysis["version"]})
    final = await client.post(f"/api/v1/sessions/{session_id}/final-answer", headers={**auth, "Idempotency-Key": f"00000000-0000-4000-8000-{suffix}04"}, json={"answer": "我赞成学校设置安静角。例如图书角在课间常有人阅读，减少谈话声能让他们更专心。", "expected_version": started.json()["version"]})
    assert final.status_code == 200
    return session_id, final.json()


async def test_final_evaluation_worker_persists_versioned_result(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    token = await login_grade_three(client)
    auth = {"Authorization": f"Bearer {token}"}
    session_id, _ = await create_submitted_final(client, session_factory, auth, "0000000001")
    worker = AiWorker(session_factory, AiGateway(MockAiProvider()), "evaluation-worker")
    assert worker.process_next() is True
    snapshot = await client.get(f"/api/v1/sessions/{session_id}", headers=auth)
    assert snapshot.json()["jobs"]["final_evaluation"]["status"] == "SUCCEEDED"
    assert snapshot.json()["next_view"] == "RESULT"
    result = await client.get(f"/api/v1/sessions/{session_id}/final-evaluation", headers=auth)
    assert result.status_code == 200
    assert result.json()["evaluation"]["schema_version"] == "final-evaluation-v1"
    assert len(result.json()["evaluation"]["dimensions"]) == 5
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(FinalEvaluation)) == 1


class InvalidFinalEvaluationProvider(MockAiProvider):
    def invoke(self, operation, payload):
        result = super().invoke(operation, payload)
        if operation == "FINAL_EVALUATION":
            result["strengths"][0]["quotes"] = ["终稿中不存在的证据"]
        return result


async def test_final_evaluation_invalid_output_retries_same_submission_then_stops(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    token = await login_grade_three(client)
    auth = {"Authorization": f"Bearer {token}"}
    session_id, submitted = await create_submitted_final(client, session_factory, auth, "0000000002")
    worker = AiWorker(session_factory, AiGateway(InvalidFinalEvaluationProvider()), "invalid-evaluation-worker", max_attempts=2)
    assert worker.process_next() is True
    failed = await client.get(f"/api/v1/sessions/{session_id}", headers=auth)
    assert failed.json()["allowed_actions"] == ["RETRY_FINAL_EVALUATION"]
    retry_headers = {**auth, "Idempotency-Key": "00000000-0000-4000-8000-000000000205"}
    retry = await client.post(f"/api/v1/sessions/{session_id}/final-evaluation/retry", headers=retry_headers, json={"expected_version": submitted["version"]})
    replay = await client.post(f"/api/v1/sessions/{session_id}/final-evaluation/retry", headers=retry_headers, json={"expected_version": submitted["version"]})
    assert retry.status_code == 200
    assert retry.json() == replay.json()
    assert retry.json()["version"] == submitted["version"] + 1
    assert worker.process_next() is True
    final = await client.get(f"/api/v1/sessions/{session_id}", headers=auth)
    assert final.json()["jobs"]["final_evaluation"]["status"] == "FAILED_FINAL"
    with session_factory() as db:
        assert db.scalar(select(func.count()).select_from(AnswerSubmission)) == 1
        assert db.scalar(select(func.count()).select_from(FinalEvaluation)) == 0
        job = db.scalar(select(AiJob).where(AiJob.job_type == "FINAL_EVALUATION"))
        assert job is not None and job.attempts == 2
        assert db.scalar(select(func.count()).select_from(AiRun).where(AiRun.job_id == job.id)) == 2


async def test_final_evaluation_rejects_fabricated_comparison_quote() -> None:
    initial = "初答观点"
    final = "终稿观点和例子"
    raw = MockAiProvider().invoke("FINAL_EVALUATION", {"initialAnswer": initial, "finalAnswer": final})
    raw["revision_evidence"][0]["initial_quote"] = "伪造初答"
    with pytest.raises(InvalidFinalEvaluationOutput):
        validate_final_evaluation(raw, initial, final)


async def test_final_evaluation_requires_quotes_for_observed_dimensions() -> None:
    initial = "初答观点"
    final = "终稿观点和例子"
    raw = MockAiProvider().invoke("FINAL_EVALUATION", {"initialAnswer": initial, "finalAnswer": final})
    raw["dimensions"][1]["quotes"] = []
    with pytest.raises(InvalidFinalEvaluationOutput):
        validate_final_evaluation(raw, initial, final)

    raw["dimensions"][1]["status"] = "not_yet_visible"
    validate_final_evaluation(raw, initial, final)


async def test_retry_actions_remain_available_after_assignment_deadline() -> None:
    from app.modules.sessions.domain import allowed_actions

    now = datetime.now(timezone.utc)
    session = AnswerSession(
        id="closed-result", assignment_id="assignment-grade-3", student_id="student-grade-3",
        phase="RESULT", mode="INITIAL", submission_status="SUBMITTED", version=4,
    )
    assert allowed_actions(
        session, now - timedelta(seconds=1), now,
        initial_analysis_status="SUCCEEDED", final_evaluation_status="FAILED_RETRYABLE",
    ) == ["RETRY_FINAL_EVALUATION"]
