from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import sqlite3
from app.core.config import get_settings

class QuotaStore:
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
                CREATE TABLE IF NOT EXISTS api_key_quotas (
                    key_id TEXT PRIMARY KEY,
                    monthly_token_limit INTEGER NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def set_monthly_limit(
        self,
        *,
        key_id: str,
        monthly_token_limit: int,
    ) -> None:
        if monthly_token_limit <= 0:
            raise ValueError("monthly_token_limit must be positive")
        updated_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO api_key_quotas (
                    key_id,
                    monthly_token_limit,
                    updated_at
                )
                VALUES (?, ?, ?)
                ON CONFLICT(key_id) DO UPDATE SET
                    monthly_token_limit = excluded.monthly_token_limit,
                    updated_at = excluded.updated_at
                """,
                (
                    key_id,
                    monthly_token_limit,
                    updated_at,
                ),
            )
            connection.commit()

    def get_monthly_limit(self, key_id: str) -> int | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT monthly_token_limit
                FROM api_key_quotas
                WHERE key_id = ?
                """,
                (key_id,),
            ).fetchone()
        if row is None:
            return None
        return int(row["monthly_token_limit"])

    def get_current_month_usage(self, key_id: str) -> int:
        now = datetime.now(timezone.utc)
        month_start = now.replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        with self._connect() as connection:
            table_exists = connection.execute(
                """
                SELECT 1
                FROM sqlite_master
                WHERE type = 'table'
                  AND name = 'llm_usage_logs'
                """
            ).fetchone()
            if table_exists is None:
                return 0
            row = connection.execute(
                """
                SELECT COALESCE(SUM(total_tokens), 0) AS total_tokens
                FROM llm_usage_logs
                WHERE key_id = ?
                  AND status_code >= 200
                  AND status_code < 300
                  AND created_at >= ?
                """,
                (
                    key_id,
                    month_start.isoformat(),
                ),
            ).fetchone()
        return int(row["total_tokens"])

    def get_snapshot(self, key_id: str) -> dict[str, object]:
        monthly_limit = self.get_monthly_limit(key_id)
        used_tokens = self.get_current_month_usage(key_id)
        if monthly_limit is None:
            return {
                "key_id": key_id,
                "monthly_limit": None,
                "used_tokens": used_tokens,
                "remaining_tokens": None,
                "unlimited": True,
            }
        return {
            "key_id": key_id,
            "monthly_limit": monthly_limit,
            "used_tokens": used_tokens,
            "remaining_tokens": max(monthly_limit - used_tokens, 0),
            "unlimited": False,
        }

@lru_cache
def get_quota_store() -> QuotaStore:
    settings = get_settings()
    return QuotaStore(settings.database_path)
