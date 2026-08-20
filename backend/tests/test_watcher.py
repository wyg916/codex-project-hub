import asyncio
from pathlib import Path

from backend.app.core.watcher import WatcherCoordinator, _DebouncedHandler


def test_watcher_filters_git_lock_and_internal_event_feedback() -> None:
    assert _DebouncedHandler._is_meaningful_git_path(Path("repo/.git/index.lock"), None) is False
    assert _DebouncedHandler._is_meaningful_git_path(Path("repo/.git/index"), None) is False
    assert _DebouncedHandler._is_meaningful_git_path(Path("repo/.git/codex-dashboard/events.jsonl"), None) is False
    assert _DebouncedHandler._is_meaningful_git_path(Path("repo/.git/codex-dashboard/status.json"), None) is True
    assert _DebouncedHandler._is_meaningful_git_path(Path("repo/.git/refs/heads/main"), None) is True
    assert _DebouncedHandler._is_meaningful_git_path(
        Path("repo/.git/refs/heads/main.lock"), Path("repo/.git/refs/heads/main")
    ) is True
    assert _DebouncedHandler._is_meaningful_git_path(
        Path("repo/.git/index.lock"), Path("repo/.git/index")
    ) is False


def test_watcher_coalesces_bursts_without_cancelling_active_refresh() -> None:
    class FakeService:
        def __init__(self) -> None:
            self.calls = 0
            self.first_started = asyncio.Event()
            self.release_first = asyncio.Event()

        async def refresh(self, project_id: int, event_type: str) -> None:
            assert project_id == 7
            assert event_type == "watchdog"
            self.calls += 1
            if self.calls == 1:
                self.first_started.set()
                await self.release_first.wait()

    async def scenario() -> None:
        service = FakeService()
        coordinator = WatcherCoordinator(service, debounce_seconds=0.01, max_debounce_seconds=0.02)  # type: ignore[arg-type]
        coordinator._queue_refresh(7)
        coordinator._queue_refresh(7)
        await asyncio.wait_for(service.first_started.wait(), timeout=0.2)
        coordinator._queue_refresh(7)
        service.release_first.set()
        task = coordinator.debounce_tasks[7]
        await asyncio.wait_for(task, timeout=0.3)
        assert service.calls == 2

    asyncio.run(scenario())


def test_watcher_sync_removes_paths_no_longer_in_desired_set(tmp_path: Path) -> None:
    common = tmp_path / "common"
    canonical_one = tmp_path / "canonical-one"
    canonical_two = tmp_path / "canonical-two"
    worktree_one = tmp_path / "worktree-one"
    worktree_two = tmp_path / "worktree-two"
    for path in (common, canonical_one, canonical_two, worktree_one, worktree_two):
        path.mkdir()

    class FakeDatabase:
        canonical = canonical_one
        worktree = worktree_one

        def list_projects(self):
            return [
                {
                    "id": 1,
                    "git_common_dir": str(common),
                    "canonical_worktree": str(self.canonical),
                }
            ]

        def get_snapshot(self, project_id):
            assert project_id == 1
            return {"worktrees": [{"path": str(self.worktree)}]}

    class FakeService:
        database = FakeDatabase()

    class FakeObserver:
        def __init__(self):
            self.unscheduled: list[object] = []

        def schedule(self, _handler, path, recursive):
            assert recursive is True
            return f"watch:{path}"

        def unschedule(self, watch):
            self.unscheduled.append(watch)

    async def scenario() -> None:
        coordinator = WatcherCoordinator(FakeService())  # type: ignore[arg-type]
        observer = FakeObserver()
        coordinator.observer = observer  # type: ignore[assignment]
        coordinator.loop = asyncio.get_running_loop()
        coordinator.sync()
        assert {key[1] for key in coordinator.watches} == {
            str(common.resolve()),
            str(canonical_one.resolve()),
            str(worktree_one.resolve()),
        }

        FakeService.database.canonical = canonical_two
        FakeService.database.worktree = worktree_two
        coordinator.sync()
        assert {key[1] for key in coordinator.watches} == {
            str(common.resolve()),
            str(canonical_two.resolve()),
            str(worktree_two.resolve()),
        }
        assert set(observer.unscheduled) == {
            f"watch:{canonical_one.resolve()}",
            f"watch:{worktree_one.resolve()}",
        }

    asyncio.run(scenario())


def test_watcher_sync_isolates_unwatchable_path_and_registers_others(tmp_path: Path) -> None:
    common = tmp_path / "unwatchable-common"
    canonical = tmp_path / "canonical"
    worktree = tmp_path / "worktree"
    for path in (common, canonical, worktree):
        path.mkdir()

    class FakeDatabase:
        def list_projects(self):
            return [{"id": 1, "git_common_dir": str(common), "canonical_worktree": str(canonical)}]

        def get_snapshot(self, _project_id):
            return {"worktrees": [{"path": str(worktree)}]}

    class FakeService:
        database = FakeDatabase()

    class FakeObserver:
        def __init__(self):
            self.attempted: list[str] = []

        def schedule(self, _handler, path, recursive):
            assert recursive is True
            self.attempted.append(path)
            if path == str(common.resolve()):
                raise OSError("watch unavailable")
            return f"watch:{path}"

    async def scenario() -> None:
        coordinator = WatcherCoordinator(FakeService())  # type: ignore[arg-type]
        observer = FakeObserver()
        coordinator.observer = observer  # type: ignore[assignment]
        coordinator.loop = asyncio.get_running_loop()
        coordinator.sync()
        assert set(observer.attempted) == {
            str(common.resolve()),
            str(canonical.resolve()),
            str(worktree.resolve()),
        }
        assert {key[1] for key in coordinator.watches} == {
            str(canonical.resolve()),
            str(worktree.resolve()),
        }
        coordinator.sync()
        assert observer.attempted.count(str(common.resolve())) == 2
        assert {key[1] for key in coordinator.watches} == {
            str(canonical.resolve()),
            str(worktree.resolve()),
        }

    asyncio.run(scenario())
