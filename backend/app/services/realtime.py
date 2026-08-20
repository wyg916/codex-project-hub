from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from fastapi import WebSocket


MAX_CONNECTIONS_PER_PROJECT = 8
MAX_CONNECTIONS_TOTAL = 32
WEBSOCKET_SEND_TIMEOUT_SECONDS = 1.0


class WebSocketManager:
    def __init__(
        self,
        max_per_project: int = MAX_CONNECTIONS_PER_PROJECT,
        max_total: int = MAX_CONNECTIONS_TOTAL,
        send_timeout: float = WEBSOCKET_SEND_TIMEOUT_SECONDS,
    ) -> None:
        self.connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        self.max_per_project = max(1, max_per_project)
        self.max_total = max(self.max_per_project, max_total)
        self.send_timeout = max(0.05, send_timeout)

    async def connect(self, project_id: int, websocket: WebSocket) -> bool:
        await websocket.accept()
        accepted = False
        async with self._lock:
            total = sum(len(group) for group in self.connections.values())
            if len(self.connections[project_id]) < self.max_per_project and total < self.max_total:
                self.connections[project_id].add(websocket)
                accepted = True
        if not accepted:
            await websocket.close(code=4429)
        return accepted

    async def disconnect(self, project_id: int, websocket: WebSocket) -> None:
        async with self._lock:
            self.connections[project_id].discard(websocket)

    def has_connections(self, project_id: int) -> bool:
        return bool(self.connections.get(project_id))

    async def broadcast(self, project_id: int, message: dict[str, Any]) -> None:
        targets = list(self.connections.get(project_id, set()))

        async def send(websocket: WebSocket) -> WebSocket | None:
            try:
                await asyncio.wait_for(websocket.send_json(message), timeout=self.send_timeout)
                return None
            except Exception:
                return websocket

        stale = [websocket for websocket in await asyncio.gather(*(send(item) for item in targets)) if websocket]
        if stale:
            async with self._lock:
                for websocket in stale:
                    self.connections[project_id].discard(websocket)
