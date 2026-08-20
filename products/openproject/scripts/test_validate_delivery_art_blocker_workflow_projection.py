import importlib.util
import json
import pathlib
import shutil
import tempfile
import unittest


SCRIPT_PATH = pathlib.Path(__file__).resolve().parent / (
    "validate_delivery_art_blocker_workflow_projection.py"
)
SPEC = importlib.util.spec_from_file_location(
    "validate_delivery_art_blocker_workflow_projection", SCRIPT_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ValidateDeliveryArtBlockerWorkflowProjectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source_root = pathlib.Path(__file__).resolve().parents[3]

    def copy_projection(self, repo_root: pathlib.Path) -> pathlib.Path:
        product_dir = repo_root / "products" / "openproject"
        product_dir.mkdir(parents=True)
        for filename in (
            "delivery-art-blocker-workflow.json",
            "delivery-art-blocker-workflow-source-lock.json",
        ):
            shutil.copy2(self.source_root / "products" / "openproject" / filename, product_dir)
        return product_dir

    def test_live_projection_passes(self) -> None:
        self.assertEqual(MODULE.validate_projection(self.source_root), [])

    def test_stale_action_vocabulary_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = pathlib.Path(tmp_dir)
            product_dir = self.copy_projection(repo_root)
            projection_path = product_dir / "delivery-art-blocker-workflow.json"
            projection = json.loads(projection_path.read_text(encoding="utf-8"))
            projection.pop("allowed_actions")
            projection_path.write_text(json.dumps(projection, indent=2) + "\n", encoding="utf-8")

            errors = MODULE.validate_projection(repo_root)
            self.assertTrue(any("allowed_actions" in error for error in errors))

    def test_stale_source_digest_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = pathlib.Path(tmp_dir)
            product_dir = self.copy_projection(repo_root)
            lock_path = product_dir / "delivery-art-blocker-workflow-source-lock.json"
            source_lock = json.loads(lock_path.read_text(encoding="utf-8"))
            source_lock["source"]["sha256"] = "0" * 64
            lock_path.write_text(json.dumps(source_lock, indent=2) + "\n", encoding="utf-8")

            errors = MODULE.validate_projection(repo_root)
            self.assertTrue(any("locked OOS source digest" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
