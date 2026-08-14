from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Optional

from sqlalchemy import and_, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.ai.gateway import AiGateway
from app.ai.initial_analysis import InvalidAnalysisOutput, validate_initial_analysis
from app.ai.coaching import InvalidCoachingOutput, validate_coaching_question
from app.ai.final_evaluation import InvalidFinalEvaluationOutput, validate_final_evaluation
from app.modules.assignments.models import Assignment
from app.modules.sessions.models import AnswerSubmission, AiJob, AiRun, AnswerSession, CoachingTurn, FinalEvaluation, InitialAnalysis


@dataclass(frozen=True)
class ClaimedJob:
    job_id: str
    run_id: str
    job_type: str
    session_id: str
    payload: dict
    submission_id: Optional[str] = None


class AiWorker:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        gateway: AiGateway,
        worker_id: str,
        lease_seconds: int = 90,
        max_attempts: int = 3,
    ):
        self.session_factory = session_factory
        self.gateway = gateway
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.max_attempts = max_attempts

    def claim_next(self) -> ClaimedJob | None:
        now = datetime.now(timezone.utc)
        with self.session_factory() as db:
            candidate = db.scalar(
                select(AiJob)
                .where(
                    AiJob.job_type.in_(["INITIAL_ANALYSIS", "COACHING_QUESTION", "FINAL_EVALUATION"]),
                    AiJob.attempts < self.max_attempts,
                    or_(
                        and_(AiJob.status == "QUEUED", AiJob.next_run_at <= now),
                        and_(AiJob.status == "RUNNING", AiJob.lease_expires_at <= now),
                    ),
                )
                .order_by(AiJob.next_run_at, AiJob.created_at)
                .limit(1)
            )
            if candidate is None:
                return None
            claimed = db.execute(
                update(AiJob)
                .where(
                    AiJob.id == candidate.id,
                    AiJob.attempts == candidate.attempts,
                    or_(
                        AiJob.status == "QUEUED",
                        and_(AiJob.status == "RUNNING", AiJob.lease_expires_at <= now),
                    ),
                )
                .values(
                    status="RUNNING",
                    attempts=candidate.attempts + 1,
                    error_code=None,
                    lease_owner=self.worker_id,
                    lease_expires_at=now + timedelta(seconds=self.lease_seconds),
                    updated_at=now,
                )
                .execution_options(synchronize_session=False)
            )
            if claimed.rowcount != 1:
                db.rollback()
                return None
            session = db.get(AnswerSession, candidate.session_id)
            assignment = db.get(Assignment, session.assignment_id) if session else None
            submission = db.get(AnswerSubmission, session.current_submission_id) if session and session.current_submission_id else None
            coaching_turn = db.scalar(select(CoachingTurn).where(CoachingTurn.question_job_id == candidate.id))
            if session is None or assignment is None or not session.initial_answer or (candidate.job_type == "FINAL_EVALUATION" and submission is None) or (candidate.job_type == "COACHING_QUESTION" and coaching_turn is None):
                db.execute(update(AiJob).where(AiJob.id == candidate.id).values(
                    status="FAILED_FINAL", error_code="INVALID_JOB_INPUT", lease_owner=None, lease_expires_at=None,
                ))
                db.commit()
                return None
            if candidate.job_type == "INITIAL_ANALYSIS":
                payload = {"assignmentPrompt": assignment.prompt, "answer": session.initial_answer}
                prompt_version = schema_version = "initial-analysis-v2"
            elif candidate.job_type == "COACHING_QUESTION":
                turns = db.scalars(select(CoachingTurn).where(CoachingTurn.session_id == session.id).order_by(CoachingTurn.round_number)).all()
                payload = {
                    "assignmentPrompt": assignment.prompt,
                    "initialAnswer": session.initial_answer,
                    "roundNumber": coaching_turn.round_number if coaching_turn else candidate.input_version,
                    "history": [
                        {"question": turn.question_text, "answer": turn.student_response}
                        for turn in turns if turn.round_number < candidate.input_version
                    ],
                }
                prompt_version = schema_version = "coaching-question-v1"
            else:
                payload = {
                    "assignmentPrompt": assignment.prompt,
                    "initialAnswer": session.initial_answer,
                    "finalAnswer": submission.answer_text,
                }
                prompt_version = schema_version = "final-evaluation-v1"
            queued_run = db.scalar(
                select(AiRun).where(AiRun.job_id == candidate.id, AiRun.status == "QUEUED").order_by(AiRun.started_at.desc())
            )
            if queued_run is None:
                queued_run = AiRun(
                    id=str(uuid4()), job_id=candidate.id, request_id=None,
                    provider=self.gateway.provider.info.name, model=self.gateway.provider.info.model,
                    operation=candidate.job_type, prompt_version=prompt_version,
                    schema_version=schema_version, status="QUEUED",
                    input_summary=self.gateway.input_summary(payload),
                    started_at=now,
                )
                db.add(queued_run)
            db.commit()
            return ClaimedJob(
                candidate.id, queued_run.id, candidate.job_type, session.id, payload,
                submission.id if submission else None,
            )

    def process_next(self) -> bool:
        claimed = self.claim_next()
        if claimed is None:
            return False
        with self.session_factory() as db:
            run = db.get(AiRun, claimed.run_id)
            if run is None:
                return False
            db.expunge(run)
            db.rollback()

        try:
            raw = self.gateway.execute(run, claimed.payload)
            if claimed.job_type == "INITIAL_ANALYSIS":
                result = validate_initial_analysis(raw, str(claimed.payload["answer"]))
            elif claimed.job_type == "COACHING_QUESTION":
                result = validate_coaching_question(raw)
            else:
                result = validate_final_evaluation(
                    raw, str(claimed.payload["initialAnswer"]), str(claimed.payload["finalAnswer"])
                )
        except Exception as exc:
            error_code = "AI_OUTPUT_INVALID" if isinstance(exc, (InvalidAnalysisOutput, InvalidCoachingOutput, InvalidFinalEvaluationOutput)) else "AI_PROVIDER_ERROR"
            self._finish_failure(claimed.job_id, run, error_code)
            return True
        self._finish_success(claimed, run, result.model_dump_json())
        return True

    def _finish_failure(self, job_id: str, run: AiRun, error_code: str) -> None:
        with self.session_factory() as db:
            job = db.get(AiJob, job_id)
            if job is None or job.lease_owner != self.worker_id or job.status != "RUNNING":
                return
            db.merge(run)
            stored_run = db.get(AiRun, run.id)
            if stored_run:
                stored_run.status = "FAILED"
                stored_run.error_code = error_code
            job.status = "FAILED_FINAL" if job.attempts >= self.max_attempts else "FAILED_RETRYABLE"
            job.error_code = error_code
            if job.job_type == "COACHING_QUESTION":
                turn = db.scalar(select(CoachingTurn).where(CoachingTurn.question_job_id == job.id))
                if turn:
                    turn.status = "FAILED" if job.attempts >= self.max_attempts else "WAITING"
            job.lease_owner = None
            job.lease_expires_at = None
            job.updated_at = datetime.now(timezone.utc)
            db.commit()

    def _finish_success(self, claimed: ClaimedJob, run: AiRun, result_json: str) -> None:
        with self.session_factory() as db:
            job = db.get(AiJob, claimed.job_id)
            if job is None or job.lease_owner != self.worker_id or job.status != "RUNNING":
                return
            if claimed.job_type == "INITIAL_ANALYSIS":
                existing = db.scalar(select(InitialAnalysis).where(InitialAnalysis.job_id == job.id))
                if existing is None:
                    db.add(InitialAnalysis(
                        id=str(uuid4()), session_id=job.session_id, job_id=job.id,
                        input_version=job.input_version, schema_version="initial-analysis-v2", result_json=result_json,
                    ))
            elif claimed.job_type == "COACHING_QUESTION":
                turn = db.scalar(select(CoachingTurn).where(CoachingTurn.question_job_id == job.id))
                if turn is not None:
                    raw = json.loads(result_json)
                    turn.question_text = raw["question"]
                    turn.focus_element = raw["focus_element"]
                    turn.scaffold_type = raw["scaffold_type"]
                    turn.status = "READY"
            else:
                existing = db.scalar(select(FinalEvaluation).where(FinalEvaluation.job_id == job.id))
                if existing is None and claimed.submission_id:
                    db.add(FinalEvaluation(
                        id=str(uuid4()), session_id=job.session_id, submission_id=claimed.submission_id,
                        job_id=job.id, schema_version="final-evaluation-v1", rubric_version="argument-writing-v1",
                        result_json=result_json,
                    ))
            db.merge(run)
            job.status = "SUCCEEDED"
            job.error_code = None
            job.lease_owner = None
            job.lease_expires_at = None
            job.updated_at = datetime.now(timezone.utc)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                result_model = InitialAnalysis if claimed.job_type == "INITIAL_ANALYSIS" else FinalEvaluation
                existing = None if claimed.job_type == "COACHING_QUESTION" else db.scalar(select(result_model).where(result_model.job_id == job.id))
                if existing is not None or claimed.job_type == "COACHING_QUESTION":
                    db.execute(update(AiJob).where(AiJob.id == job.id).values(status="SUCCEEDED", lease_owner=None, lease_expires_at=None))
                    db.commit()
