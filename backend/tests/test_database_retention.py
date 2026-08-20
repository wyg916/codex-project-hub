from __future__ import annotations

from pathlib import Path

from backend.app.db import database as database_module
from backend.app.db.database import Database


def test_database_retains_only_recent_events(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(database_module, "MAX_EVENTS_PER_PROJECT", 3)
    database = Database(tmp_path / "app.db")
    project = database.create_project(
        {
            "name": "retention",
            "repo_path": str(tmp_path),
            "canonical_worktree": str(tmp_path),
            "remote_url": None,
            "git_common_dir": str(tmp_path / ".git"),
            "main_branch": "main",
            "integration_branch": None,
            "rc_branch": None,
            "project_stage": "test",
            "priority": 0,
        }
    )
    for index in range(5):
        database.add_event(
            {
                "project_id": project["id"],
                "branch_name": "main",
                "event_type": "test",
                "severity": "info",
                "title": f"event-{index}",
                "detail": "detail",
                "fingerprint": f"event-{index}",
                "occurred_at": f"2026-08-20T00:00:0{index}+00:00",
            }
        )
    events = database.list_events(project["id"], limit=10)
    assert [event["title"] for event in events] == ["event-4", "event-3", "event-2"]
