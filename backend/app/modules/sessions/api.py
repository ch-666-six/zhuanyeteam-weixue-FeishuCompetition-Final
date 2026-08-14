import asyncio
import json

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.ai.gateway import AiGateway
from app.infrastructure.database import get_db
from app.modules.identity.models import Student
from app.modules.identity.security import get_current_student
from app.modules.sessions.application import (
    create_answer_session,
    end_coaching,
    get_coaching,
    get_session_by_id,
    get_initial_analysis,
    get_final_evaluation,
    retry_final_evaluation,
    retry_initial_analysis,
    retry_coaching_question,
    session_snapshot,
    start_final_draft,
    start_coaching,
    submit_coaching_response,
    submit_final_answer,
    submit_initial_answer,
)
from app.modules.sessions.schemas import CoachingOut, CoachingResponseIn, CreateSessionIn, FinalAnswerIn, FinalEvaluationOut, InitialAnalysisOut, InitialAnswerIn, SessionSnapshotOut, VersionedActionIn
from app.modules.sessions.models import CoachingTurn

router = APIRouter(prefix="/sessions", tags=["answer sessions"])


def get_ai_gateway(request: Request) -> AiGateway:
    return request.app.state.ai_gateway


@router.post("", response_model=SessionSnapshotOut, status_code=status.HTTP_201_CREATED)
def create_session(
    body: CreateSessionIn,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> SessionSnapshotOut:
    return create_answer_session(db, body.assignment_id, student, idempotency_key)


@router.get("/{session_id}", response_model=SessionSnapshotOut)
def get_session(
    session_id: str,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> SessionSnapshotOut:
    answer_session, assignment = get_session_by_id(db, session_id, student)
    return session_snapshot(db, answer_session, assignment)


@router.post("/{session_id}/initial-answer", response_model=SessionSnapshotOut)
def submit_answer(
    session_id: str,
    body: InitialAnswerIn,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    ai_gateway: AiGateway = Depends(get_ai_gateway),
) -> SessionSnapshotOut:
    return submit_initial_answer(
        db=db,
        ai_gateway=ai_gateway,
        session_id=session_id,
        student=student,
        answer=body.answer,
        expected_version=body.expected_version,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
    )


@router.get("/{session_id}/initial-analysis", response_model=InitialAnalysisOut)
def read_initial_analysis(
    session_id: str,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> InitialAnalysisOut:
    return get_initial_analysis(db, session_id, student)


@router.post("/{session_id}/initial-analysis/retry", response_model=SessionSnapshotOut)
def retry_analysis(
    session_id: str,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    ai_gateway: AiGateway = Depends(get_ai_gateway),
) -> SessionSnapshotOut:
    return retry_initial_analysis(db, ai_gateway, session_id, student, idempotency_key, request.state.request_id)


@router.post("/{session_id}/final-draft", response_model=SessionSnapshotOut)
def begin_final_draft(
    session_id: str,
    body: VersionedActionIn,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> SessionSnapshotOut:
    return start_final_draft(db, session_id, student, body.expected_version, idempotency_key)


@router.post("/{session_id}/coaching/start", response_model=SessionSnapshotOut)
def begin_coaching(
    session_id: str, body: VersionedActionIn,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    student: Student = Depends(get_current_student), db: Session = Depends(get_db),
) -> SessionSnapshotOut:
    return start_coaching(db, session_id, student, body.expected_version, idempotency_key)


@router.get("/{session_id}/coaching", response_model=CoachingOut)
def read_coaching(
    session_id: str, student: Student = Depends(get_current_student), db: Session = Depends(get_db),
) -> CoachingOut:
    return get_coaching(db, session_id, student)


@router.post("/{session_id}/coaching/turns/{turn_id}/response", response_model=SessionSnapshotOut)
def answer_coaching_turn(
    session_id: str, turn_id: str, body: CoachingResponseIn, request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    student: Student = Depends(get_current_student), db: Session = Depends(get_db),
    ai_gateway: AiGateway = Depends(get_ai_gateway),
) -> SessionSnapshotOut:
    return submit_coaching_response(
        db, ai_gateway, session_id, turn_id, student, body.answer, body.expected_version,
        idempotency_key, request.state.request_id,
    )


@router.post("/{session_id}/coaching/end", response_model=SessionSnapshotOut)
def finish_coaching(
    session_id: str, body: VersionedActionIn,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    student: Student = Depends(get_current_student), db: Session = Depends(get_db),
) -> SessionSnapshotOut:
    return end_coaching(db, session_id, student, body.expected_version, idempotency_key)


@router.post("/{session_id}/coaching/question/retry", response_model=SessionSnapshotOut)
def retry_question(
    session_id: str, body: VersionedActionIn, request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    student: Student = Depends(get_current_student), db: Session = Depends(get_db),
    ai_gateway: AiGateway = Depends(get_ai_gateway),
) -> SessionSnapshotOut:
    return retry_coaching_question(
        db, ai_gateway, session_id, student, body.expected_version, idempotency_key, request.state.request_id,
    )


@router.get("/{session_id}/coaching/turns/{turn_id}/stream")
def stream_coaching_question(
    session_id: str, turn_id: str,
    student: Student = Depends(get_current_student), db: Session = Depends(get_db),
) -> StreamingResponse:
    answer_session, _ = get_session_by_id(db, session_id, student)
    turn = db.get(CoachingTurn, turn_id)
    if turn is None or turn.session_id != answer_session.id or turn.status not in ("READY", "ANSWERED") or not turn.question_text:
        from app.modules.sessions.application import domain_error
        raise domain_error(status.HTTP_409_CONFLICT, "COACHING_QUESTION_NOT_READY", "辅导问题还没有准备好。")
    question = turn.question_text

    async def events():
        yield f"event: meta\ndata: {json.dumps({'turn_id': turn_id, 'round_number': turn.round_number})}\n\n"
        for index in range(0, len(question), 3):
            yield f"event: delta\ndata: {json.dumps({'text': question[index:index + 3]}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0.018)
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/{session_id}/final-answer", response_model=SessionSnapshotOut)
def submit_final(
    session_id: str,
    body: FinalAnswerIn,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    ai_gateway: AiGateway = Depends(get_ai_gateway),
) -> SessionSnapshotOut:
    return submit_final_answer(
        db, ai_gateway, session_id, student, body.answer, body.expected_version,
        idempotency_key, request.state.request_id,
    )


@router.get("/{session_id}/final-evaluation", response_model=FinalEvaluationOut)
def read_final_evaluation(
    session_id: str,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
) -> FinalEvaluationOut:
    return get_final_evaluation(db, session_id, student)


@router.post("/{session_id}/final-evaluation/retry", response_model=SessionSnapshotOut)
def retry_evaluation(
    session_id: str,
    body: VersionedActionIn,
    request: Request,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    ai_gateway: AiGateway = Depends(get_ai_gateway),
) -> SessionSnapshotOut:
    return retry_final_evaluation(
        db, ai_gateway, session_id, student, body.expected_version, idempotency_key, request.state.request_id
    )
