#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
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

            first_archive, first_result = DEV_INTEGRATION.write_session_files(
                manifest=self.manifest("execution-up", "up"),
                current_manifest=current,
                sessions_root=sessions,
            )
            DEV_INTEGRATION.write_execution_result(
                manifest_path=first_archive,
                result_path=first_result,
                returncode=0,
            )
            second_archive, second_result = DEV_INTEGRATION.write_session_files(
                manifest=self.manifest("execution-smoke", "smoke"),
                current_manifest=current,
                sessions_root=sessions,
            )
            DEV_INTEGRATION.write_execution_result(
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
                DEV_INTEGRATION.load_yaml(current)["execution_id"],
                "execution-smoke",
            )

            with self.assertRaises(FileExistsError):
                DEV_INTEGRATION.write_session_files(
                    manifest=self.manifest("execution-up", "up"),
                    current_manifest=current,
                    sessions_root=sessions,
                )

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


if __name__ == "__main__":
    unittest.main()
