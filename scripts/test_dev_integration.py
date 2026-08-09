#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import signal
import tempfile
import time
import unittest
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

    def test_owner_files_must_remain_inside_selected_checkout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-owner-file-") as temp_dir:
            root = Path(temp_dir)
            owner_root = root / "owner"
            owner_root.mkdir()
            command = owner_root / "scripts/action.sh"
            command.parent.mkdir()
            command.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

            self.assertEqual(
                DEV_INTEGRATION.resolve_owner_file(
                    owner_root,
                    "scripts/action.sh",
                    description="Profile action",
                ),
                command,
            )
            with self.assertRaisesRegex(SystemExit, "must be owner-relative"):
                DEV_INTEGRATION.resolve_owner_file(
                    owner_root,
                    str(command),
                    description="Profile action",
                )

            outside = root / "outside.sh"
            outside.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (owner_root / "scripts/escaped.sh").symlink_to(outside)
            with self.assertRaisesRegex(SystemExit, "escapes the selected owner checkout"):
                DEV_INTEGRATION.resolve_owner_file(
                    owner_root,
                    "scripts/escaped.sh",
                    description="Profile action",
                )

            with self.assertRaisesRegex(SystemExit, "is unavailable"):
                DEV_INTEGRATION.resolve_owner_file(
                    owner_root,
                    "scripts/missing.sh",
                    description="Profile action",
                )

    def test_registry_contracts_must_remain_inside_selected_checkout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-registry-file-") as temp_dir:
            root = Path(temp_dir)
            governance_root = root / "workspace-governance"
            contracts_root = governance_root / "contracts"
            contracts_root.mkdir(parents=True)
            policy_path = contracts_root / "developer-integration-policy.yaml"
            registry_path = contracts_root / "developer-integration-profiles.yaml"
            policy_path.write_text("profile_lifecycle: {}\n", encoding="utf-8")
            registry_path.write_text("profiles: {}\n", encoding="utf-8")

            policy, registry = DEV_INTEGRATION.load_registry(
                root,
                {"workspace-governance": governance_root},
            )
            self.assertEqual(policy, {"profile_lifecycle": {}})
            self.assertEqual(registry, {"profiles": {}})

            outside = root / "outside.yaml"
            outside.write_text("external: true\n", encoding="utf-8")
            policy_path.unlink()
            policy_path.symlink_to(outside)
            with self.assertRaisesRegex(
                SystemExit,
                "Dev-integration lifecycle policy escapes the selected owner checkout",
            ):
                DEV_INTEGRATION.load_registry(
                    root,
                    {"workspace-governance": governance_root},
                )

    def test_dispatch_terminates_background_process_group(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-process-") as temp_dir:
            root = Path(temp_dir)
            pid_file = root / "background.pid"
            command = root / "action.sh"
            command.write_text(
                '#!/usr/bin/env bash\nsleep 30 &\nprintf "%s\\n" "$!" >"$PID_FILE"\n',
                encoding="utf-8",
            )
            command.chmod(0o700)

            returncode = DEV_INTEGRATION.dispatch_command(
                command,
                cwd=root,
                env={**os.environ, "PID_FILE": str(pid_file)},
            )

            self.assertEqual(returncode, 0)
            background_pid = int(pid_file.read_text(encoding="utf-8"))
            deadline = time.monotonic() + 2
            while Path(f"/proc/{background_pid}").exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            if Path(f"/proc/{background_pid}/stat").is_file():
                state = Path(f"/proc/{background_pid}/stat").read_text().split()[2]
                self.assertEqual(state, "Z")

    def test_dispatch_handles_termination_and_restores_signal_handler(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-signal-") as temp_dir:
            root = Path(temp_dir)
            command = root / "action.sh"
            command.write_text(
                '#!/usr/bin/env bash\nkill -TERM "$PPID"\nsleep 30\n',
                encoding="utf-8",
            )
            command.chmod(0o700)
            previous_handler = signal.getsignal(signal.SIGTERM)

            returncode = DEV_INTEGRATION.dispatch_command(
                command,
                cwd=root,
                env=dict(os.environ),
            )

            self.assertEqual(returncode, 128 + signal.SIGTERM)
            self.assertEqual(signal.getsignal(signal.SIGTERM), previous_handler)

    def test_repo_override_owns_profile_loading_and_dispatch_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-override-") as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            default_owner = workspace_root / "owner-repo"
            selected_owner = Path(temp_dir) / "selected-owner"
            selected_platform = Path(temp_dir) / "selected-platform"
            selected_governance = Path(temp_dir) / "selected-governance"
            profile_relpath = Path("dev-integration/profiles/test/profile.yaml")
            default_profile = default_owner / profile_relpath
            selected_profile = selected_owner / profile_relpath
            default_profile.parent.mkdir(parents=True)
            selected_profile.parent.mkdir(parents=True)
            selected_platform.mkdir()
            selected_governance.mkdir()
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
            selected_platform_state = {
                "branch": "runner",
                "dirty": False,
                "head_sha": "b" * 40,
            }
            selected_governance_state = {
                "branch": "authority",
                "dirty": False,
                "head_sha": "c" * 40,
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
                    side_effect=lambda repo_root, **_: (
                        selected_state
                        if repo_root == selected_owner.resolve()
                        else (
                            selected_platform_state
                            if repo_root == selected_platform.resolve()
                            else selected_governance_state
                        )
                    ),
                ) as git_state,
            ):
                resolved = DEV_INTEGRATION.resolve_profile(
                    action="up",
                    workspace_root=workspace_root,
                    profile_id="test-profile",
                    repo_overrides={
                        "owner-repo": selected_owner,
                        "platform-engineering": selected_platform,
                        "workspace-governance": selected_governance,
                    },
                )

            _, profile, owner_root, profile_path, repo_paths, repo_states = resolved
            load_registry.assert_called_once_with(
                workspace_root,
                {
                    "owner-repo": selected_owner,
                    "platform-engineering": selected_platform,
                    "workspace-governance": selected_governance,
                },
            )
            git_state.assert_any_call(
                selected_owner.resolve(),
                workspace_root=workspace_root,
            )
            git_state.assert_any_call(
                selected_platform.resolve(),
                workspace_root=workspace_root,
            )
            git_state.assert_any_call(
                selected_governance.resolve(),
                workspace_root=workspace_root,
            )
            self.assertEqual(profile["summary"], "selected checkout")
            self.assertEqual(owner_root, selected_owner.resolve())
            self.assertEqual(profile_path, selected_profile.resolve())
            self.assertEqual(repo_paths["owner-repo"], selected_owner.resolve())
            self.assertEqual(repo_states["owner-repo"], selected_state)
            self.assertEqual(
                repo_paths["platform-engineering"],
                selected_platform.resolve(),
            )
            self.assertEqual(
                repo_states["platform-engineering"],
                selected_platform_state,
            )
            self.assertEqual(
                repo_paths["workspace-governance"],
                selected_governance.resolve(),
            )
            self.assertEqual(
                repo_states["workspace-governance"],
                selected_governance_state,
            )

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

    def test_platform_override_rejects_runner_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-reexec-") as temp_dir:
            root = Path(temp_dir)
            selected_root = root / "platform-engineering"
            selected_runner = selected_root / "scripts/dev_integration.py"
            selected_runner.parent.mkdir(parents=True)
            outside_runner = root / "outside-runner.py"
            outside_runner.write_text("# external runner\n", encoding="utf-8")
            selected_runner.symlink_to(outside_runner)

            with self.assertRaisesRegex(
                SystemExit,
                "Selected Platform runner escapes the selected owner checkout",
            ):
                DEV_INTEGRATION.reexec_from_selected_platform_checkout(
                    {"platform-engineering": selected_root},
                    workspace_root=Path("/original/workspace"),
                )


if __name__ == "__main__":
    unittest.main()
