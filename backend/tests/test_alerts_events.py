from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.app.core.alerts import AlertService
from backend.app.core.events import EventService


def test_all_advanced_alert_rules(tmp_path: Path) -> None:
    old = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    recent = datetime.now(timezone.utc).isoformat()
    project = {"canonical_worktree": str(tmp_path), "rc_branch": "release/rc"}
    snapshot = {
        "worktrees": [],
        "branches": [
            {"name": "feat/a", "head_time": recent, "changed_files": ["src/key.py"], "worktree_path": str(tmp_path / "a"), "modified_count": 1, "added_count": 0, "deleted_count": 0, "untracked_count": 0, "conflict_count": 0, "behind": 0, "status": "active", "is_merged_to_main": False},
            {"name": "fix/b", "head_time": recent, "changed_files": ["src/key.py"], "worktree_path": str(tmp_path / "b"), "modified_count": 1, "added_count": 0, "deleted_count": 0, "untracked_count": 0, "conflict_count": 0, "behind": 0, "status": "active", "is_merged_to_main": False},
        ],
    }
    metadata = {
        "data": {"branches": {
            "feat/a": {"branch_type": "rc", "status": "active", "result": "UNKNOWN", "updated_at": old},
            "fix/b": {"branch_type": "rc", "status": "active", "result": "UNKNOWN", "updated_at": recent},
        }},
        "error": None,
    }
    types = {item["alert_type"] for item in AlertService().build(project, snapshot, metadata)}
    assert {"multiple_rc", "metadata_stale", "cross_worktree_file", "dirty_worktree"} <= types


def test_worktree_task_test_and_merge_events() -> None:
    old = {
        "worktrees": [{"path": "A", "branch": "main"}],
        "branches": [{"name": "feat/a", "head_sha": "1", "modified_count": 0, "added_count": 0, "deleted_count": 0, "untracked_count": 0, "conflict_count": 0, "is_merged_to_main": False}],
        "metadata_summary": {"feat/a": {"status": "active", "tests": {"unit": "NOT_RUN"}}},
    }
    current = {
        "worktrees": [{"path": "A", "branch": "main"}, {"path": "B", "branch": "feat/a"}],
        "branches": [{"name": "feat/a", "head_sha": "1", "modified_count": 0, "added_count": 0, "deleted_count": 0, "untracked_count": 0, "conflict_count": 0, "is_merged_to_main": True}],
        "metadata_summary": {"feat/a": {"status": "validating", "tests": {"unit": "PASS"}}},
    }
    types = {item["event_type"] for item in EventService().compare(1, old, current)}
    assert {"worktree.created", "branch.merged", "task.updated", "tests.updated"} <= types


def test_repeated_state_transition_receives_a_new_event_fingerprint() -> None:
    service = EventService()
    first = service._make(1, "feat/a", "worktree.changed", "attention", "changed", "1")
    second = service._make(1, "feat/a", "worktree.changed", "attention", "changed", "1")

    assert first["fingerprint"] != second["fingerprint"]
