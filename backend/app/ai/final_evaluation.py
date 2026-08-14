from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


DimensionName = Literal["idea", "material", "structure", "language", "perspective"]
DimensionStatus = Literal["clear", "developing", "not_yet_visible"]


class EvaluationDimension(BaseModel):
    dimension: DimensionName
    status: DimensionStatus
    observation: str = Field(min_length=1, max_length=260)
    quotes: list[str] = Field(default_factory=list, max_length=3)


class EvaluationStrength(BaseModel):
    title: str = Field(min_length=1, max_length=80)
    explanation: str = Field(min_length=1, max_length=240)
    quotes: list[str] = Field(min_length=1, max_length=2)


class EvaluationNextStep(BaseModel):
    dimension: DimensionName
    suggestion: str = Field(min_length=1, max_length=300)


class RevisionEvidence(BaseModel):
    change: str = Field(min_length=1, max_length=240)
    initial_quote: str = Field(min_length=1, max_length=300)
    final_quote: str = Field(min_length=1, max_length=300)


class FinalEvaluationV1(BaseModel):
    schema_version: Literal["final-evaluation-v1"]
    rubric_version: Literal["argument-writing-v1"]
    summary: str = Field(min_length=1, max_length=300)
    strengths: list[EvaluationStrength] = Field(min_length=1, max_length=2)
    next_step: EvaluationNextStep
    dimensions: list[EvaluationDimension] = Field(min_length=5, max_length=5)
    revision_evidence: list[RevisionEvidence] = Field(default_factory=list, max_length=3)


class InvalidFinalEvaluationOutput(ValueError):
    pass


def validate_final_evaluation(raw: dict, initial_answer: str, final_answer: str) -> FinalEvaluationV1:
    try:
        evaluation = FinalEvaluationV1.model_validate(raw)
    except Exception as exc:
        raise InvalidFinalEvaluationOutput("Model output does not match final-evaluation-v1") from exc
    expected = {"idea", "material", "structure", "language", "perspective"}
    actual = [item.dimension for item in evaluation.dimensions]
    if set(actual) != expected or len(set(actual)) != len(actual):
        raise InvalidFinalEvaluationOutput("Evaluation must contain each rubric dimension exactly once")
    final_quotes = [quote for item in evaluation.dimensions for quote in item.quotes]
    final_quotes += [quote for item in evaluation.strengths for quote in item.quotes]
    for item in evaluation.dimensions:
        if item.status != "not_yet_visible" and not item.quotes:
            raise InvalidFinalEvaluationOutput(
                f"Dimension {item.dimension} needs at least one exact quote unless it is not_yet_visible"
            )
    if any(quote not in final_answer for quote in final_quotes):
        raise InvalidFinalEvaluationOutput("Every evaluation quote must be an exact substring of the final answer")
    for evidence in evaluation.revision_evidence:
        if evidence.initial_quote not in initial_answer or evidence.final_quote not in final_answer:
            raise InvalidFinalEvaluationOutput("Revision evidence must quote the matching answer exactly")
    return evaluation
