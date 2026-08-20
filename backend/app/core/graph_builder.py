from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

from .git_runner import run_git


class GraphBuilder:
    """Build a compressed, focus-first graph without walking every branch DAG."""

    def __init__(self, focus_limit: int = 7, max_workers: int = 4):
        self.focus_limit = focus_limit
        self.max_workers = max_workers

    def build(
        self,
        snapshot: dict[str, Any],
        metadata: dict[str, Any] | None = None,
        scope: str = "focus",
    ) -> dict[str, Any]:
        root = Path(snapshot["repo_path"])
        meta_branches = ((metadata or {}).get("data") or {}).get("branches", {})
        ordered = self._ordered_branches(snapshot, meta_branches)
        focus = ordered[: self.focus_limit]
        rendered = ordered if scope == "all" else focus
        detailed_names = {branch["name"] for branch in focus}
        detail_limits = {branch["name"]: 8 if branch["name"] == snapshot["main_branch"] else 6 for branch in focus}
        details = self._load_details(root, focus, detail_limits, snapshot["main_branch"])
        lane_gap = 126
        root_y = 76 + max(0, len(rendered) - 1) * lane_gap / 2
        nodes: list[dict[str, Any]] = [
            {
                "id": "project:root",
                "type": "project",
                "position": {"x": 24, "y": root_y},
                "data": {"label": root.name, "repo_path": str(root), "branch_count": len(ordered)},
            }
        ]
        edges: list[dict[str, Any]] = []
        for lane, branch in enumerate(rendered):
            name = branch["name"]
            task = meta_branches.get(name)
            branch_type = (task or {}).get("branch_type") or branch["branch_type"]
            status = (task or {}).get("status") or branch["status"]
            y = 54 + lane * lane_gap
            branch_id = f"branch:{name}"
            nodes.append(
                {
                    "id": branch_id,
                    "type": "branch",
                    "position": {"x": 205, "y": y},
                    "data": {
                        **branch,
                        "branch": name,
                        "label": name,
                        "branch_type": branch_type,
                        "status": status,
                        "git_status": branch["status"],
                        "task_name": (task or {}).get("task_name") or ("主线" if name == snapshot["main_branch"] else "未维护"),
                        "result": (task or {}).get("result", "UNKNOWN"),
                        "progress": (task or {}).get("progress"),
                        "is_focus": name in detailed_names,
                    },
                }
            )
            edges.append(self._edge("project:root", branch_id, name, status in {"active", "validating"}))
            previous = branch_id
            x = 455
            branch_detail = details.get(name, {"commits": [], "total": 0})
            commits = branch_detail["commits"]
            total = branch_detail["total"]
            limit = detail_limits.get(name, 0)
            if total > limit:
                collapsed_id = f"collapsed:{name}"
                nodes.append(
                    {
                        "id": collapsed_id,
                        "type": "collapsed",
                        "position": {"x": x, "y": y + 25},
                        "data": {"label": f"+{total - limit} commits", "branch": name},
                    }
                )
                edges.append(self._edge(previous, collapsed_id, name, False))
                previous = collapsed_id
                x += 96
            for commit in reversed(commits):
                commit_id = f"commit:{name}:{commit['sha']}"
                nodes.append(
                    {
                        "id": commit_id,
                        "type": "commit",
                        "position": {"x": x, "y": y + 24},
                        "data": {**commit, "branch": name, "label": commit["short_sha"]},
                    }
                )
                edges.append(self._edge(previous, commit_id, name, status in {"active", "validating"}))
                previous = commit_id
                x += 82
            if task:
                task_id = f"task:{name}"
                nodes.append(
                    {
                        "id": task_id,
                        "type": "task",
                        "position": {"x": max(x + 24, 690), "y": y - 2},
                        "data": {
                            "branch": name,
                            "label": task.get("task_name") or "任务状态",
                            "branch_type": branch_type,
                            "status": status,
                            "result": task.get("result", "UNKNOWN"),
                            "progress": task.get("progress"),
                            "owner": task.get("owner") or "未维护",
                            "blockers": task.get("blockers") or [],
                        },
                    }
                )
                edges.append(self._edge(previous, task_id, name, status in {"active", "validating"}))
        return {
            "nodes": nodes,
            "edges": edges,
            "generated_at": snapshot["last_scan_at"],
            "scope": scope,
            "visible_branches": len(rendered),
            "total_branches": len(ordered),
            "focus_limit": self.focus_limit,
        }

    def _ordered_branches(self, snapshot: dict[str, Any], meta_branches: dict[str, Any]) -> list[dict[str, Any]]:
        main = snapshot["main_branch"]
        integration = snapshot.get("integration_branch")
        rc = snapshot.get("rc_branch")

        def timestamp(value: str | None) -> float:
            try:
                return datetime.fromisoformat(value or "").timestamp()
            except ValueError:
                return 0

        def priority(branch: dict[str, Any]) -> tuple[Any, ...]:
            task = meta_branches.get(branch["name"]) or {}
            status = task.get("status") or branch["status"]
            role = 0 if branch["name"] == main else 1 if branch["name"] == integration else 2 if branch["name"] == rc else 3
            state = 0 if status == "blocked" else 1 if status in {"active", "validating", "waiting_merge"} else 2
            checked = 0 if branch.get("is_checked_out") else 1
            return (role, state, checked, -timestamp(branch.get("head_time")), branch["name"])

        return sorted(snapshot["branches"], key=priority)

    def _load_details(
        self,
        root: Path,
        branches: list[dict[str, Any]],
        limits: dict[str, int],
        main: str,
    ) -> dict[str, dict[str, Any]]:
        def load(branch: dict[str, Any]) -> tuple[str, dict[str, Any]]:
            name = branch["name"]
            revision = name
            if name != main and branch.get("merge_base_sha"):
                revision = f"{branch['merge_base_sha']}..{name}"
            return name, self._commits_with_count(root, revision, limits[name])

        if not branches:
            return {}
        workers = min(self.max_workers, len(branches))
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="git-graph") as executor:
            return dict(executor.map(load, branches))

    @staticmethod
    def _edge(source: str, target: str, branch: str, animated: bool) -> dict[str, Any]:
        return {
            "id": f"edge:{source}:{target}",
            "source": source,
            "target": target,
            "type": "smoothstep",
            "animated": animated,
            "data": {"branch": branch},
        }

    @staticmethod
    def _commits_with_count(root: Path, revision: str, limit: int) -> dict[str, Any]:
        fmt = "%H%x00%h%x00%s%x00%an%x00%aI"
        output = run_git(root, ["log", revision, f"--max-count={limit + 1}", f"--format={fmt}"])
        commits: list[dict[str, Any]] = []
        for line in output.splitlines():
            fields = line.split("\x00")
            if len(fields) >= 5:
                commits.append(
                    {"sha": fields[0], "short_sha": fields[1], "message": fields[2], "author": fields[3], "time": fields[4]}
                )
        if len(commits) <= limit:
            return {"commits": commits, "total": len(commits)}
        value = run_git(root, ["rev-list", "--count", revision]).strip()
        total = int(value) if value.isdigit() else len(commits)
        return {"commits": commits[:limit], "total": total}
