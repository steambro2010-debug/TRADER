from datetime import date, datetime, timedelta
import pandas as pd

from database.db import get_connection
from modules.syllabus_data import FULL_JEE_SYLLABUS


DEFAULT_CONFIG = {
    "first_time_setup_done": "0",
    "demo_mode": "1",
}


def _get_or_create_user(conn) -> int:
    user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()
    if not user:
        conn.execute("INSERT INTO users(name, exam_year) VALUES(?,?)", ("Aspirant", 2027))
    return conn.execute("SELECT id FROM users LIMIT 1").fetchone()["id"]


def ensure_config() -> None:
    with get_connection() as conn:
        for key, value in DEFAULT_CONFIG.items():
            conn.execute("INSERT OR IGNORE INTO app_config(key, value) VALUES(?,?)", (key, value))
        conn.commit()


def get_config() -> dict:
    ensure_config()
    with get_connection() as conn:
        rows = conn.execute("SELECT key, value FROM app_config").fetchall()
    return {row["key"]: row["value"] for row in rows}


def set_config(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute("INSERT INTO app_config(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        conn.commit()


def ensure_syllabus_catalog_and_progress(user_id: int, reset_progress: bool = False) -> None:
    with get_connection() as conn:
        syllabus_count = conn.execute("SELECT COUNT(*) c FROM syllabus").fetchone()["c"]
        if syllabus_count == 0:
            rows = [{"subject": s, "chapter": c, "total_weight": 1} for s, chs in FULL_JEE_SYLLABUS.items() for c in chs]
            pd.DataFrame(rows).to_sql("syllabus", conn, if_exists="append", index=False)

        existing = conn.execute("SELECT COUNT(*) c FROM syllabus_progress WHERE user_id=?", (user_id,)).fetchone()["c"]
        if existing == 0:
            conn.execute(
                """
                INSERT INTO syllabus_progress(user_id, syllabus_id, completion_status, confidence_score, questions_solved, accuracy, last_revision_date)
                SELECT ?, id, 0, 0, 0, 0, NULL FROM syllabus
                """,
                (user_id,),
            )

        if reset_progress:
            conn.execute(
                "UPDATE syllabus_progress SET completion_status=0, confidence_score=0, questions_solved=0, accuracy=0, last_revision_date=NULL WHERE user_id=?",
                (user_id,),
            )
        conn.commit()


def clear_user_tracking_data(user_id: int) -> None:
    with get_connection() as conn:
        for table in [
            "study_sessions", "mock_tests", "question_attempts", "mistake_log", "revision_schedule", "daily_plan", "habits", "analytics"
        ]:
            conn.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
        conn.commit()


def load_demo_data(user_id: int, force_clear: bool = False) -> None:
    ensure_syllabus_catalog_and_progress(user_id=user_id, reset_progress=False)
    with get_connection() as conn:
        if force_clear:
            conn.execute("DELETE FROM study_sessions WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM mock_tests WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM habits WHERE user_id=?", (user_id,))

        # syllabus demo progress
        rows = conn.execute("SELECT id FROM syllabus ORDER BY id").fetchall()
        for idx, row in enumerate(rows):
            completion = round(min(1.0, 0.2 + (idx % 10) * 0.07), 2)
            accuracy = round(min(1.0, 0.35 + (idx % 8) * 0.07), 2)
            confidence = round(min(1.0, 0.4 + (idx % 7) * 0.07), 2)
            conn.execute(
                """
                UPDATE syllabus_progress
                SET completion_status=?, confidence_score=?, questions_solved=?, accuracy=?, last_revision_date=?
                WHERE user_id=? AND syllabus_id=?
                """,
                (completion, confidence, 20 + idx * 3, accuracy, (date.today() - timedelta(days=idx % 6)).isoformat(), user_id, row["id"]),
            )

        tests_count = conn.execute("SELECT COUNT(*) c FROM mock_tests WHERE user_id=?", (user_id,)).fetchone()["c"]
        if tests_count == 0:
            for name, test_date, p, c, m in [
                ("Mock 1", "2026-01-05", 62, 71, 55),
                ("Mock 2", "2026-01-12", 68, 74, 58),
                ("Mock 3", "2026-01-19", 72, 76, 63),
                ("Mock 4", "2026-01-26", 78, 80, 69),
            ]:
                conn.execute(
                    "INSERT INTO mock_tests(user_id, test_name, test_date, physics_score, chemistry_score, math_score, total_score) VALUES(?,?,?,?,?,?,?)",
                    (user_id, name, test_date, p, c, m, p + c + m),
                )

        sessions_count = conn.execute("SELECT COUNT(*) c FROM study_sessions WHERE user_id=?", (user_id,)).fetchone()["c"]
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
                    "INSERT INTO study_sessions(user_id, start_time, end_time, subject, chapter, questions_solved, duration_minutes) VALUES(?,?,?,?,?,?,?)",
                    (user_id, start_dt.isoformat(), end_dt.isoformat(), subject, chapter, 18 + i, duration),
                )

        habits_count = conn.execute("SELECT COUNT(*) c FROM habits WHERE user_id=?", (user_id,)).fetchone()["c"]
        if habits_count == 0:
            for i in range(6, -1, -1):
                day = (date.today() - timedelta(days=i)).isoformat()
                conn.execute(
                    "INSERT INTO habits(user_id, habit_date, woke_on_time, completed_sessions, no_phone_usage, did_revision, solved_pyq, exercise, slept_on_time, discipline_score) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (user_id, day, 1, 1, 1 if i % 2 == 0 else 0, 1, 1, 1 if i % 3 != 0 else 0, 1, 88 - i * 4),
                )
        conn.commit()


def start_fresh(user_id: int) -> None:
    clear_user_tracking_data(user_id)
    ensure_syllabus_catalog_and_progress(user_id=user_id, reset_progress=True)
    set_config("demo_mode", "0")
    set_config("first_time_setup_done", "1")


def reset_all_data(user_id: int) -> None:
    clear_user_tracking_data(user_id)
    ensure_syllabus_catalog_and_progress(user_id=user_id, reset_progress=True)


def seed_if_empty() -> None:
    ensure_config()
    with get_connection() as conn:
        user_id = _get_or_create_user(conn)
        conn.commit()

    ensure_syllabus_catalog_and_progress(user_id=user_id)
    cfg = get_config()
    if cfg.get("demo_mode", "1") == "1":
        load_demo_data(user_id=user_id, force_clear=False)
