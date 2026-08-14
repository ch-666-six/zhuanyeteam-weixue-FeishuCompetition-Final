from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from app.modules.sessions.models import AnswerSession


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def is_closed(deadline: Optional[datetime], now: datetime) -> bool:
    normalized = as_utc(deadline)
    return normalized is not None and normalized <= now


def allowed_actions(
    session: AnswerSession, deadline: Optional[datetime], now: datetime,
    initial_analysis_status: Optional[str] = None, final_evaluation_status: Optional[str] = None,
    coaching_question_status: Optional[str] = None, coaching_turn_answered: bool = False,
) -> List[str]:
    closed = is_closed(deadline, now)
    if session.phase == "INITIAL_DRAFT" and not closed:
        return ["SUBMIT_INITIAL_ANSWER"]
    if session.phase == "INITIAL_ANALYSIS" and initial_analysis_status == "FAILED_RETRYABLE":
        return ["RETRY_INITIAL_ANALYSIS"]
    if session.phase == "INITIAL_ANALYSIS" and initial_analysis_status == "SUCCEEDED" and not closed:
        return ["START_COACHING", "START_FINAL_DRAFT"]
    if session.phase == "COACHING" and not closed:
        actions = ["END_COACHING"]
        if coaching_question_status == "SUCCEEDED" and not coaching_turn_answered:
            actions.insert(0, "SUBMIT_COACHING_RESPONSE")
        elif coaching_question_status == "FAILED_RETRYABLE":
            actions.insert(0, "RETRY_COACHING_QUESTION")
        return actions
    if session.phase == "FINAL_DRAFT" and not closed:
        return ["SUBMIT_FINAL_ANSWER"]
    if session.phase == "RESULT" and final_evaluation_status == "FAILED_RETRYABLE":
        return ["RETRY_FINAL_EVALUATION"]
    return []


def next_view(
    session: AnswerSession, initial_analysis_status: Optional[str] = None,
    final_evaluation_status: Optional[str] = None, coaching_question_status: Optional[str] = None,
) -> str:
    if session.phase == "INITIAL_DRAFT":
        return "INITIAL_DRAFT"
    if session.phase == "INITIAL_ANALYSIS":
        if initial_analysis_status == "SUCCEEDED":
            return "INITIAL_ANALYSIS"
        return "INITIAL_ANALYSIS_PENDING"
    if session.phase == "COACHING":
        return "COACHING" if coaching_question_status == "SUCCEEDED" else "COACHING_PENDING"
    if session.phase == "FINAL_DRAFT":
        return "FINAL_DRAFT"
    if session.phase == "RESULT":
        if final_evaluation_status == "SUCCEEDED":
            return "RESULT"
        return "FINAL_EVALUATION_PENDING"
    raise ValueError(f"Unknown session phase: {session.phase}")
