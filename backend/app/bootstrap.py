from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from backend.app.db.database import Database
from backend.app.schemas.domain import ProjectCreate
from backend.app.services.project_service import ProjectService
from backend.app.services.realtime import WebSocketManager


def _path_key(value: str | Path) -> str:
    return os.path.normcase(str(Path(value).resolve()))


def load_project_entries(config_path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取默认项目配置：{exc}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ValueError("默认项目配置 schema_version 必须为 1")
    entries = payload.get("projects")
    if not isinstance(entries, list):
        raise ValueError("默认项目配置 projects 必须是数组")
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            raise ValueError(f"第 {index} 个项目配置必须是对象")
        if not isinstance(entry.get("name"), str) or not entry["name"].strip():
            raise ValueError(f"第 {index} 个项目缺少 name")
        if not isinstance(entry.get("repo_path"), str) or not entry["repo_path"].strip():
            raise ValueError(f"第 {index} 个项目缺少 repo_path")
    return entries


async def bootstrap_projects(config_path: Path, database_path: Path) -> dict[str, Any]:
    entries = load_project_entries(config_path)
    database = Database(database_path)
    service = ProjectService(database, WebSocketManager())
    results: list[dict[str, Any]] = []

    for entry in entries:
        name = entry["name"].strip()
        try:
            configured_path = _path_key(entry["repo_path"])
            existing_fast = next(
                (
                    project
                    for project in database.list_projects()
                    if configured_path in {_path_key(project["repo_path"]), _path_key(project["canonical_worktree"])}
                ),
                None,
            )
            if existing_fast is not None and database.get_snapshot(existing_fast["id"]) is not None:
                identity = service.scanner.repository_identity(entry["repo_path"])
                if _path_key(identity["git_common_dir"]) == _path_key(existing_fast["git_common_dir"]):
                    project = service.get(existing_fast["id"])
                    snapshot = database.get_snapshot(project["id"]) or {}
                    results.append(
                        {
                            "name": project["name"],
                            "id": project["id"],
                            "action": "unchanged",
                            "repo_path": project["repo_path"],
                            "main_branch": project["main_branch"],
                            "worktree_count": len(snapshot.get("worktrees", [])),
                            "branch_count": len(snapshot.get("branches", [])),
                            "scan_status": project["scan_status"],
                        }
                    )
                    continue
            facts = service.scanner.validate_repository(entry["repo_path"])
            branches = facts["branches"]
            main_branch = entry.get("main_branch") or facts["main_branch"]
            integration_branch = entry.get("integration_branch") or None
            rc_branch = entry.get("rc_branch") or None
            service._validate_branch_choice(main_branch, branches, "主分支")
            service._validate_branch_choice(integration_branch, branches, "集成分支", optional=True)
            service._validate_branch_choice(rc_branch, branches, "RC 分支", optional=True)

            canonical = entry.get("canonical_worktree") or facts["canonical_worktree"]
            await service._validate_canonical(canonical, facts["git_common_dir"])
            existing = next(
                (
                    project
                    for project in database.list_projects()
                    if _path_key(project["git_common_dir"]) == _path_key(facts["git_common_dir"])
                ),
                None,
            )
            if existing is None:
                project = await service.create(ProjectCreate(**entry))
                action = "created"
            else:
                if database.get_snapshot(existing["id"]) is None:
                    await service.refresh(existing["id"], event_type="bootstrap")
                    action = "refreshed"
                else:
                    action = "unchanged"
                project = service.get(existing["id"])

            snapshot = database.get_snapshot(project["id"]) or {}
            results.append(
                {
                    "name": project["name"],
                    "id": project["id"],
                    "action": action,
                    "repo_path": project["repo_path"],
                    "main_branch": project["main_branch"],
                    "worktree_count": len(snapshot.get("worktrees", [])),
                    "branch_count": len(snapshot.get("branches", [])),
                    "scan_status": project["scan_status"],
                }
            )
        except Exception as exc:  # Process every configured project before failing the startup gate.
            detail = getattr(exc, "detail", None) or str(exc)
            results.append({"name": name, "action": "failed", "error": detail})

    failed = [item for item in results if item["action"] == "failed"]
    return {
        "status": "FAIL" if failed else "PASS",
        "configured": len(entries),
        "registered": len(entries) - len(failed),
        "failed": len(failed),
        "projects": results,
    }
