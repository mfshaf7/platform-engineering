from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_ai_model_profiles import validate


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATHS = (
    Path("security/governed-ai-model-profiles.yaml"),
    Path("security/governed-ai-access-plane.yaml"),
    Path("security/governed-ai-runtime-assist-contract.yaml"),
    Path("security/governed-ai-devint-egress-policy.yaml"),
)
LOCAL_REFERENCE_PATHS = (
    Path("docs/standards/governed-ai-access-model.md"),
    Path("docs/components/governed-ai-gateway/README.md"),
)


class GovernedAiModelProfileTests(unittest.TestCase):
    def prepare_repo(self, root: Path) -> Path:
        repo_root = root / "platform-engineering"
        for relative_path in CONTRACT_PATHS:
            target = repo_root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / relative_path, target)
        for relative_path in LOCAL_REFERENCE_PATHS:
            target = repo_root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("fixture\n", encoding="utf-8")
        profile_path = repo_root / "dev-integration/profiles/governed-ai-gateway/profile.yaml"
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text("schema_version: 1\n", encoding="utf-8")
        return repo_root

    def test_selected_model_binding_is_valid(self) -> None:
        with tempfile.TemporaryDirectory(prefix="governed-ai-profile-") as temp_dir:
            repo_root = self.prepare_repo(Path(temp_dir))
            self.assertEqual(validate(repo_root), [])

    def test_model_must_be_allowed_by_selected_provider_route(self) -> None:
        with tempfile.TemporaryDirectory(prefix="governed-ai-profile-") as temp_dir:
            repo_root = self.prepare_repo(Path(temp_dir))
            access_plane_path = repo_root / "security/governed-ai-access-plane.yaml"
            payload = yaml.safe_load(access_plane_path.read_text(encoding="utf-8"))
            payload["access_plane"]["provider_routes"][0]["allowed_models"] = ["different-model"]
            access_plane_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

            self.assertIn(
                "security/governed-ai-access-plane.yaml: provider route openai-responses-api must allow model 'gpt-5.6-terra'",
                validate(repo_root),
            )

    def test_provider_secret_must_reference_the_selected_route(self) -> None:
        with tempfile.TemporaryDirectory(prefix="governed-ai-profile-") as temp_dir:
            repo_root = self.prepare_repo(Path(temp_dir))
            access_plane_path = repo_root / "security/governed-ai-access-plane.yaml"
            payload = yaml.safe_load(access_plane_path.read_text(encoding="utf-8"))
            secret_ref = payload["access_plane"]["provider_credential_custody"]["provider_secret_refs"][0]
            secret_ref["route_id"] = "unknown-route"
            access_plane_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

            self.assertIn(
                "security/governed-ai-access-plane.yaml: provider_secret_refs entry #1 references unknown route 'unknown-route'",
                validate(repo_root),
            )


if __name__ == "__main__":
    unittest.main()
