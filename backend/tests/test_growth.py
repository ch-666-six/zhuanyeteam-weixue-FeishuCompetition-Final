import json
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session, sessionmaker

from app.modules.assignments.models import Assignment
from app.modules.sessions.models import AiJob, AnswerSession, AnswerSubmission, FinalEvaluation, InitialAnalysis


pytestmark = pytest.mark.asyncio


async def _auth(client: AsyncClient, student_id: str = "student-grade-3") -> dict[str, str]:
    response = await client.post("/api/v1/demo/login", json={"student_id": student_id})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _evaluation(answer: str, index: int) -> dict:
    dimensions = []
    statuses = ["developing", "clear", "clear"]
    for dimension in ["idea", "material", "structure", "language", "perspective"]:
        not_yet_visible = dimension == "perspective"
        dimensions.append(
            {
                "dimension": dimension,
                "status": "not_yet_visible" if not_yet_visible else statuses[index],
                "observation": f"第 {index + 1} 次作业中的观察。",
                "quotes": [] if not_yet_visible else [answer],
            }
        )
    return {
        "schema_version": "final-evaluation-v1",
        "rubric_version": "argument-writing-v1",
        "summary": "这是一份可追溯的成长记录。",
        "strengths": [{"title": "观点清楚", "explanation": "能够表达自己的想法。", "quotes": [answer]}],
        "next_step": {"dimension": "perspective", "suggestion": "继续考虑不同观点。"},
        "dimensions": dimensions,
        "revision_evidence": [],
    }


def _seed_completed_assignments(session_factory: sessionmaker[Session]) -> None:
    submitted_at = datetime(2026, 2, 1, tzinfo=timezone.utc)
    with session_factory() as db, db.begin():
        for index in range(3):
            assignment_id = f"growth-assignment-{index}"
            session_id = f"growth-session-{index}"
            submission_id = f"growth-submission-{index}"
            job_id = f"growth-job-{index}"
            answer = f"这是第 {index + 1} 份作业中可以定位的学生原话。"
            db.add(
                Assignment(
                    id=assignment_id,
                    title=f"成长作业 {index + 1}",
                    prompt="请说明观点。",
                    grade=2 if index == 0 else 3,
                    published_at=submitted_at - timedelta(days=1),
                    deadline=None,
                )
            )
            db.add(
                AnswerSession(
                    id=session_id,
                    assignment_id=assignment_id,
                    student_id="student-grade-3",
                    version=4,
                    phase="RESULT",
                    mode="INITIAL",
                    submission_status="SUBMITTED",
                    initial_answer=answer,
                )
            )
            db.flush()
            db.add(
                AnswerSubmission(
                    id=submission_id,
                    session_id=session_id,
                    submission_version=1,
                    answer_text=answer,
                    source_session_version=3,
                    submitted_at=submitted_at + timedelta(days=index),
                )
            )
            db.add(
                AiJob(
                    id=job_id,
                    session_id=session_id,
                    job_type="FINAL_EVALUATION",
                    status="SUCCEEDED",
                    input_version=4,
                    attempts=1,
                )
            )
            initial_job_id = f"growth-initial-job-{index}"
            db.add(
                AiJob(
                    id=initial_job_id,
                    session_id=session_id,
                    job_type="INITIAL_ANALYSIS",
                    status="SUCCEEDED",
                    input_version=2,
                    attempts=1,
                )
            )
            db.flush()
            elements = [
                {"element": element, "status": "present", "summary": "已出现。", "quotes": [answer]}
                for element in ["viewpoint", "reasons", "evidence", "counterpoint", "response", "conditions"]
            ]
            db.add(
                InitialAnalysis(
                    id=f"growth-analysis-{index}",
                    session_id=session_id,
                    job_id=initial_job_id,
                    input_version=2,
                    schema_version="initial-analysis-v1",
                    result_json=json.dumps({"schema_version": "initial-analysis-v1", "elements": elements, "priority_improvement": None}, ensure_ascii=False),
                )
            )
            db.add(
                FinalEvaluation(
                    id=f"growth-evaluation-{index}",
                    session_id=session_id,
                    submission_id=submission_id,
                    job_id=job_id,
                    schema_version="final-evaluation-v1",
                    rubric_version="argument-writing-v1",
                    result_json=json.dumps(_evaluation(answer, index), ensure_ascii=False),
                )
            )
            db.get(AnswerSession, session_id).current_submission_id = submission_id


async def test_growth_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/growth")
    assert response.status_code == 401


async def test_growth_empty_state(client: AsyncClient) -> None:
    response = await client.get("/api/v1/growth", headers=await _auth(client))
    assert response.status_code == 200
    report = response.json()
    assert report["coverage"]["completed_assignments"] == 0
    assert report["timeline"] == []
    assert len(report["thinking_moves"]) == 6
    assert all(item["stable_level"] is None for item in report["dimensions"])


async def test_growth_aggregates_evidence_and_filters_grade(
    client: AsyncClient, session_factory: sessionmaker[Session]
) -> None:
    _seed_completed_assignments(session_factory)
    headers = await _auth(client)

    response = await client.get("/api/v1/growth", headers=headers)
    assert response.status_code == 200
    report = response.json()
    assert report["coverage"] == {
        "completed_assignments": 3,
        "trend_eligible_assignments": 3,
        "available_grades": [2, 3],
    }
    assert len(report["dimensions"]) == 5
    assert report["dimensions"][0]["name"] == "思辨态度"
    assert report["dimensions"][0]["stable_level"] == "暂未体现"
    assert report["dimensions"][0]["evidence_count"] == 0
    assert report["dimensions"][1]["stable_level"] == "表达清楚"
    assert report["dimensions"][1]["evidence_count"] == 3
    assert report["timeline"][0]["assignment_title"] == "成长作业 3"
    assert report["timeline"][0]["status"] == "INCLUDED"
    assert [item["name"] for item in report["thinking_moves"]] == [
        "说出看法", "说出为什么", "用材料支撑", "看见别的想法", "回应不同想法", "说清条件"
    ]
    assert all(item["count"] == 3 for item in report["thinking_moves"])
    assert report["thinking_moves"][0]["evidence"][0]["assignment_title"] == "成长作业 3"
    assert report["teacher_confirmation"]["available"] is False

    filtered = await client.get("/api/v1/growth?grade=2", headers=headers)
    assert filtered.status_code == 200
    filtered_report = filtered.json()
    assert filtered_report["selected_grade"] == 2
    assert filtered_report["coverage"]["completed_assignments"] == 1
    assert filtered_report["coverage"]["available_grades"] == [2, 3]
    assert filtered_report["dimensions"][0]["stable_level"] is None


async def test_growth_rejects_unknown_grade(client: AsyncClient) -> None:
    response = await client.get("/api/v1/growth?grade=9", headers=await _auth(client))
    assert response.status_code == 422
