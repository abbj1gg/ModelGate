from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import sqlite3

from app.core.config import get_settings


class AuditStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS request_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    error_detail TEXT,
                    key_id TEXT,
                    user_id TEXT,
                    application_id TEXT,
                    latency_ms INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def record(
        self,
        *,
        request_id: str,
        method: str,
        path: str,
        status_code: int,
        latency_ms: int,
        error_detail: str | None = None,
        key_id: str | None = None,
        user_id: str | None = None,
        application_id: str | None = None,
    ) -> None:
        created_at = datetime.now(timezone.utc).isoformat()

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO request_audit_logs (
                    request_id,
                    method,
                    path,
                    status_code,
                    error_detail,
                    key_id,
                    user_id,
                    application_id,
                    latency_ms,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    method,
                    path,
                    status_code,
                    error_detail,
                    key_id,
                    user_id,
                    application_id,
                    latency_ms,
                    created_at,
                ),
            )
            connection.commit()

    def list_recent(
        self,
        *,
        limit: int = 100,
        failures_only: bool = False,
    ) -> list[dict[str, object]]:
        query = """
            SELECT
                request_id,
                method,
                path,
                status_code,
                error_detail,
                key_id,
                user_id,
                application_id,
                latency_ms,
                created_at
            FROM request_audit_logs
        """

        parameters: list[object] = []

        if failures_only:
            query += " WHERE status_code >= 400"

        query += " ORDER BY id DESC LIMIT ?"
        parameters.append(limit)

        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [dict(row) for row in rows]


@lru_cache
def get_audit_store() -> AuditStore:
    settings = get_settings()
    return AuditStore(settings.database_path)