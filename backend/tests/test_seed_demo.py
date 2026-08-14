from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.modules.assignments.models import Assignment
from app.scripts import seed_demo


def test_grade_five_supplemental_assignments_are_seeded_once(
    session_factory: sessionmaker[Session], monkeypatch
) -> None:
    monkeypatch.setattr(seed_demo, "get_settings", lambda: object())
    monkeypatch.setattr(seed_demo, "create_session_factory", lambda _settings: session_factory)

    assert seed_demo.seed_demo_assignments() == 16
    assert seed_demo.seed_demo_assignments() == 0

    with session_factory() as db:
        rows = db.scalars(
            select(Assignment).where(
                Assignment.title.in_(
                    ["吞食者与被圈养：生存还是自由？", "微信群问卷能代表所有人吗？"]
                )
            )
        ).all()
    assert {(row.grade, row.title) for row in rows} == {
        (5, "吞食者与被圈养：生存还是自由？"),
        (5, "微信群问卷能代表所有人吗？"),
    }
