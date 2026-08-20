from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.bootstrap import bootstrap_projects
from backend.app.config import get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="幂等登记一键启动所需的默认项目")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--database", type=Path)
    args = parser.parse_args()

    database_path = args.database or get_settings().database_path
    try:
        result = asyncio.run(bootstrap_projects(args.config.resolve(), database_path.resolve()))
    except ValueError as exc:
        print(f"PROJECT_REGISTRATION_STATUS=FAIL detail={exc}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        f"PROJECT_REGISTRATION_STATUS={result['status']} "
        f"registered={result['registered']}/{result['configured']} failed={result['failed']}"
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
