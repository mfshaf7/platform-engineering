import importlib.util
import json
import pathlib
import tempfile
import unittest


SCRIPT_PATH = (
    pathlib.Path(__file__).resolve().parent / "validate_openproject_platform_admin_surface.py"
)
SPEC = importlib.util.spec_from_file_location(
    "validate_openproject_platform_admin_surface", SCRIPT_PATH
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ValidateOpenProjectPlatformAdminSurfaceTest(unittest.TestCase):
    def test_live_contract_passes(self) -> None:
        repo_root = pathlib.Path(__file__).resolve().parents[3]
        self.assertEqual(MODULE.validate_contract(repo_root), [])

    def test_missing_runner_classification_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_root = pathlib.Path(tmp_dir)
            product_dir = repo_root / "products" / "openproject"
            scripts_dir = product_dir / "scripts"
            runbooks_dir = product_dir / "runbooks"
            scripts_dir.mkdir(parents=True)
            runbooks_dir.mkdir(parents=True)
            (repo_root / "Makefile").write_text(".PHONY: openproject-configure-delivery-art\n", encoding="utf-8")
            (product_dir / "README.md").write_text("openproject-platform-admin-surface.json\n", encoding="utf-8")
            (product_dir / "AGENTS.md").write_text("openproject-platform-admin-surface.json\n", encoding="utf-8")
            (product_dir / "delivery-art-contract.md").write_text(
                "openproject-platform-admin-surface.json\n", encoding="utf-8"
            )
            (product_dir / "runbooks" / "README.md").write_text(
                "openproject-platform-admin-surface.json\n", encoding="utf-8"
            )
            (runbooks_dir / "openproject-platform-admin-surface.md").write_text(
                "openproject-platform-admin-surface.json\nvalidate_openproject_platform_admin_surface.py\n",
                encoding="utf-8",
            )
            (scripts_dir / "README.md").write_text(
                "openproject-platform-admin-surface.json\nvalidate_openproject_platform_admin_surface.py\n",
                encoding="utf-8",
            )
            (runbooks_dir / "configure-delivery-art.md").write_text("# stub\n", encoding="utf-8")
            (scripts_dir / "openproject_configure_delivery_art.sh").write_text(
                "openproject_configure_delivery_art_runner.rb\n",
                encoding="utf-8",
            )
            (scripts_dir / "openproject_configure_delivery_art_runner.rb").write_text(
                "# runner\n", encoding="utf-8"
            )
            contract = {
                "schema_version": 1,
                "doc_surfaces": [
                    {
                        "path": "runbooks/openproject-platform-admin-surface.md",
                        "required_markers": [
                            "openproject-platform-admin-surface.json",
                            "validate_openproject_platform_admin_surface.py",
                        ],
                    },
                    {
                        "path": "scripts/README.md",
                        "required_markers": [
                            "openproject-platform-admin-surface.json",
                            "validate_openproject_platform_admin_surface.py",
                        ],
                    },
                    {"path": "README.md", "required_markers": ["openproject-platform-admin-surface.json"]},
                    {"path": "delivery-art-contract.md", "required_markers": ["openproject-platform-admin-surface.json"]},
                    {"path": "runbooks/README.md", "required_markers": ["openproject-platform-admin-surface.json"]},
                    {"path": "AGENTS.md", "required_markers": ["openproject-platform-admin-surface.json"]},
                ],
                "shell_surfaces": [
                    {
                        "script": "openproject_configure_delivery_art.sh",
                        "surface_class": "platform-admin",
                        "make_targets": ["openproject-configure-delivery-art"],
                        "runbooks": ["runbooks/configure-delivery-art.md"],
                        "purpose": "stub",
                        "internal_runner_files": ["openproject_configure_delivery_art_runner.rb"],
                    }
                ],
                "python_tools": [],
                "rails_runners": [],
                "support_modules": [],
                "test_files": [],
                "ignored_files": ["README.md"],
            }
            contract_path = product_dir / "openproject-platform-admin-surface.json"
            contract_path.write_text(json.dumps(contract), encoding="utf-8")

            original_contract_path = MODULE.CONTRACT_PATH
            try:
                MODULE.CONTRACT_PATH = contract_path
                errors = MODULE.validate_contract(repo_root)
            finally:
                MODULE.CONTRACT_PATH = original_contract_path

            self.assertTrue(
                any("Rails runners missing from platform-admin contract" in error for error in errors)
            )


if __name__ == "__main__":
    unittest.main()
