from __future__ import annotations

import re
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]
DEV_REQUIREMENTS = ROOT / "backend" / "requirements-dev.txt"
LOCK_PATH = ROOT / "backend" / "pylock.toml"
PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[A-Za-z0-9_,.-]+\])?==([^\s]+)$")


def canonicalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def direct_pins(path: Path, visited: set[Path] | None = None) -> dict[str, str]:
    seen = visited if visited is not None else set()
    resolved = path.resolve(strict=True)
    if resolved in seen:
        raise ValueError("recursive requirements include")
    seen.add(resolved)
    pins: dict[str, str] = {}
    for raw_line in resolved.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(("-r ", "--requirement ")):
            included = line.split(maxsplit=1)[1]
            pins.update(direct_pins(resolved.parent / included, seen))
            continue
        match = PIN.fullmatch(line)
        if not match:
            raise ValueError("requirements must contain only exact pins and local includes")
        name, version = canonicalize(match.group(1)), match.group(2)
        if name in pins and pins[name] != version:
            raise ValueError("conflicting direct requirement pins")
        pins[name] = version
    return pins


def main() -> int:
    lock = tomllib.loads(LOCK_PATH.read_text(encoding="utf-8"))
    packages = lock.get("packages")
    if lock.get("lock-version") != "1.0" or not isinstance(packages, list) or not packages:
        raise SystemExit("PYTHON_LOCK_STATUS=FAIL invalid PEP 751 lock")
    locked: dict[str, str] = {}
    wheel_count = 0
    for package in packages:
        name = canonicalize(str(package.get("name", "")))
        version = str(package.get("version", ""))
        wheels = package.get("wheels")
        if not name or not version or "sdist" in package or not isinstance(wheels, list) or not wheels:
            raise SystemExit("PYTHON_LOCK_STATUS=FAIL package is not wheel-locked")
        if name in locked:
            raise SystemExit("PYTHON_LOCK_STATUS=FAIL duplicate canonical package name")
        locked[name] = version
        for wheel in wheels:
            filename = wheel.get("name")
            url = wheel.get("url")
            if not isinstance(filename, str) or not filename.endswith(".whl") or not isinstance(url, str):
                raise SystemExit("PYTHON_LOCK_STATUS=FAIL wheel filename or URL missing")
            parsed = urlsplit(url)
            if (
                parsed.scheme != "https"
                or parsed.hostname != "files.pythonhosted.org"
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or Path(unquote(parsed.path)).name != filename
            ):
                raise SystemExit("PYTHON_LOCK_STATUS=FAIL wheel URL is not an official PyPI artifact")
            digest = (wheel.get("hashes") or {}).get("sha256")
            if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
                raise SystemExit("PYTHON_LOCK_STATUS=FAIL wheel hash missing")
            wheel_count += 1
    pins = direct_pins(DEV_REQUIREMENTS)
    mismatches = {
        name: version
        for name, version in pins.items()
        if locked.get(name) != version
    }
    if mismatches:
        raise SystemExit("PYTHON_LOCK_STATUS=FAIL direct pins differ from lock")
    print(
        f"PYTHON_LOCK_STATUS=PASS direct={len(pins)} "
        f"packages={len(locked)} hashed_wheels={wheel_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
