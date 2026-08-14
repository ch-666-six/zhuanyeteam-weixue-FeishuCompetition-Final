from typing import Literal

from pydantic import BaseModel, Field

from app.ai.initial_analysis import ElementName


class CoachingQuestionV1(BaseModel):
    schema_version: Literal["coaching-question-v1"]
    question: str = Field(min_length=1, max_length=300)
    focus_element: ElementName
    scaffold_type: str = Field(min_length=1, max_length=48)


class InvalidCoachingOutput(ValueError):
    pass


def validate_coaching_question(raw: dict) -> CoachingQuestionV1:
    try:
        result = CoachingQuestionV1.model_validate(raw)
    except Exception as exc:
        raise InvalidCoachingOutput("Model output does not match coaching-question-v1") from exc
    question = result.question.strip()
    if question.count("？") + question.count("?") > 1:
        raise InvalidCoachingOutput("Coaching output must contain one question")
    return result
