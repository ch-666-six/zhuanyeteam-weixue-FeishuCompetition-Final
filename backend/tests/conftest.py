from collections.abc import AsyncGenerator, Generator
from datetime import datetime, timezone
import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["APP_ENV"] = "test"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings, get_settings
from app.infrastructure.database import Base, get_db
from app.main import create_app
from app.modules.assignments.models import Assignment
from app.modules.identity.models import Student


@pytest.fixture()
def settings() -> Settings:
    return Settings(
        app_env="test",
        app_secret_key="test-secret-key-with-at-least-32-characters",
        database_url="sqlite+pysqlite:///:memory:",
        ai_provider="mock",
    )


@pytest.fixture()
def session_factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as session, session.begin():
        session.add_all(
            [
                Student(id="student-grade-3", display_name="3年级体验学生", grade=3, is_demo=True),
                Student(id="student-grade-4", display_name="4年级体验学生", grade=4, is_demo=True),
            ]
        )
        session.add_all(
            [
                Assignment(
                    id="assignment-grade-3",
                    title="校园里的安静角落",
                    prompt="学校里是否应该设置一个安静角落？请说清楚观点和理由。",
                    grade=3,
                    published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    deadline=datetime(2027, 7, 1, tzinfo=timezone.utc),
                ),
                Assignment(
                    id="assignment-grade-4",
                    title="四年级作业",
                    prompt="这项作业不应被三年级学生看到。",
                    grade=4,
                    published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                    deadline=datetime(2027, 7, 1, tzinfo=timezone.utc),
                ),
            ]
        )
    return factory


@pytest_asyncio.fixture()
async def client(
    settings: Settings, session_factory: sessionmaker[Session]
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app(settings)
    app.state.session_factory = session_factory

    def override_db() -> Generator[Session, None, None]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: settings
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client
