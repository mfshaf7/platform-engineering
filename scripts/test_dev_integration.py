#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from uuid import uuid4
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("dev_integration.py")
SPEC = importlib.util.spec_from_file_location("dev_integration", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
DEV_INTEGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEV_INTEGRATION)


class DevIntegrationRunnerTests(unittest.TestCase):
    def manifest(self, execution_id: str, action: str) -> dict:
        return {
            "schema_version": 1,
            "profile_id": "test-profile",
            "session_id": "test-profile-operator-20260809T000000Z",
            "execution_id": execution_id,
            "action": action,
        }

    def test_action_manifests_and_results_do_not_overwrite_each_other(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-") as temp_dir:
            root = Path(temp_dir)
            current = root / "state/current-session.yaml"
            sessions = root / "sessions"

            first_manifest = self.manifest("execution-up", "up")
            first_archive, first_result, first_snapshot = (
                DEV_INTEGRATION.prepare_session_files(
                    manifest=first_manifest,
                    current_manifest=current,
                    sessions_root=sessions,
                )
            )
            DEV_INTEGRATION.write_execution_result(
                manifest_snapshot=first_snapshot,
                manifest_path=first_archive,
                result_path=first_result,
                returncode=0,
            )
            second_manifest = self.manifest("execution-smoke", "smoke")
            second_archive, second_result, second_snapshot = (
                DEV_INTEGRATION.prepare_session_files(
                    manifest=second_manifest,
                    current_manifest=current,
                    sessions_root=sessions,
                )
            )
            DEV_INTEGRATION.write_execution_result(
                manifest_snapshot=second_snapshot,
                manifest_path=second_archive,
                result_path=second_result,
                returncode=2,
            )

            self.assertNotEqual(first_archive, second_archive)
            self.assertTrue(first_archive.is_file())
            self.assertTrue(first_result.is_file())
            self.assertTrue(second_archive.is_file())
            self.assertTrue(second_result.is_file())
            self.assertEqual(
                DEV_INTEGRATION.load_yaml(first_result)["result"],
                "succeeded",
            )
            self.assertEqual(
                DEV_INTEGRATION.load_yaml(second_result)["result"],
                "failed",
            )
            self.assertEqual(
                DEV_INTEGRATION.load_yaml(second_result)["returncode"],
                2,
            )
            self.assertEqual(
                DEV_INTEGRATION.load_yaml(second_result)["source_manifest"],
                second_manifest,
            )
            self.assertEqual(
                DEV_INTEGRATION.load_yaml(current)["execution_id"],
                "execution-smoke",
            )

            with self.assertRaises(FileExistsError):
                DEV_INTEGRATION.write_execution_result(
                    manifest_snapshot=first_snapshot,
                    manifest_path=first_archive,
                    result_path=first_result,
                    returncode=0,
                )

    def test_execution_evidence_is_created_only_after_action(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-evidence-") as temp_dir:
            root = Path(temp_dir)
            manifest = self.manifest("execution-up", "up")
            archive, result, snapshot = DEV_INTEGRATION.prepare_session_files(
                manifest=manifest,
                current_manifest=root / "state/current-session.yaml",
                sessions_root=root / "sessions",
            )
            self.assertFalse(archive.exists())
            self.assertFalse(result.exists())

            DEV_INTEGRATION.write_execution_result(
                manifest_snapshot=snapshot,
                manifest_path=archive,
                result_path=result,
                returncode=0,
            )

            self.assertEqual(archive.read_bytes(), snapshot)
            self.assertEqual(
                DEV_INTEGRATION.load_yaml(result)["source_manifest"],
                manifest,
            )
            self.assertEqual(archive.stat().st_mode & 0o777, 0o400)
            self.assertEqual(result.stat().st_mode & 0o777, 0o400)

    def test_dispatch_terminates_detached_session_before_return(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-process-") as temp_dir:
            root = Path(temp_dir)
            process_marker = f"devint-detached-{uuid4()}"
            ready_file = root / "detached.ready"
            command = root / "action.sh"
            command.write_text(
                "#!/usr/bin/env bash\n"
                f"setsid bash -c 'printf ready >\"$DETACHED_READY\"; "
                f"exec -a {process_marker} sleep 30' &\n"
                'while [[ ! -f "$DETACHED_READY" ]]; do sleep 0.01; done\n',
                encoding="utf-8",
            )
            command.chmod(0o700)

            returncode = DEV_INTEGRATION.dispatch_command(
                command,
                cwd=root,
                env={**os.environ, "DETACHED_READY": str(ready_file)},
            )

            self.assertEqual(returncode, 0)
            self.assertEqual(ready_file.read_text(encoding="utf-8"), "ready")
            surviving_commands = []
            for cmdline_path in Path("/proc").glob("[0-9]*/cmdline"):
                try:
                    command_line = cmdline_path.read_bytes().replace(b"\0", b" ").decode()
                except (FileNotFoundError, PermissionError, ProcessLookupError):
                    continue
                if process_marker in command_line:
                    surviving_commands.append(command_line)
            self.assertEqual(surviving_commands, [])

    def test_repo_override_owns_profile_loading_and_dispatch_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-override-") as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            default_owner = workspace_root / "owner-repo"
            selected_owner = Path(temp_dir) / "selected-owner"
            profile_relpath = Path("dev-integration/profiles/test/profile.yaml")
            default_profile = default_owner / profile_relpath
            selected_profile = selected_owner / profile_relpath
            default_profile.parent.mkdir(parents=True)
            selected_profile.parent.mkdir(parents=True)
            default_profile.write_text("summary: wrong checkout\n", encoding="utf-8")
            selected_profile.write_text(
                "\n".join(
                    [
                        "summary: selected checkout",
                        "runtime:",
                        "  namespace_pattern: devint-{profile}-{operator}",
                        "source_repos:",
                        "  - repo: owner-repo",
                        "stage_handoff:",
                        "  required_checks: []",
                        "commands:",
                        "  up: scripts/up.sh",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            entry = {
                "lifecycle": "active",
                "owner_repo": "owner-repo",
                "profile_path": profile_relpath.as_posix(),
                "runtime_owner": "platform-engineering",
                "security_owner": "security-architecture",
            }
            policy = {"profile_lifecycle": {"self_serve_statuses": ["active"]}}
            registry = {"profiles": {"test-profile": entry}}
            selected_state = {
                "branch": "test",
                "dirty": False,
                "head_sha": "a" * 40,
            }

            with (
                patch.object(
                    DEV_INTEGRATION,
                    "load_registry",
                    return_value=(policy, registry),
                ) as load_registry,
                patch.object(
                    DEV_INTEGRATION,
                    "git_state",
                    return_value=selected_state,
                ) as git_state,
            ):
                resolved = DEV_INTEGRATION.resolve_profile(
                    action="up",
                    workspace_root=workspace_root,
                    profile_id="test-profile",
                    repo_overrides={"owner-repo": selected_owner},
                )

            _, profile, owner_root, profile_path, repo_paths, repo_states = resolved
            load_registry.assert_called_once_with(
                workspace_root,
                {"owner-repo": selected_owner},
            )
            git_state.assert_called_once_with(
                selected_owner.resolve(),
                workspace_root=workspace_root,
            )
            self.assertEqual(profile["summary"], "selected checkout")
            self.assertEqual(owner_root, selected_owner.resolve())
            self.assertEqual(profile_path, selected_profile.resolve())
            self.assertEqual(repo_paths["owner-repo"], selected_owner.resolve())
            self.assertEqual(repo_states["owner-repo"], selected_state)

    def test_platform_override_reexecutes_the_selected_runner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-reexec-") as temp_dir:
            selected_root = Path(temp_dir) / "platform-engineering"
            selected_runner = selected_root / "scripts/dev_integration.py"
            selected_runner.parent.mkdir(parents=True)
            selected_runner.write_text("# selected runner\n", encoding="utf-8")

            with (
                patch.object(DEV_INTEGRATION.os, "execv") as execv,
                patch.object(
                    DEV_INTEGRATION.sys,
                    "argv",
                    ["dev_integration.py", "up", "--profile", "test-profile"],
                ),
                self.assertRaisesRegex(RuntimeError, "failed to execute"),
            ):
                DEV_INTEGRATION.reexec_from_selected_platform_checkout(
                    {"platform-engineering": selected_root},
                    workspace_root=Path("/original/workspace"),
                )

            execv.assert_called_once_with(
                DEV_INTEGRATION.sys.executable,
                [
                    DEV_INTEGRATION.sys.executable,
                    str(selected_runner.resolve()),
                    "up",
                    "--profile",
                    "test-profile",
                    "--workspace-root",
                    "/original/workspace",
                ],
            )


if __name__ == "__main__":
    unittest.main()
