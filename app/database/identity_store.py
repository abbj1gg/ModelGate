import json
import sqlite3
from pathlib import Path
from typing import Any
import hashlib
import secrets
from uuid import uuid4

class IdentityStore:
    def __init__(
        self,
        *,
        database_path: str,
        dev_key_hash: str,
        gateway_model_id: str,
    ) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        self._initialize()
        self._seed_development_identity(
            dev_key_hash=dev_key_hash,
            gateway_model_id=gateway_model_id,
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        connection = self._connect()

        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL DEFAULT 'active'
                );

                CREATE TABLE IF NOT EXISTS applications (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS api_keys (
                    id TEXT PRIMARY KEY,
                    key_hash TEXT NOT NULL UNIQUE,
                    user_id TEXT NOT NULL,
                    application_id TEXT NOT NULL,
                    allowed_models TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    FOREIGN KEY (user_id) REFERENCES users(id),
                    FOREIGN KEY (application_id) REFERENCES applications(id)
                );
                """
            )
            connection.commit()
        finally:
            connection.close()

    def _seed_development_identity(
        self,
        *,
        dev_key_hash: str,
        gateway_model_id: str,
    ) -> None:
        connection = self._connect()

        try:
            connection.execute(
                """
                INSERT OR IGNORE INTO users (id, username, status)
                VALUES (?, ?, ?)
                """,
                ("user-local", "local-user", "active"),
            )

            connection.execute(
                """
                INSERT OR IGNORE INTO applications
                    (id, name, user_id, status)
                VALUES (?, ?, ?, ?)
                """,
                (
                    "app-local",
                    "local-development-app",
                    "user-local",
                    "active",
                ),
            )

            allowed_models = json.dumps(
                ["demo-chat", gateway_model_id]
            )

            connection.execute(
                """
                INSERT OR IGNORE INTO api_keys
                    (id, key_hash, user_id, application_id,
                     allowed_models, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "key-development",
                    dev_key_hash,
                    "user-local",
                    "app-local",
                    allowed_models,
                    "active",
                ),
            )

            connection.commit()
        finally:
            connection.close()


    def create_user(self, username: str) -> dict[str, str]:
        user_id = f"user-{uuid4().hex[:12]}"

        connection = self._connect()

        try:
            connection.execute(
                """
                INSERT INTO users (id, username, status)
                VALUES (?, ?, ?)
                """,
                (user_id, username, "active"),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("username already exists") from exc
        finally:
            connection.close()

        return {
            "id": user_id,
            "username": username,
            "status": "active",
        }

    def create_application(
        self,
        *,
        name: str,
        user_id: str,
    ) -> dict[str, str]:
        application_id = f"app-{uuid4().hex[:12]}"

        connection = self._connect()

        try:
            user = connection.execute(
                """
                SELECT id
                FROM users
                WHERE id = ? AND status = 'active'
                """,
                (user_id,),
            ).fetchone()

            if user is None:
                raise ValueError("user does not exist")

            connection.execute(
                """
                INSERT INTO applications
                    (id, name, user_id, status)
                VALUES (?, ?, ?, ?)
                """,
                (
                    application_id,
                    name,
                    user_id,
                    "active",
                ),
            )
            connection.commit()
        except sqlite3.IntegrityError as exc:
            raise ValueError("application could not be created") from exc
        finally:
            connection.close()

        return {
            "id": application_id,
            "name": name,
            "user_id": user_id,
            "status": "active",
        }

    def create_api_key(
        self,
        *,
        user_id: str,
        application_id: str,
        allowed_models: list[str],
    ) -> dict[str, object]:
        key_id = f"key-{uuid4().hex[:12]}"
        raw_key = f"mg_live_{secrets.token_urlsafe(24)}"
        key_hash = hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()

        models = sorted(set(allowed_models))

        if not models:
            raise ValueError("at least one model is required")

        connection = self._connect()

        try:
            application = connection.execute(
                """
                SELECT id
                FROM applications
                WHERE id = ?
                  AND user_id = ?
                  AND status = 'active'
                """,
                (application_id, user_id),
            ).fetchone()

            if application is None:
                raise ValueError(
                    "application does not belong to the user"
                )

            connection.execute(
                """
                INSERT INTO api_keys
                    (id, key_hash, user_id, application_id,
                     allowed_models, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    key_id,
                    key_hash,
                    user_id,
                    application_id,
                    json.dumps(models),
                    "active",
                ),
            )
            connection.commit()
        finally:
            connection.close()

        return {
            "id": key_id,
            "api_key": raw_key,
            "user_id": user_id,
            "application_id": application_id,
            "allowed_models": models,
            "status": "active",
        }
 
    def find_by_key_hash(self, key_hash: str) -> dict[str, Any] | None:
        connection = self._connect()

        try:
            row = connection.execute(
                """
                SELECT
                    api_keys.id AS key_id,
                    api_keys.user_id,
                    api_keys.application_id,
                    api_keys.allowed_models,
                    users.username
                FROM api_keys
                JOIN users ON users.id = api_keys.user_id
                JOIN applications
                    ON applications.id = api_keys.application_id
                WHERE api_keys.key_hash = ?
                  AND api_keys.status = 'active'
                  AND users.status = 'active'
                  AND applications.status = 'active'
                """,
                (key_hash,),
            ).fetchone()

            return dict(row) if row else None
        finally:
            connection.close()

    def disable_api_key(self, key_id: str) -> dict[str, str]:
        connection = self._connect()

        try:
            cursor = connection.execute(
                """
                UPDATE api_keys
                SET status = 'disabled'
                WHERE id = ?
                  AND status = 'active'
                """,
                (key_id,),
            )

            if cursor.rowcount == 0:
                raise ValueError(
                    "api key does not exist or is inactive"
                )

            connection.commit()
        finally:
            connection.close()

        return {
            "id": key_id,
            "status": "disabled",
        }

    def rotate_api_key(self, key_id: str) -> dict[str, object]:
        raw_key = f"mg_live_{secrets.token_urlsafe(24)}"
        key_hash = hashlib.sha256(
            raw_key.encode("utf-8")
        ).hexdigest()

        connection = self._connect()

        try:
            row = connection.execute(
                """
                SELECT
                    user_id,
                    application_id,
                    allowed_models
                FROM api_keys
                WHERE id = ?
                  AND status = 'active'
                """,
                (key_id,),
            ).fetchone()

            if row is None:
                raise ValueError(
                    "api key does not exist or is inactive"
                )

            connection.execute(
                """
                UPDATE api_keys
                SET key_hash = ?
                WHERE id = ?
                  AND status = 'active'
                """,
                (key_hash, key_id),
            )

            connection.commit()
        finally:
            connection.close()

        return {
            "id": key_id,
            "api_key": raw_key,
            "user_id": row["user_id"],
            "application_id": row["application_id"],
            "allowed_models": json.loads(row["allowed_models"]),
            "status": "active",
        }