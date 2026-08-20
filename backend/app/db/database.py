from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAX_EVENTS_PER_PROJECT = 2000


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, check_same_thread=False, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize(self) -> None:
        with self._lock, self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    repo_path TEXT NOT NULL,
                    canonical_worktree TEXT NOT NULL,
                    remote_url TEXT,
                    git_common_dir TEXT NOT NULL,
                    main_branch TEXT NOT NULL,
                    integration_branch TEXT,
                    rc_branch TEXT,
                    project_stage TEXT NOT NULL DEFAULT '未维护',
                    priority INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_scan_at TEXT,
                    scan_status TEXT NOT NULL DEFAULT 'pending',
                    UNIQUE(git_common_dir)
                );
                CREATE TABLE IF NOT EXISTS snapshots (
                    project_id INTEGER PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id INTEGER NOT NULL,
                    branch_name TEXT,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, fingerprint),
                    FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE
                );
                """
            )

    def list_projects(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute("SELECT * FROM projects ORDER BY priority DESC, updated_at DESC").fetchall()
        return [dict(row) for row in rows]

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None

    def create_project(self, values: dict[str, Any]) -> dict[str, Any]:
        now = utc_now()
        columns = [
            "name", "repo_path", "canonical_worktree", "remote_url", "git_common_dir", "main_branch",
            "integration_branch", "rc_branch", "project_stage", "priority", "created_at", "updated_at",
        ]
        payload = {**values, "created_at": now, "updated_at": now}
        with self._lock, self.connect() as connection:
            cursor = connection.execute(
                f"INSERT INTO projects ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                tuple(payload.get(column) for column in columns),
            )
            project_id = int(cursor.lastrowid)
        return self.get_project(project_id) or {}

    def update_project(self, project_id: int, values: dict[str, Any]) -> dict[str, Any] | None:
        allowed = {"name", "canonical_worktree", "main_branch", "integration_branch", "rc_branch", "project_stage", "priority", "last_scan_at", "scan_status", "remote_url", "repo_path", "git_common_dir"}
        updates = {key: value for key, value in values.items() if key in allowed}
        if not updates:
            return self.get_project(project_id)
        updates["updated_at"] = utc_now()
        assignments = ", ".join(f"{column} = ?" for column in updates)
        with self._lock, self.connect() as connection:
            connection.execute(
                f"UPDATE projects SET {assignments} WHERE id = ?",
                (*updates.values(), project_id),
            )
        return self.get_project(project_id)

    def delete_project(self, project_id: int) -> bool:
        with self._lock, self.connect() as connection:
            cursor = connection.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        return cursor.rowcount > 0

    def save_snapshot(self, project_id: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False)
        with self._lock, self.connect() as connection:
            connection.execute(
                """INSERT INTO snapshots(project_id, payload, updated_at) VALUES(?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at""",
                (project_id, encoded, utc_now()),
            )

    def get_snapshot(self, project_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute("SELECT payload FROM snapshots WHERE project_id = ?", (project_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def add_event(self, event: dict[str, Any]) -> bool:
        with self._lock, self.connect() as connection:
            cursor = connection.execute(
                """INSERT OR IGNORE INTO events
                (project_id, branch_name, event_type, severity, title, detail, fingerprint, occurred_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event["project_id"], event.get("branch_name"), event["event_type"], event["severity"],
                    event["title"], event["detail"], event["fingerprint"], event["occurred_at"], utc_now(),
                ),
            )
            connection.execute(
                """DELETE FROM events
                WHERE project_id = ? AND id NOT IN (
                    SELECT id FROM events WHERE project_id = ?
                    ORDER BY occurred_at DESC, id DESC LIMIT ?
                )""",
                (event["project_id"], event["project_id"], MAX_EVENTS_PER_PROJECT),
            )
        return cursor.rowcount > 0

    def list_events(self, project_id: int, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM events WHERE project_id = ? ORDER BY occurred_at DESC, id DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]
