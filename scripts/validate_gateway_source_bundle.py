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
DISALLOWED_DIRECT_SOURCE_COPY_SNIPPETS = (
    'COPY openclaw-telegram-enhanced/',
    'COPY host-control-openclaw-plugin/',
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
        description='Validate that the pinned Telegram and runtime-distribution sources produce a compatible bundled-Telegram gateway image.'
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
    telegram_channel = telegram_openclaw.get('channel', {})
    telegram_bundle = telegram_openclaw.get('bundle', {})
    telegram_extensions = telegram_openclaw.get('extensions')
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
    telegram_overlay_metadata = (
        telegram_channel.get('id') == 'telegram'
        and telegram_bundle.get('stageRuntimeDependencies') is True
        and telegram_openclaw.get('setupEntry') == './setup-entry.ts'
        and telegram_extensions == ['./index.ts']
    )

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
        and host_openclaw.get('extensions') == ['./index.mjs']
    )

    uses_bundled_telegram_overlay_build = EXPECTED_BUILD_DOCKERFILE in build_openclaw_local
    build_script_runs_packager = '"$ROOT/deployment/package-local-plugins.sh" "$ROOT"' in build_openclaw_local
    dockerfile_still_copies_direct_repo_sources = any(snippet in plugin_dockerfile for snippet in DISALLOWED_DIRECT_SOURCE_COPY_SNIPPETS)
    dockerfile_stages_bundled_plugin_root = 'COPY --chown=node:node deployment/.build/bundled-plugins/ /app/extensions/' in plugin_dockerfile
    dockerfile_sets_bundled_plugin_env = 'ENV OPENCLAW_BUNDLED_PLUGINS_DIR=/app/extensions' in plugin_dockerfile
    dockerfile_preserves_bundled_runtime = 'rm -rf /app/extensions/telegram' not in plugin_dockerfile and 'rm -rf /app/dist/extensions/telegram' not in plugin_dockerfile
    package_script_uses_direct_telegram_source = 'OPENCLAW_TELEGRAM_REPO' in package_plugins_script and '$ROOT/openclaw-telegram-enhanced' not in package_plugins_script and 'sync-telegram-build-copy.sh' not in package_plugins_script
    package_script_guards_packlists = 'npm pack --json --dry-run' in package_plugins_script and 'includes non-runtime files' in package_plugins_script
    package_script_stages_bundled_telegram = 'TELEGRAM_OVERLAY_DIR' in package_plugins_script and 'stage_packlist_files "$TELEGRAM_PLUGIN_ROOT" "$TELEGRAM_OVERLAY_DIR"' in package_plugins_script
    package_script_stages_bundled_host_control = 'HOST_CONTROL_OVERLAY_DIR' in package_plugins_script and 'stage_packlist_files "$HOST_CONTROL_PLUGIN_ROOT" "$HOST_CONTROL_OVERLAY_DIR"' in package_plugins_script
    package_script_no_longer_packs_plugins = '--pack-destination "$ARTIFACT_DIR"' not in package_plugins_script
    verify_router_contract_uses_direct_source = 'CANON_TELEGRAM' in verify_router_contract_script and 'DEPLOY_ROUTER' not in verify_router_contract_script

    checks = [
        (not uses_legacy_sdk_export, 'Incompatible gateway source bundle: Telegram runtime-api still imports "openclaw/plugin-sdk/telegram". Use only stable public subpaths such as core/channel-actions/channel-status/channel-config-schema instead.'),
        (not uses_unsupported_telegram_core_import, 'Incompatible gateway source bundle: Telegram runtime-api still imports "openclaw/plugin-sdk/telegram-core", which is not a public package export in the governed runtime.'),
        (not uses_wrong_host_control_helper_import, 'Incompatible gateway source bundle: bot-message-context.session.ts still imports appendHostControlTopicSystemPrompt from ./bot/helpers.js instead of ./group-config-helpers.js.'),
        (has_plugin_compat_metadata, 'Incompatible gateway source bundle: Telegram package.json is missing OpenClaw compat/build metadata required for reproducible bundled overlays.'),
        (telegram_publishable_files, 'Incompatible gateway source bundle: Telegram package.json must use an explicit files allowlist that excludes tests, harnesses, helpers, and declaration-only files from the staged overlay.'),
        (telegram_overlay_metadata, 'Incompatible gateway source bundle: Telegram package metadata must still describe the official telegram channel entrypoint and bundle runtime dependencies for the bundled overlay path.'),
        (host_control_publishable_metadata, 'Incompatible gateway source bundle: host-control package.json must remain a publishable managed plugin with compat/build entries, ./index.mjs extension metadata, and a files whitelist that excludes tests.'),
        (uses_bundled_telegram_overlay_build, f'Incompatible gateway source bundle: deployment/build-openclaw-local.sh must default to {EXPECTED_BUILD_DOCKERFILE} so local builds use the bundled Telegram overlay path.'),
        (build_script_runs_packager, 'Incompatible gateway source bundle: deployment/build-openclaw-local.sh must prepare staged build inputs before docker build.'),
        (not dockerfile_still_copies_direct_repo_sources, 'Incompatible gateway source bundle: managed build Dockerfile still copies Telegram or host-control directly from a repo checkout instead of staged build inputs.'),
        (dockerfile_stages_bundled_plugin_root, 'Incompatible gateway source bundle: managed build Dockerfile must stage the bundled plugin root from deployment/.build/bundled-plugins into /app/extensions.'),
        (dockerfile_sets_bundled_plugin_env, 'Incompatible gateway source bundle: managed build Dockerfile must set OPENCLAW_BUNDLED_PLUGINS_DIR=/app/extensions.'),
        (dockerfile_preserves_bundled_runtime, 'Incompatible gateway source bundle: managed build Dockerfile must preserve the bundled runtime seam instead of deleting it.'),
        (package_script_uses_direct_telegram_source, 'Incompatible gateway source bundle: deployment/package-local-plugins.sh must stage Telegram directly from OPENCLAW_TELEGRAM_REPO and must not rely on a copied tree in another repo.'),
        (package_script_guards_packlists, 'Incompatible gateway source bundle: deployment/package-local-plugins.sh must dry-run npm pack and block non-runtime files from entering staged build inputs.'),
        (package_script_stages_bundled_telegram, 'Incompatible gateway source bundle: deployment/package-local-plugins.sh must stage Telegram packlist files into the bundled plugin root.'),
        (package_script_stages_bundled_host_control, 'Incompatible gateway source bundle: deployment/package-local-plugins.sh must stage host-control packlist files into the bundled plugin root.'),
        (package_script_no_longer_packs_plugins, 'Incompatible gateway source bundle: deployment/package-local-plugins.sh must not build plugin tarballs for the bundled runtime seam.'),
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
        f'telegram_publishable_files={str(telegram_publishable_files).lower()} '
        f'telegram_overlay_metadata={str(telegram_overlay_metadata).lower()} '
        f'host_control_publishable_metadata={str(host_control_publishable_metadata).lower()} '
        f'bundled_telegram_overlay_build={str(uses_bundled_telegram_overlay_build).lower()} '
        f'build_script_runs_packager={str(build_script_runs_packager).lower()} '
        f'package_script_uses_direct_telegram_source={str(package_script_uses_direct_telegram_source).lower()} '
        f'package_script_guards_packlists={str(package_script_guards_packlists).lower()} '
        f'dockerfile_stages_bundled_plugin_root={str(dockerfile_stages_bundled_plugin_root).lower()} '
        f'dockerfile_sets_bundled_plugin_env={str(dockerfile_sets_bundled_plugin_env).lower()} '
        f'package_script_stages_bundled_telegram={str(package_script_stages_bundled_telegram).lower()} '
        f'package_script_stages_bundled_host_control={str(package_script_stages_bundled_host_control).lower()} '
        f'package_script_no_longer_packs_plugins={str(package_script_no_longer_packs_plugins).lower()} '
        f'verify_router_contract_uses_direct_source={str(verify_router_contract_uses_direct_source).lower()} '
        f'security_arch_workspace_template={str((security_arch_agents.exists() and security_arch_skill.exists())).lower()}'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())