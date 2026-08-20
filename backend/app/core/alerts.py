from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class AlertService:
    def build(self, project: dict[str, Any], snapshot: dict[str, Any], metadata: dict[str, Any]) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []
        if not Path(project["canonical_worktree"]).exists():
            alerts.append(self._alert("canonical_missing", "blocking", "主项目目录不存在"))
        for worktree in snapshot.get("worktrees", []):
            if not worktree.get("path_exists"):
                alerts.append(self._alert("worktree_missing", "attention", f"Worktree 路径失效：{worktree['path']}"))
            if worktree.get("branch") == "DETACHED":
                label = f"DETACHED ({Path(worktree['path']).name})"
                dirty = sum(
                    worktree.get(key, 0)
                    for key in ("modified_count", "added_count", "deleted_count", "untracked_count")
                )
                if worktree.get("conflict_count", 0):
                    alerts.append(self._alert("git_conflict", "blocking", f"{label} 存在 Git 冲突"))
                if dirty:
                    alerts.append(
                        self._alert("dirty_worktree", "attention", f"{label} 工作区有 {dirty} 项未提交变更")
                    )
        tasks = ((metadata.get("data") or {}).get("branches") or {}) if metadata else {}
        if metadata and metadata.get("error"):
            alerts.append(self._alert("metadata_invalid", "blocking", "Codex 状态文件不可解析"))
        rc_branches = {name for name, task in tasks.items() if task.get("branch_type") == "rc"}
        if project.get("rc_branch"):
            rc_branches.add(project["rc_branch"])
        if len(rc_branches) > 1:
            alerts.append(self._alert("multiple_rc", "attention", f"项目存在多个 RC 标记：{', '.join(sorted(rc_branches))}"))
        changed_by_file: dict[str, list[str]] = {}
        for branch in snapshot.get("branches", []):
            name = branch["name"]
            task = tasks.get(name, {})
            dirty = sum(branch.get(key, 0) for key in ("modified_count", "added_count", "deleted_count", "untracked_count"))
            if branch.get("conflict_count", 0):
                alerts.append(self._alert("git_conflict", "blocking", f"{name} 存在 Git 冲突", name))
            if dirty:
                alerts.append(self._alert("dirty_worktree", "attention", f"{name} 工作区有 {dirty} 项未提交变更", name))
            if (branch.get("behind") or 0) > 0:
                alerts.append(self._alert("behind_upstream", "attention", f"{name} 落后上游 {branch['behind']} 个提交", name))
            if task.get("result") in {"FAIL", "BLOCKED"}:
                alerts.append(self._alert("test_result", "blocking", f"{name} 状态结论为 {task['result']}", name))
            if task.get("result") == "PASS" and (dirty or branch.get("conflict_count", 0)):
                alerts.append(self._alert("pass_git_mismatch", "blocking", f"{name} 元数据为 PASS，但 Git 工作区存在异常", name))
            if branch.get("status") == "stale" and task.get("status") not in {"paused", "archived"}:
                alerts.append(self._alert("stale_branch", "attention", f"{name} 超过 7 天没有提交", name))
            if branch.get("is_merged_to_main") and task.get("status") in {"active", "validating"}:
                alerts.append(self._alert("merged_still_active", "attention", f"{name} 已合并但任务仍标记活跃", name))
            if self._metadata_is_stale_for_commit(task, branch):
                alerts.append(self._alert("metadata_stale", "attention", f"{name} 状态元数据超过 24 小时未更新，但 Git 已有新提交", name))
            if branch.get("worktree_path"):
                for changed_file in branch.get("changed_files", []):
                    changed_by_file.setdefault(changed_file.lower(), []).append(name)
        for changed_file, branch_names in changed_by_file.items():
            if len(set(branch_names)) > 1:
                alerts.append(self._alert("cross_worktree_file", "attention", f"多个 Worktree 正在修改同一文件 {changed_file}：{', '.join(sorted(set(branch_names)))}"))
        return alerts

    @staticmethod
    def _alert(alert_type: str, severity: str, message: str, branch: str | None = None) -> dict[str, Any]:
        return {
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "branch_name": branch,
            "is_resolved": False,
            "last_seen_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _metadata_is_stale_for_commit(task: dict[str, Any], branch: dict[str, Any]) -> bool:
        if not task.get("updated_at") or not branch.get("head_time"):
            return False
        try:
            updated = datetime.fromisoformat(task["updated_at"])
            committed = datetime.fromisoformat(branch["head_time"])
            now = datetime.now(timezone.utc)
            return (now - updated.astimezone(timezone.utc)).total_seconds() > 86400 and committed > updated
        except (TypeError, ValueError):
            return False
