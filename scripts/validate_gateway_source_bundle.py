#!/usr/bin/env python3
import argparse
import json
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
        return path.read_text(encoding='utf-8')
    except FileNotFoundError as exc:
        raise SystemExit(f'Missing required file: {path}') from exc


def read_json(path: Path) -> dict:
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        raise SystemExit(f'Invalid JSON in required file {path}: {exc}') from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Validate that the pinned Telegram and deployment sources produce a compatible managed-plugin gateway image.'
    )
    parser.add_argument('--telegram-repo', required=True, type=Path)
    parser.add_argument('--deployment-repo', required=True, type=Path)
    args = parser.parse_args()

    runtime_api = read_text(args.telegram_repo / 'runtime-api.ts')
    telegram_package = read_json(args.telegram_repo / 'package.json')
    bot_message_context = read_text(args.telegram_repo / 'src' / 'bot-message-context.session.ts')
    build_openclaw_local = read_text(args.deployment_repo / 'deployment' / 'build-openclaw-local.sh')
    plugin_dockerfile = read_text(args.deployment_repo / EXPECTED_BUILD_DOCKERFILE)
    package_plugins_script = read_text(args.deployment_repo / 'deployment' / 'package-local-plugins.sh')
    verify_router_contract_script = read_text(args.deployment_repo / 'deployment' / 'verify-telegram-router-contract.sh')
    host_control_package = read_json(args.deployment_repo / 'host-control-openclaw-plugin' / 'package.json')
    security_arch_agents = args.deployment_repo / 'deployment' / 'workspaces' / 'security-architecture' / 'AGENTS.md'
    security_arch_skill = (
        args.deployment_repo
        / 'deployment'
        / 'workspaces'
        / 'security-architecture'
        / 'skills'
        / 'security-architecture'
        / 'SKILL.md'
    )

    uses_legacy_sdk_export = LEGACY_TELEGRAM_IMPORT in runtime_api
    uses_unsupported_telegram_core_import = UNSUPPORTED_TELEGRAM_CORE_IMPORT in runtime_api
    uses_wrong_host_control_helper_import = bool(WRONG_HOST_CONTROL_HELPER_IMPORT_RE.search(bot_message_context))
    telegram_openclaw = telegram_package.get('openclaw', {})
    telegram_files = telegram_package.get('files')
    has_plugin_compat_metadata = isinstance(telegram_openclaw.get('compat'), dict) and isinstance(telegram_openclaw.get('build'), dict)
    telegram_publishable_files = (
        isinstance(telegram_files, list)
        and 'src/' not in telegram_files
        and 'src/**/*.ts' in telegram_files
        and '!src/**/*.test.ts' in telegram_files
        and '!src/**/*test-helpers.ts' in telegram_files
        and '!src/**/*test-support.ts' in telegram_files
        and '!src/**/*test-utils.ts' in telegram_files
        and '!src/**/*test-harness.ts' in telegram_files
        and '!src/**/*fixture-test-support.ts' in telegram_files
        and '!src/**/*e2e.test.ts' in telegram_files
        and '!src/**/*e2e-harness.ts' in telegram_files
        and '!src/**/*.d.ts' in telegram_files
    )

    uses_managed_plugin_build = EXPECTED_BUILD_DOCKERFILE in build_openclaw_local
    dockerfile_still_copies_bundled_sources = any(snippet in plugin_dockerfile for snippet in DISALLOWED_BUNDLED_COPY_SNIPPETS)
    dockerfile_uses_posix_shell_install = 'RUN set -eu;' in plugin_dockerfile and 'set -euo pipefail' not in plugin_dockerfile
    dockerfile_uses_official_unsafe_install = '--dangerously-force-unsafe-install' in plugin_dockerfile

    package_script_packs_plugins = 'npm pack' in package_plugins_script and 'host-control-openclaw-plugin' in package_plugins_script
    package_script_uses_direct_telegram_source = 'OPENCLAW_TELEGRAM_REPO' in package_plugins_script and '$ROOT/openclaw-telegram-enhanced' not in package_plugins_script and 'sync-telegram-build-copy.sh' not in package_plugins_script
    package_script_guards_packlists = 'npm pack --json --dry-run' in package_plugins_script and 'includes non-runtime files' in package_plugins_script
    verify_router_contract_uses_direct_source = 'CANON_TELEGRAM' in verify_router_contract_script and 'DEPLOY_ROUTER' not in verify_router_contract_script

    host_openclaw = host_control_package.get('openclaw', {})
    host_files = host_control_package.get('files')
    host_control_publishable_metadata = (
        host_control_package.get('private') is False
        and isinstance(host_files, list)
        and 'openclaw.plugin.json' in host_files
        and 'index.mjs' in host_files
        and 'src/' in host_files
        and not any(str(entry).startswith('test') or 'test/' in str(entry) or '.test.' in str(entry) for entry in host_files)
        and isinstance(host_openclaw.get('compat'), dict)
        and isinstance(host_openclaw.get('build'), dict)
    )

    checks = [
        (not uses_legacy_sdk_export, 'Incompatible gateway source bundle: Telegram runtime-api still imports "openclaw/plugin-sdk/telegram". Use only stable public subpaths such as core/channel-actions/channel-status/channel-config-schema instead.'),
        (not uses_unsupported_telegram_core_import, 'Incompatible gateway source bundle: Telegram runtime-api still imports "openclaw/plugin-sdk/telegram-core", which is not a public package export in the governed runtime.'),
        (not uses_wrong_host_control_helper_import, 'Incompatible gateway source bundle: bot-message-context.session.ts still imports appendHostControlTopicSystemPrompt from ./bot/helpers.js instead of ./group-config-helpers.js.'),
        (has_plugin_compat_metadata, 'Incompatible gateway source bundle: Telegram package.json is missing OpenClaw compat/build metadata required for publishable managed plugin packages.'),
        (telegram_publishable_files, 'Incompatible gateway source bundle: Telegram package.json must use an explicit files allowlist that excludes tests, harnesses, helpers, and declaration-only files from the published plugin artifact.'),
        (host_control_publishable_metadata, 'Incompatible gateway source bundle: host-control package.json must be publishable metadata with compat/build entries and a files whitelist that excludes tests.'),
        (uses_managed_plugin_build, f'Incompatible gateway source bundle: deployment/build-openclaw-local.sh must default to {EXPECTED_BUILD_DOCKERFILE} so builds use managed plugin installation instead of bundled source copies.'),
        (not dockerfile_still_copies_bundled_sources, 'Incompatible gateway source bundle: managed plugin Dockerfile still copies Telegram or host-control source directly into /app/extensions.'),
        (dockerfile_uses_posix_shell_install, 'Incompatible gateway source bundle: managed plugin Dockerfile install layer must stay POSIX-sh compatible.'),
        (dockerfile_uses_official_unsafe_install, 'Incompatible gateway source bundle: managed plugin Dockerfile must use OpenClaw official --dangerously-force-unsafe-install flag when installing trusted pinned plugins with network-capable runtime code.'),
        (package_script_packs_plugins, 'Incompatible gateway source bundle: deployment/package-local-plugins.sh must package both Telegram and host-control with npm pack before the gateway image build.'),
        (package_script_uses_direct_telegram_source, 'Incompatible gateway source bundle: deployment/package-local-plugins.sh must package Telegram directly from OPENCLAW_TELEGRAM_REPO and must not rely on a copied tree in isolated-deployment.'),
        (package_script_guards_packlists, 'Incompatible gateway source bundle: deployment/package-local-plugins.sh must dry-run npm pack and block non-runtime files such as tests from entering managed plugin artifacts.'),
        (verify_router_contract_uses_direct_source, 'Incompatible gateway source bundle: verify-telegram-router-contract.sh must validate the standalone Telegram source repo directly, not a copied deployment tree.'),
        (security_arch_agents.exists() and security_arch_skill.exists(), 'Incompatible gateway source bundle: deployment is missing the tracked security-architecture workspace template required to materialize /home/node/.openclaw/workspace-security-architecture in the runtime.'),
    ]

    for ok, message in checks:
        if not ok:
            print(message, file=sys.stderr)
            return 1

    print(
        'Gateway source bundle compatible: '
        f'legacy_telegram_sdk_import={str(uses_legacy_sdk_export).lower()} '
        f'unsupported_telegram_core_import={str(uses_unsupported_telegram_core_import).lower()} '
        f'wrong_host_control_helper_import={str(uses_wrong_host_control_helper_import).lower()} '
        f'plugin_compat_metadata={str(has_plugin_compat_metadata).lower()} '
        f'telegram_publishable_files={str(telegram_publishable_files).lower()} '
        f'host_control_publishable_metadata={str(host_control_publishable_metadata).lower()} '
        f'managed_plugin_build={str(uses_managed_plugin_build).lower()} '
        f'package_script_uses_direct_telegram_source={str(package_script_uses_direct_telegram_source).lower()} '
        f'package_script_guards_packlists={str(package_script_guards_packlists).lower()} '
        f'dockerfile_uses_official_unsafe_install={str(dockerfile_uses_official_unsafe_install).lower()} '
        f'verify_router_contract_uses_direct_source={str(verify_router_contract_uses_direct_source).lower()} '
        f'security_arch_workspace_template={str((security_arch_agents.exists() and security_arch_skill.exists())).lower()}'
    )
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
