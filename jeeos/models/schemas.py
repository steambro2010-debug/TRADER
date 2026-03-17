from datetime import date, datetime
from pydantic import BaseModel, Field


class StudySessionIn(BaseModel):
    start_time: datetime
    end_time: datetime
    subject: str
    chapter: str
    questions_solved: int = 0


class MockTestIn(BaseModel):
    test_name: str
    test_date: date
    physics_score: float
    chemistry_score: float
    math_score: float


class HabitIn(BaseModel):
    habit_date: date
    woke_on_time: bool
    completed_sessions: bool
    no_phone_usage: bool
    did_revision: bool
    solved_pyq: bool
    exercise: bool
    slept_on_time: bool


class DailyPlanRequest(BaseModel):
    available_hours: float = Field(gt=0)
