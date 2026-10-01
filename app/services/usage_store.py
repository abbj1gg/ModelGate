from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import sqlite3
from app.core.config import get_settings

class UsageStore:
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
                CREATE TABLE IF NOT EXISTS llm_usage_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_id TEXT NOT NULL,
                    key_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    application_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    prompt_tokens INTEGER NOT NULL DEFAULT 0,
                    completion_tokens INTEGER NOT NULL DEFAULT 0,
                    total_tokens INTEGER NOT NULL DEFAULT 0,
                    latency_ms INTEGER NOT NULL DEFAULT 0,
                    status_code INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def record(
        self,
        *,
        request_id: str,
        key_id: str,
        user_id: str,
        application_id: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        latency_ms: int,
        status_code: int,
    ) -> None:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO llm_usage_logs (
                    request_id,
                    key_id,
                    user_id,
                    application_id,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    latency_ms,
                    status_code,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    request_id,
                    key_id,
                    user_id,
                    application_id,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    latency_ms,
                    status_code,
                    created_at,
                ),
            )
            connection.commit()

    def list_recent(self, limit: int = 100) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    request_id,
                    key_id,
                    user_id,
                    application_id,
                    model,
                    prompt_tokens,
                    completion_tokens,
                    total_tokens,
                    latency_ms,
                    status_code,
                    created_at
                FROM llm_usage_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    # ========== 新增 summarize 汇总方法 ==========
    def summarize(self) -> list[dict[str, object]]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    user_id,
                    application_id,
                    model,
                    COUNT(*) AS request_count,
                    COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    COALESCE(AVG(latency_ms), 0) AS average_latency_ms,
                    SUM(
                        CASE
                            WHEN status_code >= 200
                             AND status_code < 400
                            THEN 1
                            ELSE 0
                        END
                    ) AS success_count,
                    SUM(
                        CASE
                            WHEN status_code >= 400
                            THEN 1
                            ELSE 0
                        END
                    ) AS failure_count
                FROM llm_usage_logs
                GROUP BY user_id, application_id, model
                ORDER BY request_count DESC
                """
            ).fetchall()
        return [dict(row) for row in rows]
    # ===========================================

@lru_cache
def get_usage_store() -> UsageStore:
    settings = get_settings()
    return UsageStore(settings.database_path)
