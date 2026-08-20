from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

from backend.app.config import APP_VERSION, SERVICE_NAME, Settings, get_settings, normalize_origin
from backend.app.core.watcher import PollingService, WatcherCoordinator
from backend.app.db.database import Database
from backend.app.schemas.domain import (
    ActionRequest,
    BranchStatusUpdate,
    ProjectCreate,
    ProjectUpdate,
    StatusMetadata,
)
from backend.app.services.project_service import ProjectService
from backend.app.services.realtime import WebSocketManager
from backend.app.services.system_actions import SystemActionService


MAX_HTTP_BODY_BYTES = 1024 * 1024


class _RequestBodyTooLarge(Exception):
    pass


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_HTTP_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        try:
            content_length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            response = JSONResponse(status_code=400, content={"detail": "Content-Length 无效"})
            await response(scope, receive, send)
            return
        if content_length > self.max_bytes:
            response = JSONResponse(status_code=413, content={"detail": "请求体过大"})
            await response(scope, receive, send)
            return
        consumed = 0

        async def limited_receive():
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                consumed += len(message.get("body", b""))
                if consumed > self.max_bytes:
                    raise _RequestBodyTooLarge
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _RequestBodyTooLarge:
            response = JSONResponse(status_code=413, content={"detail": "请求体过大"})
            await response(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    allowed_origins = frozenset(normalize_origin(origin) for origin in resolved.allowed_origins)
    database = Database(resolved.database_path)
    sockets = WebSocketManager()
    projects = ProjectService(database, sockets)
    actions = SystemActionService(projects, enabled=resolved.system_actions_enabled)
    watcher = WatcherCoordinator(projects)
    poller = PollingService(projects, watcher, resolved.scan_interval_seconds)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task: asyncio.Task[Any] | None = None
        background_enabled = os.getenv("CPC_DISABLE_BACKGROUND") != "1"
        if background_enabled:
            watcher.start()
            task = asyncio.create_task(poller.run(), name="project-poller")
        yield
        if background_enabled:
            poller.stop()
            if task:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            watcher.stop()

    app = FastAPI(
        title="Codex Project Hub",
        version=APP_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.settings = resolved
    app.state.database = database
    app.state.projects = projects
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(resolved.allowed_hosts))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(allowed_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=MAX_HTTP_BODY_BYTES)

    @app.middleware("http")
    async def enforce_request_boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin:
            try:
                normalized = normalize_origin(origin)
            except ValueError:
                normalized = ""
            if normalized not in allowed_origins:
                response = JSONResponse(status_code=403, content={"detail": "Origin 不受信任"})
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; base-uri 'none'; object-src 'none'; frame-ancestors 'none'; "
            "script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'"
        )
        if request.url.path.startswith("/api/") and "application/json" in response.headers.get("content-type", ""):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/api/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "version": app.version,
            "deployment_scope": "localhost-only",
        }

    @app.post("/api/system/pick-directory")
    async def pick_directory() -> dict[str, str | None]:
        if not resolved.system_actions_enabled:
            raise HTTPException(status_code=403, detail="原生系统动作未启用")

        def choose() -> str | None:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            try:
                value = filedialog.askdirectory(title="选择本地 Git 项目目录", mustexist=True)
                return str(Path(value).resolve()) if value else None
            finally:
                root.destroy()

        return {"path": await asyncio.to_thread(choose)}

    @app.get("/api/projects")
    async def list_projects() -> list[dict[str, Any]]:
        return projects.list()

    @app.post("/api/projects", status_code=201)
    async def create_project(payload: ProjectCreate) -> dict[str, Any]:
        result = await projects.create(payload)
        watcher.sync()
        return result

    @app.get("/api/projects/{project_id}")
    async def get_project(project_id: int) -> dict[str, Any]:
        return projects.get(project_id)

    @app.put("/api/projects/{project_id}")
    async def update_project(project_id: int, payload: ProjectUpdate) -> dict[str, Any]:
        return await projects.update(project_id, payload)

    @app.delete("/api/projects/{project_id}", status_code=204)
    async def delete_project(project_id: int):
        projects.delete(project_id)

    @app.post("/api/projects/{project_id}/refresh")
    async def refresh_project(project_id: int) -> dict[str, Any]:
        return await projects.refresh(project_id)

    @app.get("/api/projects/{project_id}/overview")
    async def project_overview(project_id: int) -> dict[str, Any]:
        return projects.overview(project_id)

    @app.get("/api/projects/{project_id}/branches")
    async def project_branches(project_id: int) -> list[dict[str, Any]]:
        return projects.branches(project_id)

    @app.get("/api/projects/{project_id}/branches/detail")
    async def project_branch(project_id: int, branch_name: str = Query(..., min_length=1, max_length=1024)) -> dict[str, Any]:
        return projects.branch(project_id, branch_name)

    @app.get("/api/projects/{project_id}/worktrees")
    async def project_worktrees(project_id: int) -> list[dict[str, Any]]:
        return projects.snapshot(project_id)["worktrees"]

    @app.get("/api/projects/{project_id}/graph")
    async def project_graph(project_id: int, scope: str = Query("focus", max_length=16)) -> dict[str, Any]:
        return await projects.graph(project_id, scope)

    @app.get("/api/projects/{project_id}/events")
    async def project_events(project_id: int, limit: int = Query(100, ge=1, le=200)) -> list[dict[str, Any]]:
        return projects.project_events(project_id, limit)

    @app.get("/api/projects/{project_id}/alerts")
    async def project_alerts(project_id: int) -> list[dict[str, Any]]:
        return projects.project_alerts(project_id)

    @app.get("/api/projects/{project_id}/status-metadata")
    async def get_status_metadata(project_id: int) -> dict[str, Any]:
        return projects.status_metadata(project_id)

    @app.put("/api/projects/{project_id}/status-metadata")
    async def put_status_metadata(project_id: int, payload: StatusMetadata) -> dict[str, Any]:
        return await projects.write_metadata(project_id, payload)

    @app.put("/api/projects/{project_id}/branch-status")
    async def put_branch_status(project_id: int, payload: BranchStatusUpdate) -> dict[str, Any]:
        return await projects.write_branch_status(project_id, payload.branch_name, payload.data)

    @app.post("/api/actions/open-folder")
    async def open_folder(payload: ActionRequest) -> dict[str, Any]:
        return actions.open_folder(payload.project_id, payload.path)

    @app.post("/api/actions/open-terminal")
    async def open_terminal(payload: ActionRequest) -> dict[str, Any]:
        return actions.open_terminal(payload.project_id, payload.path)

    @app.post("/api/actions/open-vscode")
    async def open_vscode(payload: ActionRequest) -> dict[str, Any]:
        return actions.open_vscode(payload.project_id, payload.path)

    @app.post("/api/actions/copy-summary")
    async def copy_summary(payload: ActionRequest) -> dict[str, Any]:
        if not payload.branch_name:
            raise HTTPException(status_code=422, detail="必须提供 branch_name")
        branch = projects.branch(payload.project_id, payload.branch_name)
        task = branch.get("task") or {}
        dirty = sum(branch.get(key, 0) for key in ("modified_count", "added_count", "deleted_count", "untracked_count"))
        summary = "\n".join(
            [
                f"分支：{branch['name']}",
                f"类型：{branch['branch_type']}",
                f"任务：{task.get('task_name') or '未维护'}",
                f"状态：{task.get('status') or branch['status']}",
                f"结果：{task.get('result', 'UNKNOWN')}",
                f"整体进度：{str(task.get('progress')) + '%' if task.get('progress') is not None else '未维护'}",
                f"HEAD：{branch['head_sha'][:8]}",
                f"同步：ahead {branch.get('ahead', 'UNKNOWN')} / behind {branch.get('behind', 'UNKNOWN')}",
                f"工作区：{'Modified' if dirty else 'Clean'}（{dirty} files）",
                f"下一步：{(task.get('next_actions') or ['未维护'])[0]}",
            ]
        )
        return {"summary": summary}

    @app.websocket("/ws/projects/{project_id}")
    async def project_socket(websocket: WebSocket, project_id: int):
        origin = websocket.headers.get("origin")
        if origin:
            try:
                normalized_origin = normalize_origin(origin)
            except ValueError:
                normalized_origin = ""
            if normalized_origin not in allowed_origins:
                await websocket.close(code=4403)
                return
        if database.get_project(project_id) is None:
            await websocket.close(code=4404)
            return
        if not await sockets.connect(project_id, websocket):
            return
        last_message_at = 0.0
        try:
            await asyncio.wait_for(
                websocket.send_json({"type": "connected", "project_id": project_id}),
                timeout=1.0,
            )
            while True:
                message = await asyncio.wait_for(websocket.receive(), timeout=45.0)
                if message["type"] == "websocket.disconnect":
                    break
                text_message = message.get("text")
                now = time.monotonic()
                if text_message is None or len(text_message.encode("utf-8")) > 64:
                    await websocket.close(code=4400)
                    break
                if last_message_at and now - last_message_at < 0.1:
                    await websocket.close(code=4429)
                    break
                last_message_at = now
                if text_message != "ping":
                    await websocket.close(code=4400)
                    break
                await websocket.send_json({"type": "pong", "project_id": project_id})
        except asyncio.TimeoutError:
            await websocket.close(code=4408)
        except WebSocketDisconnect:
            pass
        finally:
            await sockets.disconnect(project_id, websocket)

    frontend = resolved.frontend_dist
    assets = frontend / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def frontend_fallback(full_path: str):
        if full_path.startswith(("api/", "ws/")):
            raise HTTPException(status_code=404, detail="Not found")
        index = frontend / "index.html"
        if index.exists():
            return FileResponse(index)
        raise HTTPException(status_code=503, detail="前端尚未构建，请先执行 install.bat")

    return app


app = create_app()
