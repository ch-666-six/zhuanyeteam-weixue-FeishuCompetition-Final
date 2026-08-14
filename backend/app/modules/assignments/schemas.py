from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.sessions.schemas import SessionSnapshotOut


class AssignmentSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    prompt: str
    grade: int = Field(ge=1, le=7)
    input_type: Literal["TEXT", "VOICE"]
    deadline: Optional[datetime]
    availability: Literal["OPEN", "CLOSED"]
    session: Optional[SessionSnapshotOut] = None


class AssignmentDetailOut(BaseModel):
    id: str
    title: str
    prompt: str
    grade: int = Field(ge=1, le=7)
    input_type: Literal["TEXT", "VOICE"]
    published_at: Optional[datetime]
    deadline: Optional[datetime]
    availability: Literal["OPEN", "CLOSED"]
    session: Optional[SessionSnapshotOut] = None


class ManagedAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    prompt: str
    grade: int = Field(ge=1, le=7)
    input_type: Literal["TEXT", "VOICE"]
    published_at: Optional[datetime]
    created_at: datetime


class ManagedAssignmentCreateIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    prompt: str = Field(min_length=5, max_length=3000)
    grades: list[int] = Field(min_length=1, max_length=7)
    input_type: Literal["TEXT", "VOICE"] = "TEXT"


class ManagedAssignmentUpdateIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    prompt: str = Field(min_length=5, max_length=3000)
    grade: int = Field(ge=1, le=7)
    input_type: Literal["TEXT", "VOICE"] = "TEXT"


class ManagedAssignmentBulkDeleteIn(BaseModel):
    ids: list[str] = Field(min_length=1, max_length=100)


class ManagedAssignmentBulkDeleteOut(BaseModel):
    deleted_ids: list[str]
    blocked_ids: list[str]
    not_found_ids: list[str]
