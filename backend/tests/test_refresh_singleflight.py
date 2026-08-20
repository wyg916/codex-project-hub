from __future__ import annotations

import asyncio
import threading
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from backend.app.db.database import Database
from backend.app.services.project_service import ProjectService
from backend.app.services.realtime import WebSocketManager


def make_service(tmp_path: Path) -> tuple[ProjectService, int, dict]:
    common = tmp_path / "git-common"
    repo = tmp_path / "repo"
    common.mkdir()
    repo.mkdir()
    database = Database(tmp_path / "app.db")
    project = database.create_project(
        {
            "name": "singleflight",
            "repo_path": str(repo),
            "canonical_worktree": str(repo),
            "remote_url": None,
            "git_common_dir": str(common),
            "main_branch": "main",
            "integration_branch": None,
            "rc_branch": None,
            "project_stage": "test",
            "priority": 0,
        }
    )
    snapshot = {
        "project_id": project["id"],
        "repo_path": str(repo),
        "canonical_worktree": str(repo),
        "git_common_dir": str(common),
        "remote_url": None,
        "main_branch": "main",
        "integration_branch": None,
        "rc_branch": None,
        "current_branch": "main",
        "worktrees": [],
        "branches": [],
        "last_scan_at": datetime.now(timezone.utc).isoformat(),
        "scan_status": "ok",
    }
    return ProjectService(database, WebSocketManager()), project["id"], snapshot


@pytest.mark.asyncio
async def test_concurrent_manual_refreshes_share_one_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, project_id, snapshot = make_service(tmp_path)
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def scan(_project):
        nonlocal calls
        calls += 1
        started.set()
        assert release.wait(2)
        return deepcopy(snapshot)

    monkeypatch.setattr(service.scanner, "scan_project", scan)
    first = asyncio.create_task(service.refresh(project_id))
    assert await asyncio.to_thread(started.wait, 2)
    followers = [asyncio.create_task(service.refresh(project_id)) for _ in range(4)]
    await asyncio.sleep(0.05)
    release.set()
    await asyncio.gather(first, *followers)
    assert calls == 1


@pytest.mark.asyncio
async def test_concurrent_watcher_refreshes_coalesce_to_one_pending_scan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, project_id, snapshot = make_service(tmp_path)
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def scan(_project):
        nonlocal calls
        calls += 1
        started.set()
        assert release.wait(2)
        return deepcopy(snapshot)

    monkeypatch.setattr(service.scanner, "scan_project", scan)
    first = asyncio.create_task(service.refresh(project_id))
    assert await asyncio.to_thread(started.wait, 2)
    followers = [
        asyncio.create_task(service.refresh(project_id, event_type="watchdog"))
        for _ in range(4)
    ]
    await asyncio.sleep(0.05)
    release.set()
    await asyncio.gather(first, *followers)
    assert calls == 2


@pytest.mark.asyncio
async def test_watcher_arrival_during_second_scan_is_not_lost(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, project_id, snapshot = make_service(tmp_path)
    first_started = threading.Event()
    second_started = threading.Event()
    release_first = threading.Event()
    release_second = threading.Event()
    calls = 0

    def scan(_project):
        nonlocal calls
        calls += 1
        if calls == 1:
            first_started.set()
            assert release_first.wait(2)
        elif calls == 2:
            second_started.set()
            assert release_second.wait(2)
        return deepcopy(snapshot)

    monkeypatch.setattr(service.scanner, "scan_project", scan)
    first = asyncio.create_task(service.refresh(project_id))
    assert await asyncio.to_thread(first_started.wait, 2)
    during_first = asyncio.create_task(service.refresh(project_id, event_type="watchdog"))
    await asyncio.sleep(0.05)
    release_first.set()
    assert await asyncio.to_thread(second_started.wait, 2)
    during_second = asyncio.create_task(service.refresh(project_id, event_type="watchdog"))
    await asyncio.sleep(0.05)
    release_second.set()
    await asyncio.gather(first, during_first, during_second)
    assert calls == 3


@pytest.mark.asyncio
async def test_cross_project_scans_have_global_concurrency_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = Database(tmp_path / "multi.db")
    service = ProjectService(database, WebSocketManager())
    project_ids: list[int] = []
    for index in range(7):
        repo = tmp_path / f"repo-{index}"
        common = tmp_path / f"common-{index}"
        repo.mkdir()
        common.mkdir()
        project = database.create_project(
            {
                "name": f"project-{index}",
                "repo_path": str(repo),
                "canonical_worktree": str(repo),
                "remote_url": None,
                "git_common_dir": str(common),
                "main_branch": "main",
                "integration_branch": None,
                "rc_branch": None,
                "project_stage": "test",
                "priority": 0,
            }
        )
        project_ids.append(project["id"])

    mutex = threading.Lock()
    active = 0
    maximum = 0

    def scan(project):
        nonlocal active, maximum
        with mutex:
            active += 1
            maximum = max(maximum, active)
        time.sleep(0.1)
        with mutex:
            active -= 1
        return {
            "project_id": project["id"],
            "repo_path": project["repo_path"],
            "canonical_worktree": project["canonical_worktree"],
            "git_common_dir": project["git_common_dir"],
            "remote_url": None,
            "main_branch": "main",
            "integration_branch": None,
            "rc_branch": None,
            "current_branch": "main",
            "worktrees": [],
            "branches": [],
            "last_scan_at": datetime.now(timezone.utc).isoformat(),
            "scan_status": "ok",
        }

    monkeypatch.setattr(service.scanner, "scan_project", scan)
    await asyncio.gather(*(service.refresh(project_id) for project_id in project_ids))
    assert maximum == 3
