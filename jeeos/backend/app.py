from datetime import date
from fastapi import FastAPI
import pandas as pd

from analytics.insights import dashboard_metrics, rank_prediction
from analytics.strategy import strategy_dataframe
from database.db import get_connection
from models.schemas import DailyPlanRequest, HabitIn, MockTestIn, StudySessionIn
from modules.planner import generate_daily_plan
from modules.revision import schedule_revision

app = FastAPI(title="JEEOS API", version="1.0.0")
DEFAULT_USER = 1


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/dashboard")
def dashboard():
    return dashboard_metrics(DEFAULT_USER)


@app.post("/study-session")
def add_study_session(payload: StudySessionIn):
    minutes = max(0.0, (payload.end_time - payload.start_time).total_seconds() / 60)
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO study_sessions(user_id, start_time, end_time, subject, chapter, questions_solved, duration_minutes)
            VALUES(?,?,?,?,?,?,?)
            """,
            (
                DEFAULT_USER,
                payload.start_time.isoformat(),
                payload.end_time.isoformat(),
                payload.subject,
                payload.chapter,
                payload.questions_solved,
                minutes,
            ),
        )
        conn.execute(
            """
            UPDATE syllabus_progress
            SET questions_solved = questions_solved + ?,
                completion_status = MIN(1.0, completion_status + 0.03),
                accuracy = MIN(1.0, accuracy + 0.01),
                confidence_score = MIN(1.0, confidence_score + 0.01),
                last_revision_date = ?
            WHERE user_id=? AND syllabus_id=(SELECT id FROM syllabus WHERE subject=? AND chapter=? LIMIT 1)
            """,
            (payload.questions_solved, date.today().isoformat(), DEFAULT_USER, payload.subject, payload.chapter),
        )
        conn.commit()
    schedule_revision(DEFAULT_USER, payload.chapter)
    return {"message": "session saved", "minutes": minutes}


@app.get("/study-stats")
def study_stats():
    with get_connection() as conn:
        weekly = pd.read_sql_query(
            """
            SELECT date(start_time) day, SUM(duration_minutes)/60 hours
            FROM study_sessions
            WHERE user_id=?
            GROUP BY date(start_time)
            ORDER BY day DESC LIMIT 7
            """,
            conn,
            params=(DEFAULT_USER,),
        )
        subj = pd.read_sql_query(
            "SELECT subject, SUM(duration_minutes)/60 hours FROM study_sessions WHERE user_id=? GROUP BY subject",
            conn,
            params=(DEFAULT_USER,),
        )
    return {
        "weekly": weekly.to_dict(orient="records"),
        "subject_distribution": subj.to_dict(orient="records"),
    }


@app.get("/syllabus")
def get_syllabus():
    with get_connection() as conn:
        df = pd.read_sql_query(
            """
            SELECT s.subject, s.chapter, sp.completion_status, sp.confidence_score, sp.questions_solved, sp.accuracy, sp.last_revision_date
            FROM syllabus_progress sp JOIN syllabus s ON sp.syllabus_id=s.id
            WHERE sp.user_id=?
            ORDER BY s.subject, s.chapter
            """,
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


@app.post("/habit")
def add_habit(payload: HabitIn):
    values = [
        payload.woke_on_time,
        payload.completed_sessions,
        payload.no_phone_usage,
        payload.did_revision,
        payload.solved_pyq,
        payload.exercise,
        payload.slept_on_time,
    ]
    score = (sum(values) / len(values)) * 100
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO habits(user_id, habit_date, woke_on_time, completed_sessions, no_phone_usage, did_revision, solved_pyq, exercise, slept_on_time, discipline_score)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
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
            """
            SELECT s.subject, s.chapter, sp.accuracy, sp.confidence_score
            FROM syllabus_progress sp JOIN syllabus s ON sp.syllabus_id=s.id
            WHERE sp.user_id=? ORDER BY (sp.accuracy + sp.confidence_score) ASC LIMIT 8
            """,
            (DEFAULT_USER,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/revision-tasks")
def revision_tasks():
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT chapter, due_date, interval_day, completed FROM revision_schedule WHERE user_id=? ORDER BY due_date LIMIT 25",
            (DEFAULT_USER,),
        ).fetchall()
    return [dict(r) for r in rows]


@app.post("/pyq-attempt")
def add_pyq_attempt(payload: dict):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO question_attempts(user_id, year, subject, chapter, is_correct, time_taken_seconds) VALUES(?,?,?,?,?,?)",
            (DEFAULT_USER, payload["year"], payload["subject"], payload["chapter"], int(payload["is_correct"]), payload["time_taken_seconds"]),
        )
        conn.commit()
    return {"message": "pyq attempt saved"}


@app.get("/pyq-analytics")
def pyq_analytics():
    with get_connection() as conn:
        rows = pd.read_sql_query(
            "SELECT chapter, AVG(is_correct)*100 accuracy, COUNT(*) attempts FROM question_attempts WHERE user_id=? GROUP BY chapter",
            conn,
            params=(DEFAULT_USER,),
        )
    return rows.to_dict(orient="records")


@app.post("/mistake")
def add_mistake(payload: dict):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO mistake_log(user_id, question_image_path, chapter, mistake_type, note) VALUES(?,?,?,?,?)",
            (DEFAULT_USER, payload.get("question_image_path"), payload["chapter"], payload["mistake_type"], payload.get("note", "")),
        )
        conn.commit()
    return {"message": "mistake logged"}


@app.get("/mistake-analytics")
def mistake_analytics():
    with get_connection() as conn:
        rows = pd.read_sql_query(
            "SELECT mistake_type, COUNT(*) count FROM mistake_log WHERE user_id=? GROUP BY mistake_type",
            conn,
            params=(DEFAULT_USER,),
        )
    return rows.to_dict(orient="records")


@app.get("/weekly-review")
def weekly_review():
    with get_connection() as conn:
        review = conn.execute(
            """
            SELECT COALESCE(SUM(duration_minutes)/60,0) hours, COALESCE(AVG(discipline_score),0) discipline
            FROM study_sessions ss LEFT JOIN habits h ON date(ss.start_time)=h.habit_date AND h.user_id=ss.user_id
            WHERE ss.user_id=? AND date(ss.start_time)>=date('now','-7 day')
            """,
            (DEFAULT_USER,),
        ).fetchone()
    weak = weak_topics()
    return {"study_hours": round(review["hours"],2), "discipline_score": round(review["discipline"],2), "weak_chapters": weak[:5]}


@app.get("/strategy")
def strategy_data():
    return strategy_dataframe().to_dict(orient="records")
