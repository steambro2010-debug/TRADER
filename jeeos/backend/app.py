from datetime import date
from fastapi import FastAPI
import pandas as pd

from analytics.insights import dashboard_metrics, rank_prediction
from analytics.strategy import strategy_dataframe
from database.db import get_connection
from database.seed import (
    get_config,
    load_demo_data,
    reset_all_data,
    seed_if_empty,
    set_config,
    start_fresh,
)
from models.schemas import DailyPlanRequest, HabitIn, MockTestIn, StudySessionIn
from modules.planner import generate_daily_plan
from modules.revision import schedule_revision
from modules.syllabus_data import FULL_JEE_SYLLABUS

app = FastAPI(title="JEEOS API", version="3.0.0")
DEFAULT_USER = 1


@app.on_event("startup")
def startup() -> None:
    seed_if_empty()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/config")
def config_state():
    cfg = get_config()
    return {
        "first_time_setup_done": cfg.get("first_time_setup_done", "0") == "1",
        "demo_mode": cfg.get("demo_mode", "1") == "1",
    }


@app.post("/start-fresh")
def api_start_fresh():
    start_fresh(DEFAULT_USER)
    return {"message": "Started fresh with empty tracking data."}


@app.post("/reset-all")
def api_reset_all():
    reset_all_data(DEFAULT_USER)
    return {"message": "All tracking data reset."}


@app.post("/config/demo-mode")
def set_demo_mode(payload: dict):
    enabled = bool(payload.get("enabled", False))
    set_config("demo_mode", "1" if enabled else "0")
    set_config("first_time_setup_done", "1")
    if enabled:
        load_demo_data(DEFAULT_USER, force_clear=True)
    return {"demo_mode": enabled}


@app.get("/chapters/{subject}")
def chapters_by_subject(subject: str):
    return {"subject": subject, "chapters": FULL_JEE_SYLLABUS.get(subject, [])}


@app.get("/dashboard")
def dashboard():
    return dashboard_metrics(DEFAULT_USER)


@app.get("/analytics-overview")
def analytics_overview():
    with get_connection() as conn:
        study = pd.read_sql_query(
            "SELECT date(start_time) day, subject, SUM(duration_minutes)/60 hours FROM study_sessions WHERE user_id=? GROUP BY date(start_time), subject",
            conn,
            params=(DEFAULT_USER,),
        )
        syllabus = pd.read_sql_query(
            "SELECT s.subject, s.chapter, sp.completion_status, sp.accuracy FROM syllabus_progress sp JOIN syllabus s ON sp.syllabus_id=s.id WHERE sp.user_id=?",
            conn,
            params=(DEFAULT_USER,),
        )
        tests = pd.read_sql_query(
            "SELECT physics_score, chemistry_score, math_score FROM mock_tests WHERE user_id=?",
            conn,
            params=(DEFAULT_USER,),
        )

    subject_dist = study.groupby("subject", as_index=False)["hours"].sum() if not study.empty else pd.DataFrame(columns=["subject", "hours"])
    daily_hours = study.groupby("day", as_index=False)["hours"].sum() if not study.empty else pd.DataFrame(columns=["day", "hours"])
    completion_pct = float((syllabus["completion_status"].mean() * 100) if not syllabus.empty else 0)

    perf_data = []
    if not tests.empty:
        perf_data = [
            {"subject": "Physics", "score": round(float(tests["physics_score"].mean()), 2)},
            {"subject": "Chemistry", "score": round(float(tests["chemistry_score"].mean()), 2)},
            {"subject": "Mathematics", "score": round(float(tests["math_score"].mean()), 2)},
        ]

    return {
        "subject_distribution": subject_dist.to_dict(orient="records"),
        "daily_hours": daily_hours.sort_values("day").to_dict(orient="records"),
        "completion_split": [
            {"label": "Completed", "value": round(completion_pct, 2)},
            {"label": "Remaining", "value": round(100 - completion_pct, 2)},
        ],
        "subject_performance": perf_data,
        "weak_topic_heatmap": syllabus.to_dict(orient="records"),
    }


@app.post("/study-session")
def add_study_session(payload: StudySessionIn):
    minutes = max(0.0, (payload.end_time - payload.start_time).total_seconds() / 60)
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO study_sessions(user_id, start_time, end_time, subject, chapter, questions_solved, duration_minutes) VALUES(?,?,?,?,?,?,?)",
            (DEFAULT_USER, payload.start_time.isoformat(), payload.end_time.isoformat(), payload.subject, payload.chapter, payload.questions_solved, minutes),
        )
        conn.execute(
            """
            UPDATE syllabus_progress
            SET questions_solved = questions_solved + ?,
                completion_status = MIN(1.0, completion_status + CASE WHEN ? >= 20 THEN 0.04 ELSE 0.02 END),
                accuracy = MIN(1.0, accuracy + 0.015),
                confidence_score = MIN(1.0, confidence_score + 0.012),
                last_revision_date = ?
            WHERE user_id=? AND syllabus_id=(SELECT id FROM syllabus WHERE subject=? AND chapter=? LIMIT 1)
            """,
            (payload.questions_solved, payload.questions_solved, date.today().isoformat(), DEFAULT_USER, payload.subject, payload.chapter),
        )
        conn.commit()
    schedule_revision(DEFAULT_USER, payload.chapter)
    return {"message": "session saved", "minutes": minutes}


@app.get("/syllabus")
def get_syllabus():
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT s.subject, s.chapter, sp.completion_status, sp.confidence_score, sp.questions_solved, sp.accuracy, sp.last_revision_date FROM syllabus_progress sp JOIN syllabus s ON sp.syllabus_id=s.id WHERE sp.user_id=? ORDER BY s.subject, s.chapter",
            conn,
            params=(DEFAULT_USER,),
        )
    return df.to_dict(orient="records")


@app.post("/mock-test")
def add_mock_test(payload: MockTestIn):
    total = payload.physics_score + payload.chemistry_score + payload.math_score
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO mock_tests(user_id, test_name, test_date, physics_score, chemistry_score, math_score, total_score) VALUES(?,?,?,?,?,?,?)",
            (DEFAULT_USER, payload.test_name, payload.test_date.isoformat(), payload.physics_score, payload.chemistry_score, payload.math_score, total),
        )
        conn.commit()
    return {"message": "mock test saved", "total": total}


@app.get("/mock-analytics")
def mock_analytics():
    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT test_name, test_date, physics_score, chemistry_score, math_score, total_score FROM mock_tests WHERE user_id=? ORDER BY test_date",
            conn,
            params=(DEFAULT_USER,),
        )
    insights = {
        "best_subject": df[["physics_score", "chemistry_score", "math_score"]].mean().idxmax() if not df.empty else "N/A",
        "improvement": float(df["total_score"].iloc[-1] - df["total_score"].iloc[0]) if len(df) > 1 else 0,
    }
    return {"tests": df.to_dict(orient="records"), "insights": insights}


@app.post("/daily-plan")
def create_daily_plan(payload: DailyPlanRequest):
    generate_daily_plan(DEFAULT_USER, payload.available_hours)
    return {"message": "daily plan generated"}


@app.get("/daily-plan")
def fetch_daily_plan():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, task, subject, chapter, task_type, target, completed FROM daily_plan WHERE user_id=? AND plan_date=?",
            (DEFAULT_USER, date.today().isoformat()),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/daily-plan/{task_id}/toggle")
def toggle_plan_task(task_id: int):
    with get_connection() as conn:
        row = conn.execute("SELECT completed FROM daily_plan WHERE id=? AND user_id=?", (task_id, DEFAULT_USER)).fetchone()
        if row:
            conn.execute("UPDATE daily_plan SET completed=? WHERE id=?", (0 if row["completed"] else 1, task_id))
            conn.commit()
    return {"message": "updated"}


@app.post("/habit")
def add_habit(payload: HabitIn):
    values = [payload.woke_on_time, payload.completed_sessions, payload.no_phone_usage, payload.did_revision, payload.solved_pyq, payload.exercise, payload.slept_on_time]
    score = (sum(values) / len(values)) * 100
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO habits(user_id, habit_date, woke_on_time, completed_sessions, no_phone_usage, did_revision, solved_pyq, exercise, slept_on_time, discipline_score) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (DEFAULT_USER, payload.habit_date.isoformat(), *[int(v) for v in values], score),
        )
        conn.commit()
    return {"discipline_score": score}


@app.get("/rank-prediction")
def get_rank_prediction():
    return rank_prediction(DEFAULT_USER)


@app.get("/weak-topics")
def weak_topics():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT s.subject, s.chapter, sp.accuracy, sp.confidence_score FROM syllabus_progress sp JOIN syllabus s ON sp.syllabus_id=s.id WHERE sp.user_id=? ORDER BY (sp.accuracy + sp.confidence_score) ASC LIMIT 10",
            (DEFAULT_USER,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/revision-tasks")
def revision_tasks():
    with get_connection() as conn:
        rows = conn.execute("SELECT chapter, due_date, interval_day, completed FROM revision_schedule WHERE user_id=? ORDER BY due_date LIMIT 25", (DEFAULT_USER,)).fetchall()
    return [dict(r) for r in rows]


@app.get("/strategy")
def strategy_data():
    return strategy_dataframe().to_dict(orient="records")
