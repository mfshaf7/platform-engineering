import importlib.util
import json
import pathlib
import unittest
from types import SimpleNamespace
from unittest import mock


SCRIPT_PATH = pathlib.Path(__file__).resolve().parent / "openproject_platform_admin_adapter.py"
SPEC = importlib.util.spec_from_file_location("openproject_platform_admin_adapter", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class OpenProjectPlatformAdminAdapterTest(unittest.TestCase):
    def test_sync_delivery_art_views_operation_is_defined(self) -> None:
        contract = MODULE.load_contract()
        operation = MODULE.find_operation(contract, "sync-delivery-art-views")
        self.assertEqual(operation["script"], "openproject_sync_delivery_art_views.sh")
        self.assertIn("openproject_sync_delivery_art_views_runner.rb", operation["internal_runner_files"])
        self.assertIn("OPENPROJECT_DELIVERY_PI_NAMES", operation["pass_env"])

    def test_unknown_operation_raises(self) -> None:
        contract = MODULE.load_contract()
        with self.assertRaisesRegex(RuntimeError, "is not defined"):
            MODULE.find_operation(contract, "missing-operation")

    def test_openproject_pod_uses_default_selector(self) -> None:
        def fake_run(command: list[str], *, capture_output: bool = False) -> SimpleNamespace:
            if "get" in command and "deployment" in command:
                return SimpleNamespace(stdout=json.dumps({"spec": {"selector": {"matchLabels": {}}}}))
            return SimpleNamespace(stdout="openproject-web-pod")

        with mock.patch.object(MODULE, "run", side_effect=fake_run) as run_mock:
            self.assertEqual(MODULE.openproject_pod(), "openproject-web-pod")
        first_command = run_mock.call_args_list[1].args[0]
        self.assertIn(MODULE.OPENPROJECT_POD_LABEL_SELECTOR, first_command)

    def test_openproject_pod_falls_back_to_deployment_selector(self) -> None:
        def fake_run(command: list[str], *, capture_output: bool = False) -> SimpleNamespace:
            if "get" in command and "deployment" in command:
                return SimpleNamespace(
                    stdout=json.dumps(
                        {
                            "spec": {
                                "selector": {
                                    "matchLabels": {
                                        "app.kubernetes.io/instance": "devint-accepted-idea-delivery-openproject",
                                        "app.kubernetes.io/name": "openproject",
                                    }
                                }
                            }
                        }
                    )
                )
            if command.count("pod") and MODULE.OPENPROJECT_POD_LABEL_SELECTOR in command:
                raise MODULE.subprocess.CalledProcessError(1, command)
            return SimpleNamespace(stdout="openproject-web-pod")

        with mock.patch.object(MODULE, "run", side_effect=fake_run):
            self.assertEqual(MODULE.openproject_pod(), "openproject-web-pod")


if __name__ == "__main__":
    unittest.main()
