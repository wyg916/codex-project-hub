from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from backend.app.services.project_service import ProjectService
from backend.app.core.path_safety import is_unc_or_device_path


IGNORED_WORKTREE_PARTS = {
    ".venv", "node_modules", "dist", "build", "coverage", ".pytest_cache",
    ".mypy_cache", "__pycache__", ".gradle", ".idea", ".vscode", ".git",
}


class _DebouncedHandler(FileSystemEventHandler):
    def __init__(
        self,
        project_id: int,
        loop: asyncio.AbstractEventLoop,
        callback: Callable[[int], None],
        git_metadata: bool,
    ):
        self.project_id = project_id
        self.loop = loop
        self.callback = callback
        self.git_metadata = git_metadata

    def on_any_event(self, event: FileSystemEvent) -> None:  # type: ignore[override]
        if event.is_directory:
            return
        if self.git_metadata:
            source = Path(event.src_path)
            destination = Path(getattr(event, "dest_path", "")) if getattr(event, "dest_path", "") else None
            if not self._is_meaningful_git_path(source, destination):
                return
        else:
            parts = {part.lower() for part in Path(event.src_path).parts}
            if parts & IGNORED_WORKTREE_PARTS:
                return
        self.loop.call_soon_threadsafe(self.callback, self.project_id)

    @staticmethod
    def _is_meaningful_git_path(source: Path, destination: Path | None) -> bool:
        if source.name.lower().endswith(".lock"):
            if destination:
                destination_parts = {part.lower() for part in destination.parts}
                return bool({"refs", "logs"} & destination_parts) or destination.name.lower() in {"head", "packed-refs"}
            return False
        candidates = [destination, source] if destination else [source]
        for path in candidates:
            if path is None:
                continue
            parts = {part.lower() for part in path.parts}
            name = path.name.lower()
            if "codex-dashboard" in parts:
                return name == "status.json"
            if {"refs", "logs"} & parts:
                return True
            if name in {"head", "packed-refs", "config", "commondir", "gitdir"}:
                return True
        return False


class WatcherCoordinator:
    def __init__(self, service: ProjectService, debounce_seconds: float = 1.0, max_debounce_seconds: float = 2.0):
        self.service = service
        self.debounce_seconds = max(0.01, debounce_seconds)
        self.max_debounce_seconds = max(self.debounce_seconds, max_debounce_seconds)
        self.observer = Observer(timeout=1)
        self.watches: dict[tuple[int, str], object] = {}
        self.watch_modes: dict[tuple[int, str], bool] = {}
        self.loop: asyncio.AbstractEventLoop | None = None
        self.debounce_tasks: dict[int, asyncio.Task[None]] = {}
        self.pending_refreshes: set[int] = set()

    def start(self) -> None:
        self.loop = asyncio.get_running_loop()
        self.observer.start()
        self.sync()

    def sync(self) -> None:
        if self.loop is None:
            return
        projects = self.service.database.list_projects()
        desired: dict[tuple[int, str], bool] = {}
        for project in projects:
            snapshot = self.service.database.get_snapshot(project["id"]) or {}
            raw_paths = [
                (project["git_common_dir"], True),
                (project["canonical_worktree"], False),
                *((item["path"], False) for item in snapshot.get("worktrees", [])),
            ]
            for raw_path, git_metadata in raw_paths:
                if is_unc_or_device_path(raw_path):
                    continue
                path = Path(raw_path)
                if not path.exists():
                    continue
                try:
                    key = (project["id"], str(path.resolve(strict=True)))
                except OSError:
                    continue
                desired[key] = desired.get(key, False) or git_metadata
        stale_keys = [
            key
            for key in self.watches
            if key not in desired or self.watch_modes.get(key) != desired[key]
        ]
        for key in stale_keys:
            watch = self.watches.pop(key)
            self.watch_modes.pop(key, None)
            try:
                self.observer.unschedule(watch)  # type: ignore[arg-type]
            except KeyError:
                pass
        for key, git_metadata in desired.items():
            if key in self.watches:
                continue
            project_id, resolved_path = key
            handler = _DebouncedHandler(project_id, self.loop, self._queue_refresh, git_metadata)
            try:
                watch = self.observer.schedule(handler, resolved_path, recursive=True)
            except (OSError, RuntimeError):
                continue
            self.watches[key] = watch
            self.watch_modes[key] = git_metadata

    def _queue_refresh(self, project_id: int) -> None:
        self.pending_refreshes.add(project_id)
        previous = self.debounce_tasks.get(project_id)
        if previous and not previous.done():
            return
        self.debounce_tasks[project_id] = asyncio.create_task(self._refresh(project_id))

    async def _refresh(self, project_id: int) -> None:
        loop = asyncio.get_running_loop()
        try:
            while project_id in self.pending_refreshes:
                burst_started = loop.time()
                while True:
                    self.pending_refreshes.discard(project_id)
                    await asyncio.sleep(self.debounce_seconds)
                    if project_id not in self.pending_refreshes or loop.time() - burst_started >= self.max_debounce_seconds:
                        break
                await self.service.refresh(project_id, event_type="watchdog")
        except asyncio.CancelledError:
            return

    def stop(self) -> None:
        for task in self.debounce_tasks.values():
            task.cancel()
        self.pending_refreshes.clear()
        self.observer.stop()
        self.observer.join(timeout=5)


class PollingService:
    """Poll viewed projects frequently and background projects at a bounded cadence."""

    def __init__(self, service: ProjectService, watcher: WatcherCoordinator, interval: float):
        self.service = service
        self.watcher = watcher
        self.active_interval = max(2.0, interval)
        self.background_interval = max(20.0, interval * 5)
        self._stop = asyncio.Event()
        self._last_started: dict[int, float] = {}
        self._last_watcher_sync = 0.0

    async def run(self) -> None:
        while not self._stop.is_set():
            now = time.monotonic()
            if now - self._last_watcher_sync >= 5:
                self.watcher.sync()
                self._last_watcher_sync = now
            due: list[dict] = []
            for project in self.service.database.list_projects():
                interval = self.active_interval if self.service.sockets.has_connections(project["id"]) else self.background_interval
                last = self._last_started.setdefault(project["id"], now)
                if now - last >= interval:
                    self._last_started[project["id"]] = now
                    due.append(project)
            if due:
                await asyncio.gather(
                    *(self.service.refresh(project["id"], event_type="poll") for project in due),
                    return_exceptions=True,
                )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=1.0)
            except TimeoutError:
                pass

    def stop(self) -> None:
        self._stop.set()
