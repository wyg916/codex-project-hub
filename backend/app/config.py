from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


ROOT_DIR = Path(__file__).resolve().parents[2]
APP_VERSION = "0.1.0"
SERVICE_NAME = "codex-project-hub"
DEFAULT_ALLOWED_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
    "http://127.0.0.1:8765",
    "http://localhost:8765",
)
DEFAULT_ALLOWED_HOSTS = ("127.0.0.1", "localhost", "[::1]")


def normalize_origin(value: str) -> str:
    """Return a canonical, explicit HTTP(S) origin or reject it."""
    candidate = value.strip()
    parsed = urlsplit(candidate)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("CPC_ALLOWED_ORIGINS 仅接受明确的 HTTP(S) Origin")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("CPC_ALLOWED_ORIGINS 包含无效端口") from exc
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    authority = f"{host}:{port}" if port is not None else host
    return f"{parsed.scheme.lower()}://{authority}"


def _allowed_origins_from_env() -> tuple[str, ...]:
    configured = os.getenv("CPC_ALLOWED_ORIGINS", "")
    additions = tuple(normalize_origin(item) for item in configured.split(",") if item.strip())
    return tuple(dict.fromkeys((*DEFAULT_ALLOWED_ORIGINS, *additions)))


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_path: Path
    frontend_dist: Path
    scan_interval_seconds: float
    allowed_origins: tuple[str, ...] = DEFAULT_ALLOWED_ORIGINS
    allowed_hosts: tuple[str, ...] = DEFAULT_ALLOWED_HOSTS
    system_actions_enabled: bool = False


def get_settings() -> Settings:
    data_dir = Path(os.getenv("CPC_DATA_DIR", str(ROOT_DIR / "data"))).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    interval = float(os.getenv("CPC_SCAN_INTERVAL", "4"))
    return Settings(
        data_dir=data_dir,
        database_path=data_dir / "control-center.db",
        frontend_dist=ROOT_DIR / "frontend" / "dist",
        scan_interval_seconds=max(1.0, interval),
        allowed_origins=_allowed_origins_from_env(),
        system_actions_enabled=os.getenv("CPC_ENABLE_SYSTEM_ACTIONS") == "1",
    )
