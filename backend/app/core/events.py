from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


class EventService:
    def compare(self, project_id: int, previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        old_branches = {item["name"]: item for item in (previous or {}).get("branches", [])}
        old_worktrees = {item["path"]: item for item in (previous or {}).get("worktrees", [])}
        for worktree in current.get("worktrees", []):
            old_worktree = old_worktrees.get(worktree["path"])
            if previous is not None and old_worktree is None:
                events.append(self._make(project_id, worktree.get("branch") or "", "worktree.created", "info", "发现新 Worktree", worktree["path"]))
            elif old_worktree is not None:
                old_dirty = self._dirty(old_worktree)
                new_dirty = self._dirty(worktree)
                if old_dirty != new_dirty:
                    branch = worktree.get("branch") or "DETACHED"
                    severity = "attention" if new_dirty else "info"
                    events.append(
                        self._make(
                            project_id,
                            branch,
                            "worktree.changed",
                            severity,
                            f"{branch} 工作区状态变化",
                            str(new_dirty),
                        )
                    )
        for branch in current.get("branches", []):
            name = branch["name"]
            old = old_branches.get(name)
            if old is None:
                events.append(self._make(project_id, name, "branch.created", "info", f"发现分支 {name}", branch["head_sha"]))
                continue
            if old.get("head_sha") != branch.get("head_sha"):
                events.append(self._make(project_id, name, "head.changed", "info", f"{name} HEAD 已更新", branch["head_sha"]))
            if not old.get("is_merged_to_main") and branch.get("is_merged_to_main"):
                events.append(self._make(project_id, name, "branch.merged", "info", f"{name} 已合并到主分支", branch["head_sha"]))
        old_tasks = (previous or {}).get("metadata_summary", {})
        for name, task in current.get("metadata_summary", {}).items():
            old_task = old_tasks.get(name, {})
            if old_task and old_task.get("status") != task.get("status"):
                events.append(self._make(project_id, name, "task.updated", "info", f"{name} 任务状态变化", str(task.get("status"))))
            if old_task and old_task.get("tests") != task.get("tests"):
                events.append(self._make(project_id, name, "tests.updated", "info", f"{name} 测试状态变化", str(task.get("tests"))))
        return events

    @staticmethod
    def _dirty(branch: dict[str, Any]) -> int:
        return sum(branch.get(key, 0) for key in ("modified_count", "added_count", "deleted_count", "untracked_count", "conflict_count"))

    @staticmethod
    def _make(project_id: int, branch: str, event_type: str, severity: str, title: str, detail: str) -> dict[str, Any]:
        occurred = datetime.now(timezone.utc).isoformat()
        digest = uuid.uuid4().hex[:24]
        return {
            "project_id": project_id,
            "branch_name": branch,
            "event_type": event_type,
            "severity": severity,
            "title": title,
            "detail": detail,
            "fingerprint": digest,
            "occurred_at": occurred,
        }
