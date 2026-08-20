from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from backend.app.bootstrap import bootstrap_projects
from backend.app.db.database import Database


def test_bootstrap_projects_accepts_empty_project_list(tmp_path: Path) -> None:
    config = tmp_path / "default-projects.json"
    config.write_text(
        json.dumps({"schema_version": 1, "projects": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    database_path = tmp_path / "data" / "bootstrap.db"

    result = asyncio.run(bootstrap_projects(config, database_path))

    assert result == {
        "status": "PASS",
        "configured": 0,
        "registered": 0,
        "failed": 0,
        "projects": [],
    }
    assert Database(database_path).list_projects() == []


def test_bootstrap_projects_is_idempotent(git_repo: dict[str, Path], tmp_path: Path) -> None:
    config = tmp_path / "default-projects.json"
    config.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "projects": [
                    {
                        "name": "Project Alpha",
                        "repo_path": str(git_repo["repo"]),
                        "integration_branch": "feat/dashboard",
                        "rc_branch": "fix/demo",
                        "project_stage": "未维护",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    database_path = tmp_path / "data" / "bootstrap.db"

    first = asyncio.run(bootstrap_projects(config, database_path))
    database = Database(database_path)
    database.update_project(first["projects"][0]["id"], {"project_stage": "验证中"})
    second = asyncio.run(bootstrap_projects(config, database_path))

    assert first["status"] == "PASS"
    assert first["projects"][0]["action"] == "created"
    assert first["projects"][0]["worktree_count"] == 2
    assert second["status"] == "PASS"
    assert second["projects"][0]["action"] == "unchanged"
    projects = database.list_projects()
    assert len(projects) == 1
    assert projects[0]["name"] == "Project Alpha"
    assert projects[0]["project_stage"] == "验证中"

    root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "register-default-projects.py"),
            "--config",
            str(config),
            "--database",
            str(database_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "PROJECT_REGISTRATION_STATUS=PASS" in completed.stdout
    assert '"action": "unchanged"' in completed.stdout
