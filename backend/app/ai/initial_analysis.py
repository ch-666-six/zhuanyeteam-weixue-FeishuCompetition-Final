from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, Field


ElementName = Literal["viewpoint", "reasons", "evidence", "counterpoint", "response", "conditions"]
ElementStatus = Literal["present", "emerging", "missing"]


class AnalysisElement(BaseModel):
    element: ElementName
    status: ElementStatus
    summary: str = Field(min_length=1, max_length=240)
    quotes: list[str] = Field(default_factory=list, max_length=3)


class PriorityImprovement(BaseModel):
    element: ElementName
    suggestion: str = Field(min_length=1, max_length=300)


class InitialAnalysisV1(BaseModel):
    schema_version: Literal["initial-analysis-v1"]
    elements: list[AnalysisElement] = Field(min_length=6, max_length=6)
    priority_improvement: Optional[PriorityImprovement] = None


class OpeningQuestion(BaseModel):
    question: str = Field(min_length=1, max_length=300)
    focus_element: ElementName
    scaffold_type: str = Field(min_length=1, max_length=48)


class InitialAnalysisV2(BaseModel):
    schema_version: Literal["initial-analysis-v2"]
    elements: list[AnalysisElement] = Field(min_length=6, max_length=6)
    priority_improvement: Optional[PriorityImprovement] = None
    opening_question: OpeningQuestion


class InvalidAnalysisOutput(ValueError):
    pass


def validate_initial_analysis(raw: dict, answer: str) -> Union[InitialAnalysisV1, InitialAnalysisV2]:
    try:
        analysis = InitialAnalysisV2.model_validate(raw) if raw.get("schema_version") == "initial-analysis-v2" else InitialAnalysisV1.model_validate(raw)
    except Exception as exc:
        raise InvalidAnalysisOutput("Model output does not match a supported initial-analysis schema") from exc

    expected = {"viewpoint", "reasons", "evidence", "counterpoint", "response", "conditions"}
    actual = [item.element for item in analysis.elements]
    if set(actual) != expected or len(set(actual)) != len(actual):
        raise InvalidAnalysisOutput("Analysis must contain each required element exactly once")
    for item in analysis.elements:
        if item.status == "present" and not item.quotes:
            raise InvalidAnalysisOutput(f"Present element {item.element} requires a quote")
        if any(not quote.strip() or quote not in answer for quote in item.quotes):
            raise InvalidAnalysisOutput("Every evidence quote must be an exact substring of the answer")
    return analysis
