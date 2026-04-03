#!/usr/bin/env python3
import argparse
from pathlib import Path
import re
import sys


LEGACY_TELEGRAM_IMPORT = 'from "openclaw/plugin-sdk/telegram"'
WRONG_HOST_CONTROL_HELPER_IMPORT_RE = re.compile(
    r'import\s*\{[^}]*appendHostControlTopicSystemPrompt[^}]*\}\s*from\s*"\./bot/helpers\.js";',
    re.DOTALL,
)


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
    bot_message_context = read_text(args.telegram_repo / "src" / "bot-message-context.session.ts")
    security_arch_agents = args.deployment_repo / "deployment" / "workspaces" / "security-architecture" / "AGENTS.md"
    security_arch_skill = (
        args.deployment_repo
        / "deployment"
        / "workspaces"
        / "security-architecture"
        / "skills"
        / "security-architecture"
        / "SKILL.md"
    )
    uses_legacy_sdk_export = LEGACY_TELEGRAM_IMPORT in runtime_api
    uses_wrong_host_control_helper_import = bool(
        WRONG_HOST_CONTROL_HELPER_IMPORT_RE.search(bot_message_context)
    )

    if uses_legacy_sdk_export:
        print(
            "Incompatible gateway source bundle: Telegram runtime-api still imports "
            '"openclaw/plugin-sdk/telegram", but the governed upstream runtime does not ship '
            "a stable dist/plugin-sdk/telegram.js entrypoint. Use the newer runtime-api contract "
            'that imports config-runtime/channel-contract/core/telegram-core instead.',
            file=sys.stderr,
        )
        return 1

    if uses_wrong_host_control_helper_import:
        print(
            "Incompatible gateway source bundle: bot-message-context.session.ts imports "
            "appendHostControlTopicSystemPrompt from ./bot/helpers.js, but that helper is "
            "exported by ./group-config-helpers.js. This ships a runtime TypeError when "
            "Telegram processes host-control topic messages.",
            file=sys.stderr,
        )
        return 1

    if not security_arch_agents.exists() or not security_arch_skill.exists():
        print(
            "Incompatible gateway source bundle: deployment is missing the tracked "
            "security-architecture workspace template required to materialize "
            "/home/node/.openclaw/workspace-security-architecture in the bundled runtime.",
            file=sys.stderr,
        )
        return 1

    print(
        "Gateway source bundle compatible: "
        "legacy_telegram_sdk_import="
        f"{str(uses_legacy_sdk_export).lower()} "
        "wrong_host_control_helper_import="
        f"{str(uses_wrong_host_control_helper_import).lower()} "
        "security_arch_workspace_template="
        f"{str(security_arch_agents.exists() and security_arch_skill.exists()).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
