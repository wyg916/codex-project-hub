from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from backend.app.core.alerts import AlertService
from backend.app.core.events import EventService
from backend.app.core.git_scanner import GitScanner
from backend.app.core.graph_builder import GraphBuilder
from backend.app.core.status_metadata import StatusMetadataService
from backend.app.db.database import Database, utc_now
from backend.app.schemas.domain import BranchTask, ProjectCreate, ProjectUpdate, StatusMetadata
from .realtime import WebSocketManager


MAX_COALESCED_RESCANS = 3
MAX_CONCURRENT_PROJECT_SCANS = 3


class ProjectService:
    def __init__(self, database: Database, sockets: WebSocketManager):
        self.database = database
        self.sockets = sockets
        self.scanner = GitScanner()
        self.graph_builder = GraphBuilder()
        self.metadata = StatusMetadataService()
        self.events = EventService()
        self.alerts = AlertService()
        self._scan_locks: dict[int, asyncio.Lock] = {}
        self._scan_semaphore = asyncio.Semaphore(MAX_CONCURRENT_PROJECT_SCANS)
        self._pending_rescans: set[int] = set()
        self._graph_locks: dict[tuple[int, str], asyncio.Lock] = {}
        self._graph_cache: dict[tuple[int, str, str], dict[str, Any]] = {}

    async def create(self, payload: ProjectCreate) -> dict[str, Any]:
        try:
            facts = await asyncio.to_thread(self.scanner.validate_repository, payload.repo_path)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        branches = facts["branches"]
        main = payload.main_branch or facts["main_branch"]
        self._validate_branch_choice(main, branches, "主分支")
        self._validate_branch_choice(payload.integration_branch, branches, "集成分支", optional=True)
        self._validate_branch_choice(payload.rc_branch, branches, "RC 分支", optional=True)
        canonical = payload.canonical_worktree or facts["canonical_worktree"]
        await self._validate_canonical(canonical, facts["git_common_dir"])
        values = {
            "name": payload.name or Path(facts["repo_path"]).name,
            "repo_path": facts["repo_path"],
            "canonical_worktree": str(Path(canonical).resolve()),
            "remote_url": facts["remote_url"],
            "git_common_dir": facts["git_common_dir"],
            "main_branch": main,
            "integration_branch": payload.integration_branch,
            "rc_branch": payload.rc_branch,
            "project_stage": payload.project_stage,
            "priority": payload.priority,
        }
        try:
            project = self.database.create_project(values)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="该 Git Common Dir 已登记") from exc
        await self.refresh(project["id"])
        return self.get(project["id"])

    async def update(self, project_id: int, payload: ProjectUpdate) -> dict[str, Any]:
        project = self._require_project(project_id)
        snapshot = self.database.get_snapshot(project_id) or await self.refresh(project_id)
        values = payload.model_dump(exclude_none=True)
        branches = [item["name"] for item in snapshot.get("branches", [])]
        for key, label in (("main_branch", "主分支"), ("integration_branch", "集成分支"), ("rc_branch", "RC 分支")):
            if key in values:
                self._validate_branch_choice(values[key], branches, label, optional=key != "main_branch")
        if values.get("canonical_worktree"):
            await self._validate_canonical(values["canonical_worktree"], project["git_common_dir"])
            values["canonical_worktree"] = str(Path(values["canonical_worktree"]).resolve())
        updated = self.database.update_project(project_id, values)
        await self.refresh(project_id)
        return self.get(project_id) if updated else self._not_found()

    def delete(self, project_id: int) -> None:
        if not self.database.delete_project(project_id):
            self._not_found()

    def list(self) -> list[dict[str, Any]]:
        return [self._project_with_overview(project) for project in self.database.list_projects()]

    def get(self, project_id: int) -> dict[str, Any]:
        return self._project_with_overview(self._require_project(project_id))

    async def refresh(self, project_id: int, event_type: str = "manual") -> dict[str, Any]:
        project = self._require_project(project_id)
        lock = self._scan_locks.setdefault(project_id, asyncio.Lock())
        if lock.locked():
            if event_type in {"watchdog", "poll"}:
                self._pending_rescans.add(project_id)
            async with lock:
                pass
            return self.database.get_snapshot(project_id) or {}
        async with lock:
            snapshot = await self._refresh_once(project_id, project, event_type)
            coalesced = 0
            while project_id in self._pending_rescans and coalesced < MAX_COALESCED_RESCANS:
                self._pending_rescans.discard(project_id)
                snapshot = await self._refresh_once(project_id, project, "coalesced")
                coalesced += 1
            return snapshot

    async def _refresh_once(
        self, project_id: int, project: dict[str, Any], event_type: str
    ) -> dict[str, Any]:
        await self.sockets.broadcast(project_id, {"type": "scan.started", "project_id": project_id})
        previous = self.database.get_snapshot(project_id)
        try:
            async with self._scan_semaphore:
                snapshot = await asyncio.to_thread(self.scanner.scan_project, project)
            status_path = self.metadata.metadata_path(snapshot["git_common_dir"])
            if status_path.exists():
                status_stat = status_path.stat()
                snapshot["metadata_revision"] = f"{status_stat.st_mtime_ns}:{status_stat.st_size}"
            else:
                snapshot["metadata_revision"] = "missing"
            metadata_state = self.metadata.read(snapshot["git_common_dir"])
            snapshot["metadata_summary"] = {
                name: {
                    "status": task.get("status"),
                    "result": task.get("result"),
                    "tests": task.get("tests"),
                    "updated_at": task.get("updated_at"),
                }
                for name, task in ((metadata_state.get("data") or {}).get("branches") or {}).items()
            }
            changed = self._snapshot_key(previous) != self._snapshot_key(snapshot)
            if changed:
                self._invalidate_graph(project_id)
            self.database.save_snapshot(project_id, snapshot)
            self.database.update_project(
                project_id,
                {
                    "last_scan_at": snapshot["last_scan_at"],
                    "scan_status": "ok",
                    "remote_url": snapshot.get("remote_url"),
                    "repo_path": snapshot["repo_path"],
                    "git_common_dir": snapshot["git_common_dir"],
                },
            )
            for item in self.events.compare(project_id, previous, snapshot):
                if self.database.add_event(item):
                    await self.sockets.broadcast(project_id, {"type": "event.created", "data": item})
            if changed:
                await self.sockets.broadcast(
                    project_id,
                    {"type": "snapshot.updated", "project_id": project_id, "scanned_at": snapshot["last_scan_at"]},
                )
            await self.sockets.broadcast(project_id, {"type": "scan.completed", "project_id": project_id})
            return snapshot
        except Exception as exc:
            self.database.update_project(project_id, {"last_scan_at": utc_now(), "scan_status": "failed"})
            await self.sockets.broadcast(
                project_id,
                {"type": "scan.failed", "project_id": project_id, "detail": "项目扫描失败"},
            )
            if event_type in {"poll", "watchdog", "coalesced"}:
                return previous or {"scan_status": "failed", "error": "项目扫描失败"}
            raise HTTPException(status_code=422, detail="项目扫描失败，请检查项目状态") from exc

    def snapshot(self, project_id: int) -> dict[str, Any]:
        self._require_project(project_id)
        snapshot = self.database.get_snapshot(project_id)
        if snapshot is None:
            raise HTTPException(status_code=503, detail="项目尚未完成首次扫描")
        return snapshot

    def branches(self, project_id: int) -> list[dict[str, Any]]:
        snapshot = self.snapshot(project_id)
        metadata = self.status_metadata(project_id)
        tasks = ((metadata.get("data") or {}).get("branches") or {})
        result = []
        for branch in snapshot["branches"]:
            task = tasks.get(branch["name"])
            result.append({**branch, "task": task, "maintenance_status": "已维护" if task else "未维护"})
        return result

    def branch(self, project_id: int, branch_name: str) -> dict[str, Any]:
        for branch in self.branches(project_id):
            if branch["name"] == branch_name:
                return branch
        raise HTTPException(status_code=404, detail="分支不存在")

    async def graph(self, project_id: int, scope: str = "focus") -> dict[str, Any]:
        if scope not in {"focus", "all"}:
            raise HTTPException(status_code=422, detail="scope 只支持 focus 或 all")
        snapshot = self.snapshot(project_id)
        revision = self._snapshot_key(snapshot)
        cache_key = (project_id, scope, revision)
        cached = self._graph_cache.get(cache_key)
        if cached is not None:
            return cached
        lock_key = (project_id, scope)
        lock = self._graph_locks.setdefault(lock_key, asyncio.Lock())
        async with lock:
            cached = self._graph_cache.get(cache_key)
            if cached is not None:
                return cached
            graph = await asyncio.to_thread(
                self.graph_builder.build,
                snapshot,
                self.status_metadata(project_id),
                scope,
            )
            self._graph_cache[cache_key] = graph
            return graph

    def status_metadata(self, project_id: int) -> dict[str, Any]:
        project = self._require_project(project_id)
        return self.metadata.read(project["git_common_dir"])

    async def write_metadata(self, project_id: int, payload: StatusMetadata) -> dict[str, Any]:
        project = self._require_project(project_id)
        try:
            result = await asyncio.to_thread(self.metadata.write, project["git_common_dir"], payload)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail="状态元数据写入冲突") from exc
        self._invalidate_graph(project_id)
        await self.sockets.broadcast(project_id, {"type": "branch.updated", "project_id": project_id})
        return result

    async def write_branch_status(self, project_id: int, branch_name: str, task: BranchTask) -> dict[str, Any]:
        self.branch(project_id, branch_name)
        project = self._require_project(project_id)
        project_defaults = {
            "display_name": project["name"],
            "canonical_worktree": project["canonical_worktree"],
            "main_branch": project["main_branch"],
            "integration_branch": project.get("integration_branch") or "",
            "rc_branch": project.get("rc_branch") or "",
        }
        try:
            result = await asyncio.to_thread(
                self.metadata.update_branch,
                project["git_common_dir"],
                branch_name,
                task,
                project_defaults,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail="状态元数据写入冲突") from exc
        self._invalidate_graph(project_id)
        await self.sockets.broadcast(project_id, {"type": "branch.updated", "project_id": project_id, "branch": branch_name})
        return result

    def project_events(self, project_id: int, limit: int = 100) -> list[dict[str, Any]]:
        self._require_project(project_id)
        return self.database.list_events(project_id, min(max(limit, 1), 200))

    def project_alerts(self, project_id: int) -> list[dict[str, Any]]:
        project = self._require_project(project_id)
        return self.alerts.build(project, self.snapshot(project_id), self.status_metadata(project_id))

    def overview(self, project_id: int) -> dict[str, Any]:
        return self._project_with_overview(self._require_project(project_id))["overview"]

    def allowed_paths(self, project_id: int) -> list[Path]:
        project = self._require_project(project_id)
        snapshot = self.database.get_snapshot(project_id) or {}
        values = [project["repo_path"], project["canonical_worktree"], *(item["path"] for item in snapshot.get("worktrees", []))]
        paths: list[Path] = []
        for value in values:
            if not value:
                continue
            path = Path(value).expanduser().absolute()
            if path not in paths:
                paths.append(path)
        return paths

    def _project_with_overview(self, project: dict[str, Any]) -> dict[str, Any]:
        snapshot = self.database.get_snapshot(project["id"])
        if not snapshot:
            return {**project, "overview": {"active": 0, "waiting_merge": 0, "blocked": 0, "dirty": 0, "alerts": 0, "next_action": "等待首次扫描"}}
        metadata = self.metadata.read(project["git_common_dir"])
        tasks = ((metadata.get("data") or {}).get("branches") or {})
        merged = sum(1 for item in snapshot["branches"] if item["is_merged_to_main"])
        active = sum(1 for item in snapshot["branches"] if (tasks.get(item["name"]) or {}).get("status", item["status"]) in {"active", "validating"})
        waiting = sum(1 for task in tasks.values() if task.get("status") == "waiting_merge")
        blocked = sum(1 for task in tasks.values() if task.get("status") == "blocked")
        dirty = sum(
            1
            for item in snapshot.get("worktrees", [])
            if any(
                item.get(key, 0)
                for key in ("modified_count", "added_count", "deleted_count", "untracked_count", "conflict_count")
            )
        )
        next_action = next((task.get("next_actions", [None])[0] for task in tasks.values() if task.get("next_actions")), "未维护")
        alerts = self.alerts.build(project, snapshot, metadata)
        return {
            **project,
            "overview": {
                "active": active,
                "waiting_merge": waiting,
                "blocked": blocked,
                "dirty": dirty,
                "merged": merged,
                "alerts": len(alerts),
                "next_action": next_action,
                "metadata_status": "状态文件不可解析" if metadata["error"] else "已维护" if metadata["maintained"] else "未维护",
            },
        }

    def _require_project(self, project_id: int) -> dict[str, Any]:
        project = self.database.get_project(project_id)
        if project is None:
            self._not_found()
        return project

    @staticmethod
    def _not_found():
        raise HTTPException(status_code=404, detail="项目不存在")

    @staticmethod
    def _validate_branch_choice(value: str | None, branches: list[str], label: str, optional: bool = False) -> None:
        if not value and optional:
            return
        if value not in branches:
            raise HTTPException(status_code=422, detail=f"{label}不是现有本地分支")

    async def _validate_canonical(self, path: str, expected_common: str) -> None:
        try:
            facts = await asyncio.to_thread(self.scanner.validate_repository, path)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"主项目目录无效：{exc}") from exc
        if Path(facts["git_common_dir"]).resolve() != Path(expected_common).resolve():
            raise HTTPException(status_code=422, detail="主项目目录不属于同一 Git Common Dir")

    @staticmethod
    def _snapshot_key(snapshot: dict[str, Any] | None) -> str:
        if snapshot is None:
            return ""
        payload = {key: value for key, value in snapshot.items() if key != "last_scan_at"}
        payload["branches"] = [
            {key: value for key, value in branch.items() if key != "last_scan_at"}
            for branch in snapshot.get("branches", [])
        ]
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _invalidate_graph(self, project_id: int) -> None:
        self._graph_cache = {
            key: value for key, value in self._graph_cache.items() if key[0] != project_id
        }
