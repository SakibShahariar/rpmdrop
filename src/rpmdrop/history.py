"""Private local history for RpmDrop package transactions."""

from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OperationRecord:
    id: int
    created_at: datetime
    status: str
    packages: tuple[str, ...]
    details: str


class HistoryStore:
    """Store a small, private record of recent package operations."""

    def __init__(self, database_path: str | Path | None = None):
        if database_path is None:
            data_home = Path(
                os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
            )
            database_path = data_home / "rpmdrop" / "history.sqlite3"
        self.path = Path(database_path).expanduser()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            self.path.parent.chmod(0o700)
        except OSError:
            pass
        if not self.path.exists():
            self.path.touch(mode=0o600)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
        connection = sqlite3.connect(self.path)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                packages_json TEXT NOT NULL,
                details TEXT NOT NULL DEFAULT ''
            )
            """
        )
        connection.commit()
        return connection

    def record(
        self,
        status: str,
        packages: tuple[str, ...] | list[str],
        details: str = "",
    ) -> None:
        if status not in {"success", "failed", "cancelled"}:
            raise ValueError(f"Unsupported operation status: {status}")
        package_list = tuple(str(package) for package in packages)
        with closing(self._connect()) as connection, connection:
            connection.execute(
                """
                INSERT INTO operations (created_at, status, packages_json, details)
                VALUES (?, ?, ?, ?)
                """,
                (
                    datetime.now(UTC).isoformat(),
                    status,
                    json.dumps(package_list, ensure_ascii=False),
                    details[:4000],
                ),
            )
            connection.execute(
                """
                DELETE FROM operations
                WHERE id NOT IN (
                    SELECT id FROM operations ORDER BY id DESC LIMIT 100
                )
                """
            )

    def list_recent(self, limit: int = 50) -> tuple[OperationRecord, ...]:
        bounded_limit = max(1, min(int(limit), 100))
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT id, created_at, status, packages_json, details
                FROM operations
                ORDER BY id DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        records = []
        for row_id, timestamp, status, packages_json, details in rows:
            records.append(
                OperationRecord(
                    id=int(row_id),
                    created_at=datetime.fromisoformat(timestamp),
                    status=str(status),
                    packages=tuple(json.loads(packages_json)),
                    details=str(details),
                )
            )
        return tuple(records)
