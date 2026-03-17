from datetime import date, timedelta
import pandas as pd
from sklearn.linear_model import LinearRegression
from database.db import get_connection


def dashboard_metrics(user_id: int) -> dict:
    with get_connection() as conn:
        today = date.today().isoformat()
        start_week = (date.today() - timedelta(days=6)).isoformat()

        today_minutes = conn.execute(
            "SELECT COALESCE(SUM(duration_minutes),0) val FROM study_sessions WHERE user_id=? AND date(start_time)=?",
            (user_id, today),
        ).fetchone()["val"]

        syllabus_stats = conn.execute(
            "SELECT AVG(completion_status) completion, AVG(accuracy) acc FROM syllabus_progress WHERE user_id=?",
            (user_id,),
        ).fetchone()

        streak = conn.execute(
            "SELECT COUNT(*) c FROM habits WHERE user_id=? AND discipline_score>=70 AND habit_date>=?",
            (user_id, start_week),
        ).fetchone()["c"]

        mock_avg = conn.execute(
            "SELECT COALESCE(AVG(total_score),0) v FROM mock_tests WHERE user_id=?",
            (user_id,),
        ).fetchone()["v"]

        weak = conn.execute(
            """
            SELECT s.chapter FROM syllabus_progress sp JOIN syllabus s ON sp.syllabus_id=s.id
            WHERE sp.user_id=? ORDER BY (sp.accuracy + sp.confidence_score) ASC LIMIT 3
            """,
            (user_id,),
        ).fetchall()

        revision = conn.execute(
            "SELECT COUNT(*) c FROM revision_schedule WHERE user_id=? AND due_date<=? AND completed=0",
            (user_id, today),
        ).fetchone()["c"]

        backlog = conn.execute(
            "SELECT COUNT(*) c FROM daily_plan WHERE user_id=? AND completed=0 AND plan_date<?",
            (user_id, today),
        ).fetchone()["c"]

    return {
        "today_hours": round(today_minutes / 60, 2),
        "syllabus_completion": round((syllabus_stats["completion"] or 0) * 100, 1),
        "mock_avg": round(mock_avg, 1),
        "streak": streak,
        "weakest_chapters": [w["chapter"] for w in weak],
        "revision_tasks": revision,
        "backlog_tasks": backlog,
    }


def rank_prediction(user_id: int) -> dict:
    with get_connection() as conn:
        tests = pd.read_sql_query(
            "SELECT physics_score, chemistry_score, math_score, total_score FROM mock_tests WHERE user_id=?",
            conn,
            params=(user_id,),
        )
        hours = pd.read_sql_query(
            "SELECT date(start_time) d, SUM(duration_minutes)/60 h FROM study_sessions WHERE user_id=? GROUP BY d",
            conn,
            params=(user_id,),
        )

    if tests.empty:
        return {"percentile": 80.0, "advanced_rank": 25000}

    tests["accuracy_proxy"] = tests["total_score"] / 300
    mean_hours = hours["h"].mean() if not hours.empty else 4.0
    tests["study_hours"] = mean_hours

    X = tests[["total_score", "accuracy_proxy", "study_hours"]].values
    y = 70 + (tests["total_score"] / 300) * 30
    model = LinearRegression().fit(X, y)
    pred = model.predict([[tests["total_score"].iloc[-1], tests["accuracy_proxy"].iloc[-1], mean_hours]])[0]
    percentile = float(max(1, min(99.9, pred)))
    adv_rank = int((100 - percentile) * 1200)
    return {"percentile": round(percentile, 2), "advanced_rank": max(1, adv_rank)}
