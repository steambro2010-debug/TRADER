from datetime import date, datetime, timedelta
import pandas as pd

from database.db import get_connection
from modules.syllabus_data import FULL_JEE_SYLLABUS


def seed_if_empty() -> None:
    with get_connection() as conn:
        user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
        if not user:
            conn.execute("INSERT INTO users(name, exam_year) VALUES(?,?)", ("Aspirant", 2027))
        user_id = conn.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]

        syllabus_count = conn.execute("SELECT COUNT(*) c FROM syllabus").fetchone()["c"]
        if syllabus_count == 0:
            syllabus_rows = [
                {"subject": subject, "chapter": chapter, "total_weight": 1}
                for subject, chapters in FULL_JEE_SYLLABUS.items()
                for chapter in chapters
            ]
            pd.DataFrame(syllabus_rows).to_sql("syllabus", conn, if_exists="append", index=False)
            all_rows = conn.execute("SELECT id FROM syllabus").fetchall()
            for idx, row in enumerate(all_rows):
                completion = round(min(1.0, 0.2 + (idx % 10) * 0.07), 2)
                accuracy = round(min(1.0, 0.35 + (idx % 8) * 0.07), 2)
                confidence = round(min(1.0, 0.4 + (idx % 7) * 0.07), 2)
                conn.execute(
                    """
                    INSERT INTO syllabus_progress(user_id, syllabus_id, completion_status, confidence_score, questions_solved, accuracy, last_revision_date)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (
                        user_id,
                        row["id"],
                        completion,
                        confidence,
                        20 + idx * 3,
                        accuracy,
                        (date.today() - timedelta(days=idx % 6)).isoformat(),
                    ),
                )

        tests_count = conn.execute("SELECT COUNT(*) c FROM mock_tests").fetchone()["c"]
        if tests_count == 0:
            mock_rows = [
                ("Mock 1", "2026-01-05", 62, 71, 55),
                ("Mock 2", "2026-01-12", 68, 74, 58),
                ("Mock 3", "2026-01-19", 72, 76, 63),
                ("Mock 4", "2026-01-26", 78, 80, 69),
            ]
            for name, test_date, p, c, m in mock_rows:
                conn.execute(
                    "INSERT INTO mock_tests(user_id, test_name, test_date, physics_score, chemistry_score, math_score, total_score) VALUES(?,?,?,?,?,?,?)",
                    (user_id, name, test_date, p, c, m, p + c + m),
                )

        sessions_count = conn.execute("SELECT COUNT(*) c FROM study_sessions").fetchone()["c"]
        if sessions_count == 0:
            chapters = [c for vals in FULL_JEE_SYLLABUS.values() for c in vals]
            for i in range(12):
                day = date.today() - timedelta(days=i)
                subject = ["Physics", "Chemistry", "Mathematics"][i % 3]
                chapter = chapters[i % len(chapters)]
                start_dt = datetime.combine(day, datetime.min.time()).replace(hour=6 + (i % 3), minute=0)
                duration = 90 + (i % 4) * 20
                end_dt = start_dt + timedelta(minutes=duration)
                conn.execute(
                    """
                    INSERT INTO study_sessions(user_id, start_time, end_time, subject, chapter, questions_solved, duration_minutes)
                    VALUES(?,?,?,?,?,?,?)
                    """,
                    (user_id, start_dt.isoformat(), end_dt.isoformat(), subject, chapter, 18 + i, duration),
                )

        habits_count = conn.execute("SELECT COUNT(*) c FROM habits").fetchone()["c"]
        if habits_count == 0:
            for i in range(6, -1, -1):
                day = (date.today() - timedelta(days=i)).isoformat()
                vals = (
                    user_id,
                    day,
                    1,
                    1,
                    1 if i % 2 == 0 else 0,
                    1,
                    1,
                    1 if i % 3 != 0 else 0,
                    1,
                    88 - i * 4,
                )
                conn.execute(
                    """
                    INSERT INTO habits(user_id, habit_date, woke_on_time, completed_sessions, no_phone_usage, did_revision, solved_pyq, exercise, slept_on_time, discipline_score)
                    VALUES(?,?,?,?,?,?,?,?,?,?)
                    """,
                    vals,
                )
        conn.commit()
