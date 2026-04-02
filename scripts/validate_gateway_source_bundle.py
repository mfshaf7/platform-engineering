#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys


LEGACY_TELEGRAM_IMPORT = 'from "openclaw/plugin-sdk/telegram"'


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing required file: {path}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that the pinned Telegram and deployment sources produce a compatible bundled gateway image."
    )
    parser.add_argument("--telegram-repo", required=True, type=Path)
    parser.add_argument("--deployment-repo", required=True, type=Path)
    args = parser.parse_args()

    runtime_api = read_text(args.telegram_repo / "runtime-api.ts")
    uses_legacy_sdk_export = LEGACY_TELEGRAM_IMPORT in runtime_api

    if uses_legacy_sdk_export:
        print(
            "Incompatible gateway source bundle: Telegram runtime-api still imports "
            '"openclaw/plugin-sdk/telegram", but the governed upstream runtime does not ship '
            "a stable dist/plugin-sdk/telegram.js entrypoint. Use the newer runtime-api contract "
            'that imports config-runtime/channel-contract/core/telegram-core instead.',
            file=sys.stderr,
        )
        return 1

    print(
        "Gateway source bundle compatible: "
        f"legacy_telegram_sdk_import={str(uses_legacy_sdk_export).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
