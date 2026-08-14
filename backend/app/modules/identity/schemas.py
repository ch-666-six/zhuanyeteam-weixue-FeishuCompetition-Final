from pydantic import BaseModel, ConfigDict, Field


class DemoStudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    display_name: str
    grade: int = Field(ge=1, le=7)


class DemoLoginIn(BaseModel):
    student_id: str = Field(min_length=1, max_length=36)


class DemoLoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    student: DemoStudentOut

