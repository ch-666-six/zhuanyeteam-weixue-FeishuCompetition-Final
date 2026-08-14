from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.gateway import AiGateway, AiRequestContext
from app.modules.assignments.models import Assignment
from app.modules.identity.models import Student
from app.modules.sessions.domain import allowed_actions, as_utc, is_closed, next_view
from app.modules.sessions.models import AnswerSubmission, AiJob, AiRun, AnswerSession, CoachingSession, CoachingTurn, FinalEvaluation, IdempotencyRecord, InitialAnalysis
from app.modules.sessions.schemas import CoachingOut, CoachingSummaryOut, CoachingTurnOut, FinalEvaluationOut, InitialAnalysisOut, SessionJobOut, SessionJobsOut, SessionSnapshotOut
from app.ai.initial_analysis import InitialAnalysisV1, InitialAnalysisV2
from app.ai.final_evaluation import FinalEvaluationV1


def domain_error(http_status: int, code: str, message: str, snapshot: Optional[SessionSnapshotOut] = None) -> HTTPException:
    detail = {"code": code, "message": message}
    if snapshot is not None:
        detail["snapshot"] = snapshot.model_dump(mode="json")
    return HTTPException(status_code=http_status, detail=detail)


def validate_idempotency_key(value: Optional[str]) -> str:
    if not value:
        raise domain_error(status.HTTP_400_BAD_REQUEST, "IDEMPOTENCY_KEY_REQUIRED", "请刷新页面后再试一次。")
    try:
        UUID(value)
    except ValueError as exc:
        raise domain_error(status.HTTP_400_BAD_REQUEST, "INVALID_IDEMPOTENCY_KEY", "请求标识无效，请刷新页面后再试一次。") from exc
    return value


def request_hash(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def get_assignment_for_student(db: Session, assignment_id: str, student: Student) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    now = datetime.now(timezone.utc)
    if (
        assignment is None
        or assignment.grade != student.grade
        or assignment.published_at is None
        or as_utc(assignment.published_at) > now
    ):
        raise domain_error(status.HTTP_404_NOT_FOUND, "ASSIGNMENT_NOT_FOUND", "没有找到这项作业。")
    return assignment


def latest_initial_analysis_job(db: Session, session_id: str) -> Optional[AiJob]:
    return db.scalar(
        select(AiJob)
        .where(AiJob.session_id == session_id, AiJob.job_type == "INITIAL_ANALYSIS")
        .order_by(AiJob.created_at.desc())
        .limit(1)
    )


def latest_job(db: Session, session_id: str, job_type: str) -> Optional[AiJob]:
    return db.scalar(
        select(AiJob)
        .where(AiJob.session_id == session_id, AiJob.job_type == job_type)
        .order_by(AiJob.created_at.desc())
        .limit(1)
    )


def session_snapshot(db: Session, session: AnswerSession, assignment: Assignment) -> SessionSnapshotOut:
    now = datetime.now(timezone.utc)
    job = latest_initial_analysis_job(db, session.id)
    evaluation_job = latest_job(db, session.id, "FINAL_EVALUATION")
    coaching = db.scalar(select(CoachingSession).where(CoachingSession.session_id == session.id))
    current_turn = db.scalar(
        select(CoachingTurn).where(CoachingTurn.session_id == session.id).order_by(CoachingTurn.round_number.desc()).limit(1)
    )
    coaching_job = db.get(AiJob, current_turn.question_job_id) if current_turn and current_turn.question_job_id else None
    coaching_question_status = (
        "SUCCEEDED" if current_turn and current_turn.status in ("READY", "ANSWERED")
        else coaching_job.status if coaching_job else None
    )
    completed_rounds = db.scalar(
        select(func.count()).select_from(CoachingTurn).where(
            CoachingTurn.session_id == session.id, CoachingTurn.student_response.is_not(None)
        )
    ) or 0
    submission = db.get(AnswerSubmission, session.current_submission_id) if session.current_submission_id else None
    return SessionSnapshotOut(
        id=session.id,
        assignment_id=session.assignment_id,
        student_id=session.student_id,
        version=session.version,
        phase=session.phase,
        mode=session.mode,
        submission_status=session.submission_status,
        allowed_actions=allowed_actions(
            session, assignment.deadline, now, job.status if job else None,
            evaluation_job.status if evaluation_job else None, coaching_question_status,
            bool(current_turn and current_turn.student_response),
        ),
        next_view=next_view(
            session, job.status if job else None, evaluation_job.status if evaluation_job else None,
            coaching_question_status,
        ),
        jobs=SessionJobsOut(
            initial_analysis=SessionJobOut(
                status=job.status if job else "IDLE",
                error_code=job.error_code if job else None,
            ),
            final_evaluation=SessionJobOut(
                status=evaluation_job.status if evaluation_job else "IDLE",
                error_code=evaluation_job.error_code if evaluation_job else None,
            ),
            coaching_question=SessionJobOut(
                status=coaching_question_status or "IDLE",
                error_code=coaching_job.error_code if coaching_job else None,
            ),
        ),
        coaching=CoachingSummaryOut(
            status=coaching.status if coaching else "NOT_STARTED",
            current_round=coaching.current_round if coaching else 0,
            completed_rounds=completed_rounds,
            max_rounds=coaching.max_rounds if coaching else 20,
            current_turn_id=current_turn.id if current_turn else None,
        ),
        initial_answer=session.initial_answer,
        current_submission_id=session.current_submission_id,
        final_answer=submission.answer_text if submission else None,
        deadline=as_utc(assignment.deadline),
        server_time=now,
    )


def find_session(db: Session, assignment_id: str, student_id: str) -> Optional[AnswerSession]:
    return db.scalar(
        select(AnswerSession).where(
            AnswerSession.assignment_id == assignment_id,
            AnswerSession.student_id == student_id,
        )
    )


def idempotent_response(
    db: Session, student_id: str, endpoint: str, key: str, payload_hash: str
) -> Optional[SessionSnapshotOut]:
    record = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.student_id == student_id,
            IdempotencyRecord.endpoint == endpoint,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    if record is None:
        return None
    if record.request_hash != payload_hash:
        raise domain_error(status.HTTP_409_CONFLICT, "IDEMPOTENCY_KEY_REUSED", "这次请求与之前不一致，请刷新页面后重试。")
    return SessionSnapshotOut.model_validate_json(record.response_json)


def save_idempotency(
    db: Session,
    student_id: str,
    endpoint: str,
    key: str,
    payload_hash: str,
    snapshot: SessionSnapshotOut,
) -> None:
    db.add(
        IdempotencyRecord(
            id=str(uuid4()),
            student_id=student_id,
            endpoint=endpoint,
            idempotency_key=key,
            request_hash=payload_hash,
            response_json=snapshot.model_dump_json(),
        )
    )


def create_answer_session(
    db: Session, assignment_id: str, student: Student, idempotency_key: str
) -> SessionSnapshotOut:
    key = validate_idempotency_key(idempotency_key)
    endpoint = "POST:/sessions"
    payload_hash = request_hash({"assignmentId": assignment_id})
    replay = idempotent_response(db, student.id, endpoint, key, payload_hash)
    if replay is not None:
        return replay

    assignment = get_assignment_for_student(db, assignment_id, student)
    if is_closed(assignment.deadline, datetime.now(timezone.utc)):
        raise domain_error(status.HTTP_410_GONE, "ASSIGNMENT_CLOSED", "这项作业已经截止。")

    session = find_session(db, assignment_id, student.id)
    if session is None:
        session = AnswerSession(
            id=str(uuid4()),
            assignment_id=assignment_id,
            student_id=student.id,
            version=1,
            phase="INITIAL_DRAFT",
            mode="INITIAL",
            submission_status="DRAFT",
        )
        db.add(session)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            session = find_session(db, assignment_id, student.id)
            if session is None:
                raise

    snapshot = session_snapshot(db, session, assignment)
    save_idempotency(db, student.id, endpoint, key, payload_hash, snapshot)
    db.commit()
    return snapshot


def start_final_draft(
    db: Session,
    session_id: str,
    student: Student,
    expected_version: int,
    idempotency_key: str,
) -> SessionSnapshotOut:
    key = validate_idempotency_key(idempotency_key)
    endpoint = f"POST:/sessions/{session_id}/final-draft"
    payload_hash = request_hash({"expectedVersion": expected_version})
    replay = idempotent_response(db, student.id, endpoint, key, payload_hash)
    if replay is not None:
        return replay
    session, assignment = get_session_by_id(db, session_id, student)
    current = session_snapshot(db, session, assignment)
    if is_closed(assignment.deadline, datetime.now(timezone.utc)):
        raise domain_error(status.HTTP_410_GONE, "ASSIGNMENT_CLOSED", "这项作业已经截止。")
    if expected_version != session.version:
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", current)
    if "START_FINAL_DRAFT" not in current.allowed_actions:
        raise domain_error(status.HTTP_409_CONFLICT, "ACTION_NOT_ALLOWED", "当前步骤不能进入修改。", current)
    now = datetime.now(timezone.utc)
    if db.scalar(select(CoachingSession).where(CoachingSession.session_id == session.id)) is None:
        db.add(CoachingSession(
            id=str(uuid4()), session_id=session.id, status="SKIPPED", current_round=0,
            max_rounds=20, ended_at=now,
        ))
    changed = db.execute(
        update(AnswerSession)
        .where(AnswerSession.id == session.id, AnswerSession.version == expected_version)
        .values(phase="FINAL_DRAFT", version=expected_version + 1, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        latest, latest_assignment = get_session_by_id(db, session_id, student)
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", session_snapshot(db, latest, latest_assignment))
    db.expire(session)
    snapshot = session_snapshot(db, session, assignment)
    save_idempotency(db, student.id, endpoint, key, payload_hash, snapshot)
    db.commit()
    return snapshot


def get_coaching(db: Session, session_id: str, student: Student) -> CoachingOut:
    session, _ = get_session_by_id(db, session_id, student)
    coaching = db.scalar(select(CoachingSession).where(CoachingSession.session_id == session.id))
    if coaching is None:
        raise domain_error(status.HTTP_409_CONFLICT, "COACHING_NOT_STARTED", "这次辅导还没有开始。")
    turns = db.scalars(
        select(CoachingTurn).where(CoachingTurn.session_id == session.id).order_by(CoachingTurn.round_number)
    ).all()
    return CoachingOut(
        session_id=session.id, status=coaching.status, current_round=coaching.current_round,
        max_rounds=coaching.max_rounds,
        turns=[CoachingTurnOut(
            id=turn.id, round_number=turn.round_number, question_text=turn.question_text,
            focus_element=turn.focus_element, scaffold_type=turn.scaffold_type,
            student_response=turn.student_response, status=turn.status,
        ) for turn in turns],
    )


def start_coaching(
    db: Session, session_id: str, student: Student, expected_version: int, idempotency_key: str,
) -> SessionSnapshotOut:
    key = validate_idempotency_key(idempotency_key)
    endpoint = f"POST:/sessions/{session_id}/coaching/start"
    payload_hash = request_hash({"expectedVersion": expected_version})
    replay = idempotent_response(db, student.id, endpoint, key, payload_hash)
    if replay is not None:
        return replay
    session, assignment = get_session_by_id(db, session_id, student)
    current = session_snapshot(db, session, assignment)
    if is_closed(assignment.deadline, datetime.now(timezone.utc)):
        raise domain_error(status.HTTP_410_GONE, "ASSIGNMENT_CLOSED", "这项作业已经截止。")
    if expected_version != session.version:
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", current)
    if "START_COACHING" not in current.allowed_actions:
        raise domain_error(status.HTTP_409_CONFLICT, "ACTION_NOT_ALLOWED", "当前步骤不能开始辅导。", current)
    analysis_row = db.scalar(select(InitialAnalysis).where(InitialAnalysis.session_id == session.id).order_by(InitialAnalysis.created_at.desc()).limit(1))
    if analysis_row is None:
        raise domain_error(status.HTTP_409_CONFLICT, "INITIAL_ANALYSIS_NOT_READY", "初步分析还没有完成。")
    raw = json.loads(analysis_row.result_json)
    opening = raw.get("opening_question") or {
        "question": "你能举一个更具体的例子，帮助别人理解你的理由吗？",
        "focus_element": "evidence", "scaffold_type": "concrete_example",
    }
    now = datetime.now(timezone.utc)
    coaching = CoachingSession(
        id=str(uuid4()), session_id=session.id, status="ACTIVE", current_round=1,
        max_rounds=20, started_at=now,
    )
    turn = CoachingTurn(
        id=str(uuid4()), session_id=session.id, round_number=1,
        question_text=opening["question"], focus_element=opening["focus_element"],
        scaffold_type=opening["scaffold_type"], status="READY",
        question_schema_version="coaching-question-v1", created_at=now,
    )
    db.add_all([coaching, turn])
    changed = db.execute(update(AnswerSession).where(
        AnswerSession.id == session.id, AnswerSession.version == expected_version
    ).values(phase="COACHING", version=expected_version + 1, updated_at=now))
    if changed.rowcount != 1:
        db.rollback()
        latest, latest_assignment = get_session_by_id(db, session_id, student)
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", session_snapshot(db, latest, latest_assignment))
    db.flush(); db.expire(session)
    snapshot = session_snapshot(db, session, assignment)
    save_idempotency(db, student.id, endpoint, key, payload_hash, snapshot)
    db.commit()
    return snapshot


def submit_coaching_response(
    db: Session, ai_gateway: AiGateway, session_id: str, turn_id: str, student: Student,
    answer: str, expected_version: int, idempotency_key: str, request_id: Optional[str],
) -> SessionSnapshotOut:
    key = validate_idempotency_key(idempotency_key)
    normalized = answer.strip()
    if not normalized:
        raise domain_error(status.HTTP_400_BAD_REQUEST, "INVALID_ANSWER", "请先写下你的回答。")
    endpoint = f"POST:/sessions/{session_id}/coaching/turns/{turn_id}/response"
    payload_hash = request_hash({"answer": normalized, "expectedVersion": expected_version})
    replay = idempotent_response(db, student.id, endpoint, key, payload_hash)
    if replay is not None:
        return replay
    session, assignment = get_session_by_id(db, session_id, student)
    current = session_snapshot(db, session, assignment)
    if is_closed(assignment.deadline, datetime.now(timezone.utc)):
        raise domain_error(status.HTTP_410_GONE, "ASSIGNMENT_CLOSED", "这项作业已经截止。")
    if expected_version != session.version:
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", current)
    turn = db.get(CoachingTurn, turn_id)
    coaching = db.scalar(select(CoachingSession).where(CoachingSession.session_id == session.id))
    if turn is None or turn.session_id != session.id or coaching is None or coaching.status != "ACTIVE" or turn.status != "READY":
        raise domain_error(status.HTTP_409_CONFLICT, "ACTION_NOT_ALLOWED", "当前问题不能提交回答。", current)
    now = datetime.now(timezone.utc)
    turn.student_response = normalized
    turn.status = "ANSWERED"
    turn.answered_at = now
    if turn.round_number >= coaching.max_rounds:
        coaching.status = "ENDED_BY_LIMIT"
        coaching.ended_at = now
        next_phase = "FINAL_DRAFT"
    else:
        next_round = turn.round_number + 1
        coaching.current_round = next_round
        job = AiJob(
            id=str(uuid4()), session_id=session.id, job_type="COACHING_QUESTION", status="QUEUED",
            input_version=next_round, attempts=0, next_run_at=now, created_at=now, updated_at=now,
        )
        next_turn = CoachingTurn(
            id=str(uuid4()), session_id=session.id, round_number=next_round, status="WAITING",
            question_job_id=job.id, question_schema_version="coaching-question-v1", created_at=now,
        )
        db.add_all([job, next_turn])
        ai_gateway.record_queued(db, job, AiRequestContext(
            request_id, "COACHING_QUESTION", "coaching-question-v1", "coaching-question-v1",
        ), {"sessionId": session.id, "roundNumber": next_round, "answer": normalized})
        next_phase = "COACHING"
    changed = db.execute(update(AnswerSession).where(
        AnswerSession.id == session.id, AnswerSession.version == expected_version
    ).values(phase=next_phase, version=expected_version + 1, updated_at=now))
    if changed.rowcount != 1:
        db.rollback()
        latest, latest_assignment = get_session_by_id(db, session_id, student)
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", session_snapshot(db, latest, latest_assignment))
    db.flush(); db.expire(session)
    snapshot = session_snapshot(db, session, assignment)
    save_idempotency(db, student.id, endpoint, key, payload_hash, snapshot)
    db.commit()
    return snapshot


def end_coaching(
    db: Session, session_id: str, student: Student, expected_version: int, idempotency_key: str,
) -> SessionSnapshotOut:
    key = validate_idempotency_key(idempotency_key)
    endpoint = f"POST:/sessions/{session_id}/coaching/end"
    payload_hash = request_hash({"expectedVersion": expected_version})
    replay = idempotent_response(db, student.id, endpoint, key, payload_hash)
    if replay is not None:
        return replay
    session, assignment = get_session_by_id(db, session_id, student)
    current = session_snapshot(db, session, assignment)
    if expected_version != session.version:
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", current)
    if "END_COACHING" not in current.allowed_actions:
        raise domain_error(status.HTTP_409_CONFLICT, "ACTION_NOT_ALLOWED", "当前步骤不能结束辅导。", current)
    coaching = db.scalar(select(CoachingSession).where(CoachingSession.session_id == session.id))
    now = datetime.now(timezone.utc)
    if coaching is None:
        raise domain_error(status.HTTP_409_CONFLICT, "COACHING_NOT_STARTED", "这次辅导还没有开始。")
    coaching.status = "ENDED_BY_STUDENT"; coaching.ended_at = now
    changed = db.execute(update(AnswerSession).where(
        AnswerSession.id == session.id, AnswerSession.version == expected_version
    ).values(phase="FINAL_DRAFT", version=expected_version + 1, updated_at=now))
    if changed.rowcount != 1:
        db.rollback()
        latest, latest_assignment = get_session_by_id(db, session_id, student)
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", session_snapshot(db, latest, latest_assignment))
    db.flush(); db.expire(session)
    snapshot = session_snapshot(db, session, assignment)
    save_idempotency(db, student.id, endpoint, key, payload_hash, snapshot)
    db.commit()
    return snapshot


def submit_final_answer(
    db: Session,
    ai_gateway: AiGateway,
    session_id: str,
    student: Student,
    answer: str,
    expected_version: int,
    idempotency_key: str,
    request_id: Optional[str],
) -> SessionSnapshotOut:
    key = validate_idempotency_key(idempotency_key)
    normalized_answer = answer.strip()
    if not normalized_answer:
        raise domain_error(status.HTTP_400_BAD_REQUEST, "INVALID_ANSWER", "请先完成修改稿。")
    endpoint = f"POST:/sessions/{session_id}/final-answer"
    payload_hash = request_hash({"answer": normalized_answer, "expectedVersion": expected_version})
    replay = idempotent_response(db, student.id, endpoint, key, payload_hash)
    if replay is not None:
        return replay
    session, assignment = get_session_by_id(db, session_id, student)
    current = session_snapshot(db, session, assignment)
    if is_closed(assignment.deadline, datetime.now(timezone.utc)):
        raise domain_error(status.HTTP_410_GONE, "ASSIGNMENT_CLOSED", "这项作业已经截止。")
    if expected_version != session.version:
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", current)
    if "SUBMIT_FINAL_ANSWER" not in current.allowed_actions:
        raise domain_error(status.HTTP_409_CONFLICT, "ACTION_NOT_ALLOWED", "当前步骤不能提交修改稿。", current)

    now = datetime.now(timezone.utc)
    submission_id = str(uuid4())
    changed = db.execute(
        update(AnswerSession)
        .where(AnswerSession.id == session.id, AnswerSession.version == expected_version)
        .values(
            phase="RESULT", submission_status="SUBMITTED", version=expected_version + 1, updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        latest, latest_assignment = get_session_by_id(db, session_id, student)
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", session_snapshot(db, latest, latest_assignment))
    submission = AnswerSubmission(
        id=submission_id, session_id=session.id, submission_version=1,
        answer_text=normalized_answer, source_session_version=expected_version, submitted_at=now,
    )
    db.add(submission)
    db.flush()
    db.execute(
        update(AnswerSession)
        .where(AnswerSession.id == session.id, AnswerSession.version == expected_version + 1)
        .values(current_submission_id=submission.id)
        .execution_options(synchronize_session=False)
    )
    job = AiJob(
        id=str(uuid4()), session_id=session.id, job_type="FINAL_EVALUATION", status="QUEUED",
        input_version=expected_version + 1, attempts=0, next_run_at=now, created_at=now, updated_at=now,
    )
    db.add(job)
    ai_gateway.record_queued(
        db, job,
        AiRequestContext(request_id, "FINAL_EVALUATION", "final-evaluation-v1", "final-evaluation-v1"),
        {"assignmentId": assignment.id, "sessionId": session.id, "initialAnswer": session.initial_answer or "", "finalAnswer": normalized_answer},
    )
    db.flush()
    db.expire(session)
    snapshot = session_snapshot(db, session, assignment)
    save_idempotency(db, student.id, endpoint, key, payload_hash, snapshot)
    db.commit()
    return snapshot


def get_initial_analysis(db: Session, session_id: str, student: Student) -> InitialAnalysisOut:
    session, _ = get_session_by_id(db, session_id, student)
    result = db.scalar(
        select(InitialAnalysis)
        .where(InitialAnalysis.session_id == session.id)
        .order_by(InitialAnalysis.created_at.desc())
        .limit(1)
    )
    if result is None:
        raise domain_error(status.HTTP_409_CONFLICT, "INITIAL_ANALYSIS_NOT_READY", "初步分析还没有完成。")
    return InitialAnalysisOut(
        session_id=session.id,
        input_version=result.input_version,
        initial_answer=session.initial_answer or "",
        analysis=(InitialAnalysisV2 if result.schema_version == "initial-analysis-v2" else InitialAnalysisV1).model_validate_json(result.result_json),
    )


def get_final_evaluation(db: Session, session_id: str, student: Student) -> FinalEvaluationOut:
    session, _ = get_session_by_id(db, session_id, student)
    if not session.current_submission_id:
        raise domain_error(status.HTTP_409_CONFLICT, "FINAL_EVALUATION_NOT_READY", "终稿评价还没有完成。")
    submission = db.get(AnswerSubmission, session.current_submission_id)
    result = db.scalar(
        select(FinalEvaluation).where(FinalEvaluation.submission_id == session.current_submission_id).limit(1)
    )
    if submission is None or result is None:
        raise domain_error(status.HTTP_409_CONFLICT, "FINAL_EVALUATION_NOT_READY", "终稿评价还没有完成。")
    return FinalEvaluationOut(
        session_id=session.id, submission_id=submission.id,
        initial_answer=session.initial_answer or "", final_answer=submission.answer_text,
        evaluation=FinalEvaluationV1.model_validate_json(result.result_json),
    )


def retry_final_evaluation(
    db: Session,
    ai_gateway: AiGateway,
    session_id: str,
    student: Student,
    expected_version: int,
    idempotency_key: str,
    request_id: Optional[str],
) -> SessionSnapshotOut:
    key = validate_idempotency_key(idempotency_key)
    endpoint = f"POST:/sessions/{session_id}/final-evaluation/retry"
    payload_hash = request_hash({"sessionId": session_id, "expectedVersion": expected_version})
    replay = idempotent_response(db, student.id, endpoint, key, payload_hash)
    if replay is not None:
        return replay
    session, assignment = get_session_by_id(db, session_id, student)
    current = session_snapshot(db, session, assignment)
    if expected_version != session.version:
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", current)
    job = latest_job(db, session.id, "FINAL_EVALUATION")
    submission = db.get(AnswerSubmission, session.current_submission_id) if session.current_submission_id else None
    if job is None or submission is None or job.status != "FAILED_RETRYABLE" or "RETRY_FINAL_EVALUATION" not in current.allowed_actions:
        raise domain_error(status.HTTP_409_CONFLICT, "ACTION_NOT_ALLOWED", "当前评价任务不能重试。", current)
    now = datetime.now(timezone.utc)
    changed = db.execute(
        update(AnswerSession)
        .where(AnswerSession.id == session.id, AnswerSession.version == expected_version)
        .values(version=expected_version + 1, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        latest, latest_assignment = get_session_by_id(db, session_id, student)
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", session_snapshot(db, latest, latest_assignment))
    job.status = "QUEUED"
    job.error_code = None
    job.next_run_at = now
    job.lease_owner = None
    job.lease_expires_at = None
    job.updated_at = now
    ai_gateway.record_queued(
        db, job,
        AiRequestContext(request_id, "FINAL_EVALUATION", "final-evaluation-v1", "final-evaluation-v1"),
        {"sessionId": session.id, "initialAnswer": session.initial_answer or "", "finalAnswer": submission.answer_text},
    )
    db.flush()
    db.expire(session)
    snapshot = session_snapshot(db, session, assignment)
    save_idempotency(db, student.id, endpoint, key, payload_hash, snapshot)
    db.commit()
    return snapshot


def retry_initial_analysis(
    db: Session,
    ai_gateway: AiGateway,
    session_id: str,
    student: Student,
    idempotency_key: str,
    request_id: Optional[str],
) -> SessionSnapshotOut:
    key = validate_idempotency_key(idempotency_key)
    endpoint = f"POST:/sessions/{session_id}/initial-analysis/retry"
    payload_hash = request_hash({"sessionId": session_id})
    replay = idempotent_response(db, student.id, endpoint, key, payload_hash)
    if replay is not None:
        return replay
    session, assignment = get_session_by_id(db, session_id, student)
    job = latest_initial_analysis_job(db, session.id)
    current = session_snapshot(db, session, assignment)
    if job is None or job.status != "FAILED_RETRYABLE" or "RETRY_INITIAL_ANALYSIS" not in current.allowed_actions:
        raise domain_error(status.HTTP_409_CONFLICT, "ACTION_NOT_ALLOWED", "当前分析任务不能重试。", current)
    now = datetime.now(timezone.utc)
    job.status = "QUEUED"
    job.error_code = None
    job.next_run_at = now
    job.lease_owner = None
    job.lease_expires_at = None
    job.updated_at = now
    ai_gateway.record_queued(
        db,
        job,
        AiRequestContext(request_id, "INITIAL_ANALYSIS", "initial-analysis-v2", "initial-analysis-v2"),
        {"sessionId": session.id, "answer": session.initial_answer or ""},
    )
    db.flush()
    snapshot = session_snapshot(db, session, assignment)
    save_idempotency(db, student.id, endpoint, key, payload_hash, snapshot)
    db.commit()
    return snapshot


def retry_coaching_question(
    db: Session, ai_gateway: AiGateway, session_id: str, student: Student,
    expected_version: int, idempotency_key: str, request_id: Optional[str],
) -> SessionSnapshotOut:
    key = validate_idempotency_key(idempotency_key)
    endpoint = f"POST:/sessions/{session_id}/coaching/question/retry"
    payload_hash = request_hash({"expectedVersion": expected_version})
    replay = idempotent_response(db, student.id, endpoint, key, payload_hash)
    if replay is not None:
        return replay
    session, assignment = get_session_by_id(db, session_id, student)
    current = session_snapshot(db, session, assignment)
    if expected_version != session.version:
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", current)
    turn = db.scalar(select(CoachingTurn).where(CoachingTurn.session_id == session.id).order_by(CoachingTurn.round_number.desc()).limit(1))
    job = db.get(AiJob, turn.question_job_id) if turn and turn.question_job_id else None
    if job is None or job.status != "FAILED_RETRYABLE" or "RETRY_COACHING_QUESTION" not in current.allowed_actions:
        raise domain_error(status.HTTP_409_CONFLICT, "ACTION_NOT_ALLOWED", "当前问题不能重新生成。", current)
    now = datetime.now(timezone.utc)
    job.status = "QUEUED"; job.error_code = None; job.next_run_at = now
    job.lease_owner = None; job.lease_expires_at = None; job.updated_at = now
    if turn:
        turn.status = "WAITING"
    ai_gateway.record_queued(db, job, AiRequestContext(
        request_id, "COACHING_QUESTION", "coaching-question-v1", "coaching-question-v1",
    ), {"sessionId": session.id, "roundNumber": turn.round_number if turn else 0})
    db.execute(update(AnswerSession).where(AnswerSession.id == session.id).values(
        version=expected_version + 1, updated_at=now,
    ))
    db.flush(); db.expire(session)
    snapshot = session_snapshot(db, session, assignment)
    save_idempotency(db, student.id, endpoint, key, payload_hash, snapshot)
    db.commit()
    return snapshot


def get_session_by_id(db: Session, session_id: str, student: Student) -> tuple[AnswerSession, Assignment]:
    session = db.get(AnswerSession, session_id)
    if session is None or session.student_id != student.id:
        raise domain_error(status.HTTP_404_NOT_FOUND, "SESSION_NOT_FOUND", "没有找到这次作答。")
    assignment = db.get(Assignment, session.assignment_id)
    if assignment is None:
        raise domain_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "INCONSISTENT_SESSION_STATE", "作答数据暂时无法读取。")
    return session, assignment


def submit_initial_answer(
    db: Session,
    ai_gateway: AiGateway,
    session_id: str,
    student: Student,
    answer: str,
    expected_version: int,
    idempotency_key: str,
    request_id: Optional[str],
) -> SessionSnapshotOut:
    key = validate_idempotency_key(idempotency_key)
    normalized_answer = answer.strip()
    if not normalized_answer:
        raise domain_error(status.HTTP_400_BAD_REQUEST, "INVALID_ANSWER", "请先写下你的想法。")

    endpoint = f"POST:/sessions/{session_id}/initial-answer"
    payload_hash = request_hash({"answer": normalized_answer, "expectedVersion": expected_version})
    replay = idempotent_response(db, student.id, endpoint, key, payload_hash)
    if replay is not None:
        return replay

    session, assignment = get_session_by_id(db, session_id, student)
    current = session_snapshot(db, session, assignment)
    if is_closed(assignment.deadline, datetime.now(timezone.utc)):
        raise domain_error(status.HTTP_410_GONE, "ASSIGNMENT_CLOSED", "这项作业已经截止。")
    if expected_version != session.version:
        raise domain_error(status.HTTP_409_CONFLICT, "SESSION_VERSION_CONFLICT", "作答状态已经变化，请查看最新内容。", current)
    if "SUBMIT_INITIAL_ANSWER" not in current.allowed_actions:
        raise domain_error(status.HTTP_409_CONFLICT, "ACTION_NOT_ALLOWED", "当前步骤不能再次提交初答。", current)

    now = datetime.now(timezone.utc)
    result = db.execute(
        update(AnswerSession)
        .where(AnswerSession.id == session.id, AnswerSession.version == expected_version)
        .values(
            initial_answer=normalized_answer,
            initial_answer_submitted_at=now,
            phase="INITIAL_ANALYSIS",
            version=expected_version + 1,
            updated_at=now,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        latest, latest_assignment = get_session_by_id(db, session_id, student)
        raise domain_error(
            status.HTTP_409_CONFLICT,
            "SESSION_VERSION_CONFLICT",
            "作答状态已经变化，请查看最新内容。",
            session_snapshot(db, latest, latest_assignment),
        )

    job = AiJob(
        id=str(uuid4()),
        session_id=session.id,
        job_type="INITIAL_ANALYSIS",
        status="QUEUED",
        input_version=expected_version + 1,
        attempts=0,
        next_run_at=now,
        created_at=now,
    )
    db.add(job)
    ai_gateway.record_queued(
        db,
        job,
        AiRequestContext(
            request_id=request_id,
            operation="INITIAL_ANALYSIS",
            prompt_version="initial-analysis-v2",
            schema_version="initial-analysis-v2",
        ),
        {"assignmentId": assignment.id, "sessionId": session.id, "answer": normalized_answer},
    )
    db.flush()
    db.refresh(session)
    snapshot = session_snapshot(db, session, assignment)
    save_idempotency(db, student.id, endpoint, key, payload_hash, snapshot)
    db.commit()
    return snapshot
