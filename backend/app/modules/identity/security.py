from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.infrastructure.database import get_db
from app.modules.identity.models import Student

bearer_scheme = HTTPBearer(auto_error=False)


def create_access_token(student_id: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": student_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
        "type": "demo_student",
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256")


def get_current_student(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Student:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "请先选择学生身份。"},
        )
    try:
        payload = jwt.decode(credentials.credentials, settings.app_secret_key, algorithms=["HS256"])
        student_id = payload.get("sub")
        if not student_id or payload.get("type") != "demo_student":
            raise InvalidTokenError
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "登录已失效，请重新选择身份。"},
        ) from exc

    student = db.get(Student, student_id)
    if student is None or not student.is_demo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "AUTHENTICATION_REQUIRED", "message": "登录已失效，请重新选择身份。"},
        )
    return student
