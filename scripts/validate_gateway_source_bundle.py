#!/usr/bin/env python3
import argparse
from pathlib import Path
import re
import sys


LEGACY_TELEGRAM_IMPORT = 'from "openclaw/plugin-sdk/telegram"'
UNSUPPORTED_TELEGRAM_CORE_IMPORT = 'from "openclaw/plugin-sdk/telegram-core"'
WRONG_HOST_CONTROL_HELPER_IMPORT_RE = re.compile(
    r'import\s*\{[^}]*appendHostControlTopicSystemPrompt[^}]*\}\s*from\s*"\./bot/helpers\.js";',
    re.DOTALL,
)
EXPECTED_BUILD_DOCKERFILE = 'deployment/Dockerfile.plugin-install.example'
DISALLOWED_BUNDLED_COPY_SNIPPETS = (
    'COPY openclaw-telegram-enhanced/ /app/extensions/telegram/',
    'COPY host-control-openclaw-plugin/ /app/extensions/host-control/',
)


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing required file: {path}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that the pinned Telegram and deployment sources produce a compatible managed-plugin gateway image."
    )
    parser.add_argument("--telegram-repo", required=True, type=Path)
    parser.add_argument("--deployment-repo", required=True, type=Path)
    args = parser.parse_args()

    runtime_api = read_text(args.telegram_repo / "runtime-api.ts")
    package_json = read_text(args.telegram_repo / "package.json")
    bot_message_context = read_text(args.telegram_repo / "src" / "bot-message-context.session.ts")
    build_openclaw_local = read_text(args.deployment_repo / "deployment" / "build-openclaw-local.sh")
    plugin_dockerfile_path = args.deployment_repo / EXPECTED_BUILD_DOCKERFILE
    plugin_dockerfile = read_text(plugin_dockerfile_path)
    package_plugins_script = read_text(args.deployment_repo / "deployment" / "package-local-plugins.sh")
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
    uses_unsupported_telegram_core_import = UNSUPPORTED_TELEGRAM_CORE_IMPORT in runtime_api
    uses_wrong_host_control_helper_import = bool(
        WRONG_HOST_CONTROL_HELPER_IMPORT_RE.search(bot_message_context)
    )
    has_plugin_compat_metadata = '"compat"' in package_json and '"build"' in package_json
    uses_managed_plugin_build = EXPECTED_BUILD_DOCKERFILE in build_openclaw_local
    dockerfile_still_copies_bundled_sources = any(snippet in plugin_dockerfile for snippet in DISALLOWED_BUNDLED_COPY_SNIPPETS)
    package_script_packs_plugins = 'npm pack' in package_plugins_script and 'openclaw-telegram-enhanced' in package_plugins_script and 'host-control-openclaw-plugin' in package_plugins_script

    if uses_legacy_sdk_export:
        print(
            'Incompatible gateway source bundle: Telegram runtime-api still imports '
            '"openclaw/plugin-sdk/telegram", but the governed upstream runtime currently advertises '
            'that export without consistently shipping the backing dist/plugin-sdk/telegram.js file. '
            'Import only stable public subpaths such as core/channel-actions/channel-status/channel-config-schema instead.',
            file=sys.stderr,
        )
        return 1

    if uses_unsupported_telegram_core_import:
        print(
            'Incompatible gateway source bundle: Telegram runtime-api still imports '
            '"openclaw/plugin-sdk/telegram-core", which is not a public package export in the governed runtime. '
            'Use stable public subpaths and local helpers for any Telegram-only seams that are not exported yet.',
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

    if not has_plugin_compat_metadata:
        print(
            'Incompatible gateway source bundle: Telegram package.json is missing OpenClaw compat/build metadata required for publishable managed plugin packages.',
            file=sys.stderr,
        )
        return 1

    if not uses_managed_plugin_build:
        print(
            f'Incompatible gateway source bundle: deployment/build-openclaw-local.sh must default to {EXPECTED_BUILD_DOCKERFILE} so builds use managed plugin installation instead of bundled source copies.',
            file=sys.stderr,
        )
        return 1

    if dockerfile_still_copies_bundled_sources:
        print(
            'Incompatible gateway source bundle: managed plugin Dockerfile still copies Telegram or host-control source directly into /app/extensions. Package plugins and install them with openclaw plugins install instead.',
            file=sys.stderr,
        )
        return 1

    if not package_script_packs_plugins:
        print(
            'Incompatible gateway source bundle: deployment/package-local-plugins.sh must package both Telegram and host-control with npm pack before the gateway image build.',
            file=sys.stderr,
        )
        return 1

    if not security_arch_agents.exists() or not security_arch_skill.exists():
        print(
            "Incompatible gateway source bundle: deployment is missing the tracked "
            "security-architecture workspace template required to materialize "
            "/home/node/.openclaw/workspace-security-architecture in the runtime.",
            file=sys.stderr,
        )
        return 1

    print(
        "Gateway source bundle compatible: "
        "legacy_telegram_sdk_import="
        f"{str(uses_legacy_sdk_export).lower()} "
        "unsupported_telegram_core_import="
        f"{str(uses_unsupported_telegram_core_import).lower()} "
        "wrong_host_control_helper_import="
        f"{str(uses_wrong_host_control_helper_import).lower()} "
        "plugin_compat_metadata="
        f"{str(has_plugin_compat_metadata).lower()} "
        "managed_plugin_build="
        f"{str(uses_managed_plugin_build).lower()} "
        "security_arch_workspace_template="
        f"{str(security_arch_agents.exists() and security_arch_skill.exists()).lower()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
