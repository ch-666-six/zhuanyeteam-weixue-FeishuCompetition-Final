from __future__ import annotations

import json
from collections import defaultdict
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.final_evaluation import FinalEvaluationV1
from app.modules.assignments.models import Assignment
from app.modules.identity.models import Student
from app.modules.sessions.models import AnswerSession, AnswerSubmission, CoachingSession, FinalEvaluation, InitialAnalysis

from .schemas import (
    GrowthCoverageOut,
    GrowthDimensionOut,
    GrowthPointOut,
    GrowthReportOut,
    GrowthTimelineItemOut,
    TeacherConfirmationOut,
    ThinkingMoveEvidenceOut,
    ThinkingMoveOut,
)


DIMENSIONS = (
    ("attitude", "思辨态度", "perspective"),
    ("information", "信息判别", "material"),
    ("reasoning", "逻辑推理", "structure"),
    ("argument", "论证建构", "idea"),
    ("expression", "思辨表达", "language"),
)
STATUS_LEVEL = {
    "not_yet_visible": ("暂未体现", 1),
    "developing": ("正在发展", 2),
    "clear": ("表达清楚", 3),
}
MOVES = (
    ("claim", "说出看法", "我说清了自己怎么看", "viewpoint"),
    ("reason", "说出为什么", "我说明了为什么", "reasons"),
    ("evidence", "用材料支撑", "我用了相关材料", "evidence"),
    ("counterpoint", "看见别的想法", "我看见了另一种想法", "counterpoint"),
    ("response", "回应不同想法", "我回应了一个不同意见", "response"),
    ("condition", "说清条件", "我说清了条件或边界", "conditions"),
)


def _stable_level(points: list[GrowthPointOut]) -> str | None:
    eligible = [point.level_value for point in points if point.eligible]
    if len(eligible) < 3:
        return None
    value = int(median(eligible[-3:]))
    return next(label for label, level_value in STATUS_LEVEL.values() if level_value == value)


def _narrative(dimensions: list[GrowthDimensionOut], completed: int) -> str:
    if completed == 0:
        return "完成第一份作业后，这里会开始记录你的思考成长。"
    stable = [item.name for item in dimensions if item.stable_level == "表达清楚"]
    accumulating = [item.name for item in dimensions if item.stable_level is None]
    text = f"已经根据 {completed} 份已完成作业整理五维成长证据。"
    if stable:
        text += f"目前在{'、'.join(stable[:2])}上已有较稳定的清楚表达。"
    if accumulating:
        text += f"{'、'.join(accumulating[:2])}仍在积累可比较的原文证据。"
    return text


def _dimension_summary(name: str, points: list[GrowthPointOut], stable_level: str | None) -> str:
    eligible_count = sum(point.eligible for point in points)
    if eligible_count == 0:
        return f"{name}的可比较记录仍在积累，当前不对变化作判断。"
    if eligible_count < 3 or stable_level is None:
        return f"已在 {eligible_count} 份可用于观察的记录中留下{name}表现，档案仍在持续积累。"
    return f"已在多份可比较记录中形成{name}的连续观察，近期整体处于“{stable_level}”的表现状态。"


def build_report(db: Session, student: Student, grade: int | None = None) -> GrowthReportOut:
    statement = (
        select(AnswerSession, Assignment, AnswerSubmission, FinalEvaluation, CoachingSession)
        .join(Assignment, Assignment.id == AnswerSession.assignment_id)
        .join(AnswerSubmission, AnswerSubmission.id == AnswerSession.current_submission_id)
        .join(FinalEvaluation, FinalEvaluation.submission_id == AnswerSubmission.id)
        .outerjoin(CoachingSession, CoachingSession.session_id == AnswerSession.id)
        .where(AnswerSession.student_id == student.id)
        .order_by(AnswerSubmission.submitted_at.asc())
    )
    records = []
    available_grades: set[int] = set()
    for answer_session, assignment, submission, evaluation_row, coaching in db.execute(statement).all():
        try:
            evaluation = FinalEvaluationV1.model_validate(json.loads(evaluation_row.result_json))
        except (ValueError, TypeError, json.JSONDecodeError):
            continue
        available_grades.add(assignment.grade)
        if grade is not None and assignment.grade != grade:
            continue
        by_dimension = {item.dimension: item for item in evaluation.dimensions}
        records.append((answer_session, assignment, submission, evaluation, by_dimension, coaching))

    points_by_key: dict[str, list[GrowthPointOut]] = defaultdict(list)
    timeline: list[GrowthTimelineItemOut] = []
    fully_eligible_count = 0
    for answer_session, assignment, submission, evaluation, by_dimension, coaching in records:
        trend_eligible = all(
            bool(by_dimension[source].quotes) or by_dimension[source].status == "not_yet_visible"
            for _, _, source in DIMENSIONS
        )
        if trend_eligible:
            fully_eligible_count += 1
        representative = []
        representative_quote = None
        for key, name, source in DIMENSIONS:
            item = by_dimension[source]
            level, level_value = STATUS_LEVEL[item.status]
            quote = item.quotes[0] if item.quotes else None
            eligible = quote is not None or item.status == "not_yet_visible"
            points_by_key[key].append(
                GrowthPointOut(
                    session_id=answer_session.id,
                    assignment_id=assignment.id,
                    assignment_title=assignment.title,
                    submitted_at=submission.submitted_at,
                    grade=assignment.grade,
                    level=level,
                    level_value=level_value,
                    eligible=eligible,
                    quote=quote,
                    observation=item.observation,
                )
            )
            if len(representative) < 2 and item.status != "not_yet_visible":
                representative.append(name)
            if representative_quote is None and quote:
                representative_quote = quote
        rounds = coaching.current_round if coaching else 0
        timeline.append(
            GrowthTimelineItemOut(
                session_id=answer_session.id,
                assignment_id=assignment.id,
                assignment_title=assignment.title,
                submitted_at=submission.submitted_at,
                grade=assignment.grade,
                used_coaching=bool(coaching and coaching.status != "SKIPPED"),
                coaching_rounds=rounds,
                status="INCLUDED" if trend_eligible else "EVIDENCE_INCOMPLETE",
                representative_dimensions=representative,
                quote=representative_quote,
            )
        )

    dimensions = []
    for key, name, _ in DIMENSIONS:
        points = points_by_key[key]
        current = points[-1] if points else None
        stable_level = _stable_level(points)
        dimensions.append(
            GrowthDimensionOut(
                key=key,
                name=name,
                current_level=current.level if current else None,
                current_value=current.level_value if current else None,
                stable_level=stable_level,
                evidence_count=sum(point.quote is not None for point in points),
                summary=_dimension_summary(name, points, stable_level),
                points=points,
            )
        )

    record_by_session = {record[0].id: record for record in records}
    move_evidence: dict[str, list[ThinkingMoveEvidenceOut]] = defaultdict(list)
    if record_by_session:
        analyses = db.scalars(
            select(InitialAnalysis)
            .where(InitialAnalysis.session_id.in_(record_by_session))
            .order_by(InitialAnalysis.created_at.asc())
        ).all()
        latest_analysis = {analysis.session_id: analysis for analysis in analyses}
        for session_id, analysis in latest_analysis.items():
            try:
                elements = json.loads(analysis.result_json).get("elements", [])
            except (AttributeError, TypeError, json.JSONDecodeError):
                continue
            element_by_name = {item.get("element"): item for item in elements if isinstance(item, dict)}
            assignment = record_by_session[session_id][1]
            for key, _, _, element_name in MOVES:
                element = element_by_name.get(element_name, {})
                quotes = element.get("quotes") or []
                if element.get("status") == "missing" or not quotes or not isinstance(quotes[0], str):
                    continue
                move_evidence[key].append(
                    ThinkingMoveEvidenceOut(
                        session_id=session_id,
                        assignment_title=assignment.title,
                        quote=quotes[0],
                    )
                )
    thinking_moves = [
        ThinkingMoveOut(
            key=key,
            name=name,
            student_label=student_label,
            count=len(move_evidence[key]),
            evidence=list(reversed(move_evidence[key]))[:3],
        )
        for key, name, student_label, _ in MOVES
    ]

    return GrowthReportOut(
        selected_grade=grade,
        student_grade=student.grade,
        coverage=GrowthCoverageOut(
            completed_assignments=len(records),
            trend_eligible_assignments=fully_eligible_count,
            available_grades=sorted(available_grades),
        ),
        dimensions=dimensions,
        timeline=list(reversed(timeline)),
        thinking_moves=thinking_moves,
        narrative=_narrative(dimensions, len(records)),
        teacher_confirmation=TeacherConfirmationOut(total_count=len(records)),
    )
