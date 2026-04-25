import importlib.util
import pathlib
import unittest


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


if __name__ == "__main__":
    unittest.main()
