from datetime import date
from database.db import get_connection


def generate_daily_plan(user_id: int, available_hours: float) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM daily_plan WHERE user_id=? AND plan_date=?", (user_id, date.today().isoformat()))

        weak_rows = conn.execute(
            """
            SELECT s.subject, s.chapter, sp.accuracy, sp.confidence_score
            FROM syllabus_progress sp
            JOIN syllabus s ON sp.syllabus_id=s.id
            WHERE sp.user_id=?
            ORDER BY (sp.accuracy + sp.confidence_score) ASC
            LIMIT 6
            """,
            (user_id,),
        ).fetchall()

        blocks = ["Deep Study 1", "Deep Study 2", "Deep Study 3"]
        task_types = ["theory", "practice", "revision", "PYQ"]
        per_block = max(1, int((available_hours * 60) / len(blocks)))

        for i, block in enumerate(blocks):
            row = weak_rows[i % len(weak_rows)] if weak_rows else {"subject": "Physics", "chapter": "Kinematics"}
            task_type = task_types[i % len(task_types)]
            target = f"{per_block} min / {15 + i * 5} questions"
            conn.execute(
                """
                INSERT INTO daily_plan(user_id, plan_date, task, subject, chapter, task_type, target, completed)
                VALUES(?,?,?,?,?,?,?,0)
                """,
                (user_id, date.today().isoformat(), block, row["subject"], row["chapter"], task_type, target),
            )

        routine = [
            "Wake: 5:30 AM", "School", "Revision", "Sleep: 10:30 PM"
        ]
        for item in routine:
            conn.execute(
                "INSERT INTO daily_plan(user_id, plan_date, task, completed) VALUES(?,?,?,0)",
                (user_id, date.today().isoformat(), item),
            )
        conn.commit()
