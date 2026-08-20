from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.tests.conftest import configure_repo, git


def create_project(client: TestClient, repo: Path) -> dict:
    response = client.post("/api/projects", json={"name": "测试项目", "repo_path": str(repo), "main_branch": "main", "integration_branch": "feat/dashboard"})
    assert response.status_code == 201, response.text
    return response.json()


def test_detached_dirty_worktree_is_counted_and_alerted(
    client: TestClient, git_repo: dict[str, Path], tmp_path: Path
) -> None:
    detached = tmp_path / "detached-worktree"
    git(git_repo["repo"], "worktree", "add", "--detach", str(detached), "HEAD")
    (detached / "detached-untracked.txt").write_text("dirty\n", encoding="utf-8")

    project = create_project(client, git_repo["repo"])
    worktrees = client.get(f"/api/projects/{project['id']}/worktrees").json()
    detached_state = next(item for item in worktrees if item["path"] == str(detached.resolve()))
    overview = client.get(f"/api/projects/{project['id']}/overview").json()
    alerts = client.get(f"/api/projects/{project['id']}/alerts").json()

    assert detached_state["branch"] == "DETACHED"
    assert detached_state["untracked_count"] == 1
    assert overview["dirty"] >= 1
    assert any(item["alert_type"] == "dirty_worktree" and "DETACHED" in item["message"] for item in alerts)


def test_project_crud_scan_graph_and_persistence(client: TestClient, git_repo: dict[str, Path]) -> None:
    project = create_project(client, git_repo["repo"])
    project_id = project["id"]
    dashboard = git_repo["repo"] / ".git" / "codex-dashboard"
    assert not dashboard.exists()
    assert client.post(f"/api/projects/{project_id}/refresh").status_code == 200
    assert not dashboard.exists()
    assert project["main_branch"] == "main"
    assert client.get("/api/projects").json()[0]["overview"]["metadata_status"] == "未维护"
    branches = client.get(f"/api/projects/{project_id}/branches").json()
    assert any(item["name"] == "feat/dashboard" and item["maintenance_status"] == "未维护" for item in branches)
    assert len(client.get(f"/api/projects/{project_id}/worktrees").json()) == 2
    graph = client.get(f"/api/projects/{project_id}/graph").json()
    assert any(node["id"] == "branch:main" for node in graph["nodes"])
    assert client.put(f"/api/projects/{project_id}", json={"project_stage": "验证中", "rc_branch": "fix/demo"}).status_code == 200
    assert client.get(f"/api/projects/{project_id}").json()["project_stage"] == "验证中"
    assert client.post("/api/projects", json={"repo_path": str(git_repo["worktree"])}).status_code == 409
    assert client.delete(f"/api/projects/{project_id}").status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_status_events_alerts_websocket_and_actions(client: TestClient, git_repo: dict[str, Path]) -> None:
    project = create_project(client, git_repo["repo"])
    project_id = project["id"]
    status = {
        "branch_name": "feat/dashboard",
        "data": {
            "branch_type": "feature",
            "task_name": "总控台任务",
            "objective": "闭环",
            "status": "active",
            "result": "PASS",
            "phase_progress": {"requirement": 100, "design": 100, "development": 80},
            "next_actions": ["运行验收"],
        },
    }
    response = client.put(f"/api/projects/{project_id}/branch-status", json=status)
    assert response.status_code == 200, response.text
    metadata_project = response.json()["data"]["project"]
    assert metadata_project == {
        "display_name": "测试项目",
        "canonical_worktree": project["canonical_worktree"],
        "main_branch": "main",
        "integration_branch": "feat/dashboard",
        "rc_branch": "",
    }
    branch = client.get(f"/api/projects/{project_id}/branches/detail", params={"branch_name": "feat/dashboard"}).json()
    assert branch["task"]["task_name"] == "总控台任务"
    alerts = client.get(f"/api/projects/{project_id}/alerts").json()
    assert any(item["alert_type"] == "pass_git_mismatch" for item in alerts)
    assert client.get(f"/api/projects/{project_id}/events").json()
    summary = client.post("/api/actions/copy-summary", json={"project_id": project_id, "branch_name": "feat/dashboard"}).json()["summary"]
    assert "总控台任务" in summary and "HEAD" in summary
    forbidden = client.post("/api/actions/open-folder", json={"project_id": project_id, "path": str(git_repo["repo"].parent.parent)})
    assert forbidden.status_code == 403
    with client.websocket_connect(f"/ws/projects/{project_id}") as socket:
        assert socket.receive_json()["type"] == "connected"


def test_invalid_project_does_not_break_health(client: TestClient, tmp_path: Path) -> None:
    response = client.post("/api/projects", json={"repo_path": str(tmp_path)})
    assert response.status_code == 422
    assert client.get("/api/health").json()["status"] == "ok"


def test_graph_is_focus_first_cached_and_supports_all_scope(client: TestClient, git_repo: dict[str, Path], monkeypatch) -> None:
    project = create_project(client, git_repo["repo"])
    service = client.app.state.projects
    original = service.graph_builder.build
    calls: list[str] = []

    def counted(snapshot, metadata, scope="focus"):
        calls.append(scope)
        return original(snapshot, metadata, scope)

    monkeypatch.setattr(service.graph_builder, "build", counted)
    first = client.get(f"/api/projects/{project['id']}/graph")
    second = client.get(f"/api/projects/{project['id']}/graph")
    expanded = client.get(f"/api/projects/{project['id']}/graph", params={"scope": "all"})

    assert first.status_code == second.status_code == expanded.status_code == 200
    assert calls == ["focus", "all"]
    assert first.json()["scope"] == "focus"
    assert first.json()["visible_branches"] <= first.json()["total_branches"]
    assert expanded.json()["visible_branches"] == expanded.json()["total_branches"]
    assert client.get(f"/api/projects/{project['id']}/graph", params={"scope": "invalid"}).status_code == 422


def test_registers_five_independent_projects(client: TestClient, tmp_path: Path) -> None:
    for index in range(5):
        repo = tmp_path / f"repo-{index}"
        repo.mkdir()
        git(repo, "init", "-b", "main")
        configure_repo(repo)
        (repo / "README.md").write_text(str(index), encoding="utf-8")
        git(repo, "add", "README.md")
        git(repo, "commit", "-m", f"project {index}")
        assert client.post("/api/projects", json={"repo_path": str(repo)}).status_code == 201
    assert len(client.get("/api/projects").json()) == 5
