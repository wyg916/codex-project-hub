from __future__ import annotations

import asyncio

from backend.app.services.realtime import WebSocketManager


class FakeWebSocket:
    def __init__(self, *, slow: bool = False) -> None:
        self.slow = slow
        self.accepted = False
        self.closed_code: int | None = None
        self.messages: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def close(self, code: int) -> None:
        self.closed_code = code

    async def send_json(self, message: dict) -> None:
        if self.slow:
            await asyncio.sleep(1)
        self.messages.append(message)


def test_websocket_manager_limits_connections_and_evicts_slow_clients() -> None:
    async def scenario() -> None:
        manager = WebSocketManager(max_per_project=2, max_total=3, send_timeout=0.01)
        first = FakeWebSocket()
        second = FakeWebSocket(slow=True)
        rejected = FakeWebSocket()

        assert await manager.connect(1, first) is True  # type: ignore[arg-type]
        assert await manager.connect(1, second) is True  # type: ignore[arg-type]
        assert await manager.connect(1, rejected) is False  # type: ignore[arg-type]
        assert rejected.closed_code == 4429

        await manager.broadcast(1, {"type": "snapshot.updated"})

        assert first.messages == [{"type": "snapshot.updated"}]
        assert second not in manager.connections[1]

    asyncio.run(scenario())
