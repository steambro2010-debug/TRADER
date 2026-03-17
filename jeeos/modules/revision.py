from datetime import date, timedelta
from database.db import get_connection

INTERVALS = [1, 3, 7, 21, 60]


def schedule_revision(user_id: int, chapter: str, base_date: date | None = None) -> None:
    base = base_date or date.today()
    with get_connection() as conn:
        for interval in INTERVALS:
            due = base + timedelta(days=interval)
            conn.execute(
                "INSERT INTO revision_schedule(user_id, chapter, due_date, interval_day, completed) VALUES(?,?,?,?,0)",
                (user_id, chapter, due.isoformat(), interval),
            )
        conn.commit()
