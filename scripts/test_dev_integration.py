#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest


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


if __name__ == "__main__":
    unittest.main()
