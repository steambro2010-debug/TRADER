from __future__ import annotations

import sqlite3
import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


@dataclass(slots=True)
class ActionLog:
    timestamp: str
    intent: str
    risk_level: str
    parameters: Dict[str, Any]
    status: str
    result: str


class MemoryStore:
    """SQLite memory and audit logging for JARVIS."""

    def __init__(self, db_path: str, retention_days: int = 30) -> None:
        self.db_path = Path(db_path)
        self.retention_days = retention_days
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self) -> Iterable[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS action_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    intent TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    parameters_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS kv_memory (
                    key TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def log_action(
        self,
        intent: str,
        risk_level: str,
        parameters: Dict[str, Any],
        status: str,
        result: str,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO action_logs (
                    timestamp, intent, risk_level, parameters_json, status, result
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    datetime.utcnow().isoformat(timespec="seconds"),
                    intent,
                    risk_level,
                    json.dumps(parameters, ensure_ascii=False),
                    status,
                    result,
                ),
            )

    def set_memory(self, key: str, value: Dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat(timespec="seconds")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO kv_memory (key, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (key, json.dumps(value, ensure_ascii=False), now),
            )

    def get_memory(self, key: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT value_json FROM kv_memory WHERE key = ?",
                (key,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["value_json"])

    def recent_actions(self, limit: int = 20) -> list[ActionLog]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT timestamp, intent, risk_level, parameters_json, status, result
                FROM action_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            ActionLog(
                timestamp=r["timestamp"],
                intent=r["intent"],
                risk_level=r["risk_level"],
                parameters=json.loads(r["parameters_json"]),
                status=r["status"],
                result=r["result"],
            )
            for r in rows
        ]

    def cleanup(self) -> int:
        cutoff = (datetime.utcnow() - timedelta(days=self.retention_days)).isoformat(
            timespec="seconds"
        )
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM action_logs WHERE timestamp < ?",
                (cutoff,),
            )
            deleted = cur.rowcount
        return deleted
