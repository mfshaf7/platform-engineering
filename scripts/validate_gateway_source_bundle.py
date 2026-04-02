#!/usr/bin/env python3
import argparse
from pathlib import Path
import sys


LEGACY_TELEGRAM_IMPORT = 'from "openclaw/plugin-sdk/telegram"'
EXPORT_PATCH_MARKER = 'pkg.exports["./plugin-sdk/telegram"]'
EXPORT_TARGET_MARKER = '"./dist/plugin-sdk/telegram.js"'


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
    dockerfile = read_text(args.deployment_repo / "deployment" / "Dockerfile.telegram-bundled.example")

    uses_legacy_sdk_export = LEGACY_TELEGRAM_IMPORT in runtime_api
    has_export_patch = EXPORT_PATCH_MARKER in dockerfile and EXPORT_TARGET_MARKER in dockerfile

    if uses_legacy_sdk_export and not has_export_patch:
        print(
            "Incompatible gateway source bundle: Telegram runtime-api imports "
            '"openclaw/plugin-sdk/telegram" but the deployment Dockerfile does not patch '
            "the matching ./plugin-sdk/telegram package export into /app/package.json.",
            file=sys.stderr,
        )
        return 1

    print(
        "Gateway source bundle compatible: "
        f"legacy_telegram_sdk_import={str(uses_legacy_sdk_export).lower()} "
        f"dockerfile_export_patch={str(has_export_patch).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
