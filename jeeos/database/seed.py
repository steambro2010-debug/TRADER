from datetime import date, timedelta
from pathlib import Path
import pandas as pd

from database.db import get_connection

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


def seed_if_empty() -> None:
    with get_connection() as conn:
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if not user:
            conn.execute("INSERT INTO users(name, exam_year) VALUES(?,?)", ("Aspirant", 2027))
        user_id = conn.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]

        syllabus_count = conn.execute("SELECT COUNT(*) c FROM syllabus").fetchone()["c"]
        if syllabus_count == 0:
            df = pd.read_csv(DATA_DIR / "syllabus_sample.csv")
            df.to_sql("syllabus", conn, if_exists="append", index=False)
            conn.execute(
                """
                INSERT INTO syllabus_progress(user_id, syllabus_id, completion_status, confidence_score, questions_solved, accuracy, last_revision_date)
                SELECT ?, id, 0, 0.4, 0, 0.0, ? FROM syllabus
                """,
                (user_id, date.today().isoformat()),
            )

        tests_count = conn.execute("SELECT COUNT(*) c FROM mock_tests").fetchone()["c"]
        if tests_count == 0:
            tests = pd.read_csv(DATA_DIR / "mock_tests_sample.csv")
            tests["user_id"] = user_id
            tests["total_score"] = tests[["physics_score", "chemistry_score", "math_score"]].sum(axis=1)
            tests.to_sql("mock_tests", conn, if_exists="append", index=False)

        habits_count = conn.execute("SELECT COUNT(*) c FROM habits").fetchone()["c"]
        if habits_count == 0:
            for i in range(6, -1, -1):
                day = (date.today() - timedelta(days=i)).isoformat()
                vals = (user_id, day, 1, 1, 1 if i % 2 == 0 else 0, 1, 1, 1, 1, 85 - i * 3)
                conn.execute(
                    """
                    INSERT INTO habits(user_id, habit_date, woke_on_time, completed_sessions, no_phone_usage, did_revision, solved_pyq, exercise, slept_on_time, discipline_score)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    vals,
                )
        conn.commit()
