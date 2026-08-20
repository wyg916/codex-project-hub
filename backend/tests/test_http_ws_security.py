from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.app.config import Settings, get_settings
from backend.app.main import MAX_HTTP_BODY_BYTES, RequestBodyLimitMiddleware, create_app
from backend.tests.test_api import create_project


def test_http_host_origin_cors_and_security_headers(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["service"] == "codex-project-hub"
    assert response.json()["version"] == "0.1.0"
    assert response.json()["deployment_scope"] == "localhost-only"
    assert "bind" not in response.json()
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    assert client.get("/api/docs").status_code == 404
    assert client.get("/api/openapi.json").status_code == 404

    assert client.get("/api/health", headers={"host": "attacker.example"}).status_code == 400
    assert client.get("/api/health", headers={"origin": "https://attacker.example"}).status_code == 403
    allowed = client.get("/api/health", headers={"origin": "http://127.0.0.1:5173"})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
    assert client.get("/api/projects").headers["cache-control"] == "no-store"


def test_production_defaults_do_not_trust_testclient_host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CPC_DISABLE_BACKGROUND", "1")
    monkeypatch.setenv("CPC_DATA_DIR", str(tmp_path / "production-data"))
    settings = get_settings()
    assert "testserver" not in settings.allowed_hosts
    with TestClient(create_app(settings)) as production_client:
        assert production_client.get("/api/health").status_code == 400


def test_configured_same_origin_can_load_static_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CPC_DISABLE_BACKGROUND", "1")
    frontend = tmp_path / "dist"
    assets = frontend / "assets"
    assets.mkdir(parents=True)
    (frontend / "index.html").write_text("<html></html>", encoding="utf-8")
    (assets / "app.js").write_text("export {}", encoding="utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        database_path=tmp_path / "data" / "app.db",
        frontend_dist=frontend,
        scan_interval_seconds=1,
        allowed_origins=("http://127.0.0.1:18765",),
        allowed_hosts=("127.0.0.1", "localhost", "testserver", "[::1]"),
    )
    with TestClient(create_app(settings)) as local_client:
        headers = {"origin": "http://127.0.0.1:18765"}
        assert local_client.get("/", headers=headers).status_code == 200
        asset = local_client.get("/assets/app.js", headers=headers)
        assert asset.status_code == 200
        assert asset.text == "export {}"
        assert asset.headers.get("cache-control") != "no-store"

        original_resolve = Path.resolve

        def reject_external_resolution(path: Path, *args, **kwargs):
            rendered = str(path)
            if "\\" in rendered or ":" in path.name:
                raise AssertionError("SPA fallback attempted to resolve an untrusted request path")
            return original_resolve(path, *args, **kwargs)

        monkeypatch.setattr(Path, "resolve", reject_external_resolution)
        for untrusted in (
            "/%5C%5Cattacker.invalid%5Cshare%5Cpayload",
            "/%43%3A%5CWindows%5Cwin.ini",
            "/..%5C..%5Csecret",
        ):
            fallback = local_client.get(untrusted, headers=headers)
            assert fallback.status_code == 200
            assert fallback.text == "<html></html>"


def test_picker_and_native_actions_default_to_forbidden(
    client: TestClient, git_repo: dict[str, Path]
) -> None:
    project = create_project(client, git_repo["repo"])
    assert client.get("/api/system/pick-directory").status_code == 404
    assert client.post("/api/system/pick-directory").status_code == 403
    response = client.post(
        "/api/actions/open-folder",
        json={"project_id": project["id"], "path": str(git_repo["repo"])},
    )
    assert response.status_code == 403
    assert "未启用" in response.json()["detail"]


def test_websocket_rejects_cross_site_origin_before_accept(
    client: TestClient, git_repo: dict[str, Path]
) -> None:
    project = create_project(client, git_repo["repo"])
    with pytest.raises(WebSocketDisconnect) as caught:
        with client.websocket_connect(
            f"/ws/projects/{project['id']}",
            headers={"origin": "https://attacker.example"},
        ):
            pass
    assert caught.value.code == 4403


def test_websocket_rejects_oversized_or_unknown_messages(
    client: TestClient, git_repo: dict[str, Path]
) -> None:
    project = create_project(client, git_repo["repo"])
    with client.websocket_connect(f"/ws/projects/{project['id']}") as socket:
        assert socket.receive_json()["type"] == "connected"
        socket.send_text("x" * 65)
        close = socket.receive()
        assert close["type"] == "websocket.close"
        assert close["code"] == 4400


def test_request_and_query_limits_apply_before_business_logic(client: TestClient) -> None:
    assert client.post("/api/projects", json={"repo_path": "x" * 4097}).status_code == 422
    assert client.get("/api/projects/1/events", params={"limit": 201}).status_code == 422
    assert client.get(
        "/api/projects/1/branches/detail",
        params={"branch_name": "x" * 1025},
    ).status_code == 422
    oversized = b'{"repo_path":"' + (b"x" * (1024 * 1024)) + b'"}'
    assert client.post("/api/projects", content=oversized, headers={"content-type": "application/json"}).status_code == 413


@pytest.mark.asyncio
async def test_body_limit_rejects_chunked_stream_without_content_length() -> None:
    messages = iter(
        (
            {"type": "http.request", "body": b"x" * (MAX_HTTP_BODY_BYTES // 2 + 1), "more_body": True},
            {"type": "http.request", "body": b"x" * (MAX_HTTP_BODY_BYTES // 2 + 1), "more_body": False},
        )
    )
    sent: list[dict] = []

    async def receive():
        return next(messages)

    async def send(message):
        sent.append(message)

    async def consume_body(_scope, limited_receive, _send):
        while True:
            message = await limited_receive()
            if not message.get("more_body"):
                break

    middleware = RequestBodyLimitMiddleware(consume_body)
    await middleware(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/projects",
            "raw_path": b"/api/projects",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 80),
            "root_path": "",
        },
        receive,
        send,
    )
    assert any(message.get("status") == 413 for message in sent)
