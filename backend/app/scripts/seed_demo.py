from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select

from app.config import get_settings
from app.infrastructure.database import create_session_factory
from app.modules.assignments.models import Assignment
from app.modules.identity.models import Student

ASSIGNMENT_TEMPLATES = (
    (
        "校园里的安静角落",
        "学校里是否应该设置一个安静角落，让同学可以在课间阅读或休息？请说清楚你的观点和理由。",
    ),
    (
        "一次有意义的合作",
        "小组任务中，怎样的分工才算公平？请结合一次经历或设想，说说你的判断。",
    ),
)

GRADE_ASSIGNMENT_TEMPLATES = {
    5: (
        (
            "吞食者与被圈养：生存还是自由？",
            "为了延续生命，人类是否应该选择成为吞食者文明圈养的家畜？请说明你的态度和理由。",
        ),
        (
            "微信群问卷能代表所有人吗？",
            "学校家委会仅凭一份“82%家长赞同”的微信群问卷，便宣布增加周末试卷。你认为这份数据足以支持该决定吗？",
        ),
    ),
}


def seed_demo_students() -> int:
    session_factory = create_session_factory(get_settings())
    created = 0
    with session_factory() as session, session.begin():
        existing = set(session.scalars(select(Student.id)))
        for grade in range(1, 8):
            student_id = str(uuid5(NAMESPACE_URL, f"weixue-demo-grade-{grade}"))
            if student_id in existing:
                continue
            session.add(
                Student(
                    id=student_id,
                    display_name=f"{grade}年级体验学生",
                    grade=grade,
                    is_demo=True,
                )
            )
            created += 1
    return created


def seed_demo_assignments() -> int:
    session_factory = create_session_factory(get_settings())
    created = 0
    with session_factory() as session, session.begin():
        existing = set(session.scalars(select(Assignment.id)))
        for grade in range(1, 8):
            for index, (title, prompt) in enumerate(ASSIGNMENT_TEMPLATES, start=1):
                assignment_id = str(uuid5(NAMESPACE_URL, f"weixue-demo-assignment-{grade}-{index}"))
                if assignment_id in existing:
                    continue
                grade_prompt = prompt
                if grade >= 5:
                    grade_prompt += " 请考虑可能不同意你的人会怎么想。"
                session.add(
                    Assignment(
                        id=assignment_id,
                        title=title,
                        prompt=grade_prompt,
                        grade=grade,
                        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        deadline=datetime(2027, 7, 1, tzinfo=timezone.utc),
                    )
                )
                created += 1
            for index, (title, prompt) in enumerate(GRADE_ASSIGNMENT_TEMPLATES.get(grade, ()), start=1):
                assignment_id = str(uuid5(NAMESPACE_URL, f"weixue-demo-assignment-{grade}-supplement-{index}"))
                if assignment_id in existing:
                    continue
                session.add(
                    Assignment(
                        id=assignment_id,
                        title=title,
                        prompt=prompt,
                        grade=grade,
                        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                        deadline=datetime(2027, 7, 1, tzinfo=timezone.utc),
                    )
                )
                created += 1
    return created


if __name__ == "__main__":
    student_count = seed_demo_students()
    assignment_count = seed_demo_assignments()
    print(f"Created {student_count} demo students and {assignment_count} assignments.")
