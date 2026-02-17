from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any


class MemoryStore:
    def __init__(self, db_path: str = "jarvis_memory.db") -> None:
        self._path = Path(db_path)
        self._conn = sqlite3.connect(self._path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts REAL NOT NULL,
                kind TEXT NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def add_event(self, kind: str, payload: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO events(ts, kind, payload) VALUES(?,?,?)",
            (time.time(), kind, json.dumps(payload)),
        )
        self._conn.commit()

    def recent_events(self, limit: int = 30) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT ts, kind, payload FROM events ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        output: list[dict[str, Any]] = []
        for ts, kind, payload in rows:
            output.append({"ts": ts, "kind": kind, "payload": json.loads(payload)})
        return output

    def close(self) -> None:
        self._conn.close()
