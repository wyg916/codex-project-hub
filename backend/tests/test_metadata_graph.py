from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.app.core import status_metadata
from backend.app.core.git_scanner import GitScanner
from backend.app.core.graph_builder import GraphBuilder
from backend.app.core.status_metadata import StatusMetadataService, UnsafeMetadataPath
from backend.app.schemas.domain import BranchTask, StatusMetadata, weighted_progress
from backend.tests.conftest import git
from backend.tests.test_git_scanner import project


def test_metadata_missing_invalid_and_weighted_progress(git_repo: dict[str, Path]) -> None:
    facts = GitScanner().validate_repository(git_repo["repo"])
    service = StatusMetadataService()
    missing = service.read(facts["git_common_dir"])
    assert missing["maintained"] is False
    assert missing["data"] is None
    path = service.metadata_path(facts["git_common_dir"])
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")
    invalid = service.read(facts["git_common_dir"])
    assert invalid["maintained"] is True
    assert "状态文件不可解析" in invalid["error"]
    assert path.read_text(encoding="utf-8") == "{broken"
    assert weighted_progress({"phase_progress": {"requirement": 100, "design": 100, "development": 50}}) == 38


def test_graph_limits_commits_and_adds_collapsed_node(git_repo: dict[str, Path]) -> None:
    worktree = git_repo["worktree"]
    git(worktree, "add", "feature.txt", "未跟踪.txt")
    git(worktree, "commit", "-m", "clean dirty files")
    for index in range(10):
        (worktree / "feature.txt").write_text(f"change {index}\n", encoding="utf-8")
        git(worktree, "commit", "-am", f"feature {index}")
    scanner = GitScanner()
    snapshot = scanner.scan_project(project(git_repo["repo"]))
    graph = GraphBuilder().build(snapshot, {"maintained": False, "data": None})
    feature_commits = [node for node in graph["nodes"] if node["type"] == "commit" and node["data"]["branch"] == "feat/dashboard"]
    assert len(feature_commits) == 6
    assert any(node["type"] == "collapsed" and node["data"]["branch"] == "feat/dashboard" for node in graph["nodes"])


def test_metadata_round_trip_defaults_tests_to_not_run(git_repo: dict[str, Path]) -> None:
    facts = GitScanner().validate_repository(git_repo["repo"])
    payload = {
        "schema_version": 1,
        "project": {"display_name": "测试", "canonical_worktree": str(git_repo["repo"]), "main_branch": "main"},
        "branches": {"feat/dashboard": {"task_name": "真实任务", "phase_progress": {"development": 50}}},
    }
    result = StatusMetadataService().write(facts["git_common_dir"], payload)
    task = result["data"]["branches"]["feat/dashboard"]
    assert task["tests"]["unit"] == "NOT_RUN"
    assert task["progress"] == 18
    json.loads(Path(result["path"]).read_text(encoding="utf-8"))


def test_full_metadata_write_preserves_and_rejects_corrupt_status(tmp_path: Path) -> None:
    common = tmp_path / "common"
    common.mkdir()
    service = StatusMetadataService()
    path = service.metadata_path(common)
    path.parent.mkdir()
    path.write_text("{invalid", encoding="utf-8")
    payload = {
        "schema_version": 1,
        "project": {"display_name": "test", "canonical_worktree": str(tmp_path), "main_branch": "main"},
        "branches": {},
    }

    with pytest.raises(ValueError, match="状态文件已损坏"):
        service.write(common, payload)

    assert path.read_text(encoding="utf-8") == "{invalid"
    assert not list(path.parent.glob("status.*.bak.json"))


def test_metadata_requires_contract_project_fields() -> None:
    with pytest.raises(ValidationError):
        StatusMetadata.model_validate(
            {"schema_version": 1, "project": {"main_branch": "main"}, "branches": {}}
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"project": {"display_name": "x", "canonical_worktree": "x", "main_branch": "main"}, "branches": {}},
        {"schema_version": 1, "project": {"display_name": "x", "canonical_worktree": "x", "main_branch": "main"}},
    ],
)
def test_metadata_requires_all_top_level_contract_fields(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        StatusMetadata.model_validate(payload)


def test_metadata_rejects_unknown_phase_progress_key() -> None:
    with pytest.raises(ValidationError):
        BranchTask.model_validate({"phase_progress": {"arbitrary_phase": 50}})


def test_metadata_rejects_reparse_dashboard_without_reflecting_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    common = tmp_path / "sensitive-common-name"
    dashboard = common / "codex-dashboard"
    dashboard.mkdir(parents=True)
    service = StatusMetadataService()
    original = service._is_reparse_point
    monkeypatch.setattr(
        service,
        "_is_reparse_point",
        lambda path: path == dashboard or original(path),
    )

    with pytest.raises(UnsafeMetadataPath):
        service.metadata_path(common)
    result = service.read(common)
    assert result["error"] == "状态文件路径不安全"
    assert result["path"] is None
    assert "sensitive-common-name" not in result["error"]


def test_status_backups_have_bounded_retention(tmp_path: Path) -> None:
    common = tmp_path / "common"
    common.mkdir()
    service = StatusMetadataService()
    payload = {
        "schema_version": 1,
        "project": {"display_name": "test", "canonical_worktree": str(tmp_path), "main_branch": "main"},
        "branches": {},
    }
    for index in range(8):
        payload["project"]["display_name"] = f"test-{index}"
        service.write(common, payload)
    backups = list((common / "codex-dashboard").glob("status.*.bak.json"))
    assert len(backups) == status_metadata.MAX_STATUS_BACKUPS


def test_oversized_write_does_not_rotate_status_or_backups(tmp_path: Path) -> None:
    common = tmp_path / "common"
    common.mkdir()
    service = StatusMetadataService()
    payload = {
        "schema_version": 1,
        "project": {"display_name": "test", "canonical_worktree": str(tmp_path), "main_branch": "main"},
        "branches": {},
    }
    for index in range(status_metadata.MAX_STATUS_BACKUPS + 1):
        payload["project"]["display_name"] = f"test-{index}"
        service.write(common, payload)
    path = service.metadata_path(common)
    before_status = path.read_bytes()
    before_backups = {item.name: item.read_bytes() for item in path.parent.glob("status.*.bak.json")}
    oversized = {
        **payload,
        "branches": {
            f"feat/{index}": {"task_name": f"task-{index}", "objective": "x" * 4096}
            for index in range(300)
        },
    }

    with pytest.raises(ValueError, match="大小限制"):
        service.write(common, oversized)

    assert path.read_bytes() == before_status
    assert {item.name: item.read_bytes() for item in path.parent.glob("status.*.bak.json")} == before_backups


def test_concurrent_branch_updates_do_not_lose_sibling_branch(tmp_path: Path) -> None:
    common = tmp_path / "common"
    common.mkdir()
    service = StatusMetadataService()
    barrier = threading.Barrier(2)
    project = {
        "display_name": "concurrent",
        "canonical_worktree": str(tmp_path),
        "main_branch": "main",
    }

    def update(name: str) -> None:
        barrier.wait(timeout=2)
        service.update_branch(
            common,
            name,
            BranchTask(task_name=name, status="active"),
            project_defaults=project,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(update, ("feat/one", "feat/two")))
    result = service.read(common)
    assert result["error"] is None
    assert set(result["data"]["branches"]) == {"feat/one", "feat/two"}
