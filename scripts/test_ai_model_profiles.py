from __future__ import annotations

import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
RUNTIME_ROOT = (
    Path(__file__).resolve().parents[1]
    / "dev-integration/profiles/governed-ai-gateway/runtime"
)
sys.path.insert(0, str(RUNTIME_ROOT))

from validate_ai_model_profiles import validate
from model_profile_resolver import (
    ModelProfileResolutionError,
    resolve_model_profile,
    resolve_model_profile_registry,
)
from strict_output_schema import OutputSchemaError, validate_output


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATHS = (
    Path("security/governed-ai-model-profiles.yaml"),
    Path("security/governed-ai-access-plane.yaml"),
    Path("security/governed-ai-runtime-assist-contract.yaml"),
    Path("security/governed-ai-devint-egress-policy.yaml"),
    Path("security/schemas/intake-classification-result.schema.json"),
    Path("security/schemas/delivery-work-design-advice.schema.json"),
    Path("security/schemas/delivery-refinement-advice.schema.json"),
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

    def test_provider_neutral_model_binding_is_valid(self) -> None:
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
                "security/governed-ai-access-plane.yaml: provider route ollama-local-host must allow model 'qwen3:8b'",
                validate(repo_root),
            )

    def test_selected_environment_must_reference_known_binding(self) -> None:
        with tempfile.TemporaryDirectory(prefix="governed-ai-profile-") as temp_dir:
            repo_root = self.prepare_repo(Path(temp_dir))
            profile_path = repo_root / "security/governed-ai-model-profiles.yaml"
            payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            payload["model_profiles"]["intake-classifier-v1"]["selected_binding_by_environment"][
                "dev-integration"
            ] = "missing"
            profile_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

            self.assertIn(
                "security/governed-ai-model-profiles.yaml: intake-classifier-v1 environment "
                "'dev-integration' references unknown binding 'missing'",
                validate(repo_root),
            )

    def test_active_ollama_binding_requires_digest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="governed-ai-profile-") as temp_dir:
            repo_root = self.prepare_repo(Path(temp_dir))
            profile_path = repo_root / "security/governed-ai-model-profiles.yaml"
            payload = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            del payload["model_profiles"]["intake-classifier-v1"]["bindings"][
                "local-ollama-qwen3-8b"
            ]["model_digest"]
            profile_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

            self.assertIn(
                "security/governed-ai-model-profiles.yaml: intake-classifier-v1 Ollama binding "
                "local-ollama-qwen3-8b missing non-empty model_digest",
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

    def test_selected_not_active_caller_cannot_be_listed_as_active(self) -> None:
        with tempfile.TemporaryDirectory(prefix="governed-ai-profile-") as temp_dir:
            repo_root = self.prepare_repo(Path(temp_dir))
            contract_path = repo_root / "security/governed-ai-runtime-assist-contract.yaml"
            payload = yaml.safe_load(contract_path.read_text(encoding="utf-8"))
            consumers = payload["contract"]["consumers"]
            caller = "operator-orchestration-service/refinement-assist"
            consumers["registered_not_active_callers"].remove(caller)
            consumers["allowed_callers"].append(caller)
            contract_path.write_text(
                yaml.safe_dump(payload, sort_keys=False), encoding="utf-8"
            )

            errors = validate(repo_root)
            self.assertIn(
                "security/governed-ai-runtime-assist-contract.yaml: "
                "consumers.allowed_callers must match active profile callers exactly",
                errors,
            )
            self.assertIn(
                "security/governed-ai-runtime-assist-contract.yaml: "
                "consumers.registered_not_active_callers must match "
                "selected-not-active profile callers exactly",
                errors,
            )

    def test_activation_profile_must_own_the_selected_environment_binding(self) -> None:
        with tempfile.TemporaryDirectory(prefix="governed-ai-profile-") as temp_dir:
            repo_root = self.prepare_repo(Path(temp_dir))
            access_plane_path = repo_root / "security/governed-ai-access-plane.yaml"
            payload = yaml.safe_load(access_plane_path.read_text(encoding="utf-8"))
            payload["access_plane"]["activation_state"]["active_profile"] = "missing-profile"
            access_plane_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

            self.assertIn(
                "security/governed-ai-access-plane.yaml: activation_state.active_profile "
                "references unknown profile 'missing-profile'",
                validate(repo_root),
            )


class ModelProfileResolverTests(unittest.TestCase):
    def prepare_contracts(self, root: Path) -> tuple[Path, Path]:
        profile_path = root / "governed-ai-model-profiles.yaml"
        access_path = root / "governed-ai-access-plane.yaml"
        shutil.copy2(REPO_ROOT / "security/governed-ai-model-profiles.yaml", profile_path)
        shutil.copy2(REPO_ROOT / "security/governed-ai-access-plane.yaml", access_path)
        for schema_name in (
            "intake-classification-result.schema.json",
            "delivery-work-design-advice.schema.json",
            "delivery-refinement-advice.schema.json",
        ):
            schema_path = root / "security/schemas" / schema_name
            schema_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO_ROOT / "security/schemas" / schema_name, schema_path)
        return profile_path, access_path

    def resolve(self, root: Path, **overrides):
        profile_path, access_path = self.prepare_contracts(root)
        values = {
            "profile_id": "intake-classifier-v1",
            "environment": "dev-integration",
        }
        values.update(overrides)
        return resolve_model_profile(profile_path, access_path, **values)

    def test_selected_binding_evidence_is_deterministic_and_complete(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            root = Path(temp_dir)
            first = self.resolve(root, require_active=True)
            second = resolve_model_profile(
                root / "governed-ai-model-profiles.yaml",
                root / "governed-ai-access-plane.yaml",
                profile_id="intake-classifier-v1",
                environment="dev-integration",
                require_active=True,
            )

            self.assertEqual(first, second)
            self.assertEqual(first["binding_id"], "local-ollama-qwen3-8b")
            self.assertEqual(first["provider"], "ollama")
            self.assertEqual(first["fallback_mode"], "fail-closed-no-implicit-fallback")
            self.assertTrue(first["activation_eligible"])
            self.assertRegex(first["selection_digest"], r"^sha256:[0-9a-f]{64}$")
            self.assertEqual(
                first["selection_ref"],
                "model-binding-selection:" + first["selection_digest"].removeprefix("sha256:"),
            )

    def test_second_valid_profile_resolves_without_resolver_code_changes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            root = Path(temp_dir)
            profile_path, access_path = self.prepare_contracts(root)
            registry = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            access = yaml.safe_load(access_path.read_text(encoding="utf-8"))

            synthetic = copy.deepcopy(registry["model_profiles"]["intake-classifier-v1"])
            synthetic["purpose"] = "synthetic-governed-assist"
            synthetic["allowed_callers"] = ["synthetic/workflow"]
            synthetic["selected_binding_by_environment"]["dev-integration"] = "synthetic-ollama"
            synthetic["bindings"]["synthetic-ollama"] = synthetic["bindings"].pop(
                "local-ollama-qwen3-8b"
            )
            registry["model_profiles"]["synthetic-profile-v1"] = synthetic

            access_plane = access["access_plane"]
            access_plane["allowed_profiles"].append("synthetic-profile-v1")
            access_plane["provider_routes"][0]["allowed_profiles"].append(
                "synthetic-profile-v1"
            )
            access_plane["allowed_callers"].append(
                {
                    "caller_id": "synthetic/workflow",
                    "purpose": "synthetic-governed-assist",
                    "required_profile": "synthetic-profile-v1",
                    "required_provider_output_schema_ref": copy.deepcopy(
                        synthetic["provider_output_schema_ref"]
                    ),
                    "accepted_record_schema_ref": copy.deepcopy(
                        synthetic["accepted_record_schema_ref"]
                    ),
                    "allowed_task_kinds": ["intake_classification"],
                }
            )
            access_plane["activation_state"]["profile_activations"][
                "synthetic-profile-v1"
            ] = {
                "activation_allowed": True,
                "environment": "dev-integration",
                "binding": "synthetic-ollama",
                "reason": "synthetic-test",
            }
            access_plane["activation_state"]["active_binding"] = "synthetic-ollama"
            access_plane["activation_state"]["active_profile"] = "synthetic-profile-v1"
            profile_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
            access_path.write_text(yaml.safe_dump(access, sort_keys=False), encoding="utf-8")

            result = resolve_model_profile(
                profile_path,
                access_path,
                profile_id="synthetic-profile-v1",
                environment="dev-integration",
                require_active=True,
            )

            self.assertEqual(result["profile_id"], "synthetic-profile-v1")
            self.assertEqual(result["binding_id"], "synthetic-ollama")
            self.assertEqual(result["allowed_callers"], ["synthetic/workflow"])

    def test_profile_scoped_binding_id_cannot_bypass_activation_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            root = Path(temp_dir)
            profile_path, access_path = self.prepare_contracts(root)
            registry = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            access = yaml.safe_load(access_path.read_text(encoding="utf-8"))

            synthetic = copy.deepcopy(registry["model_profiles"]["intake-classifier-v1"])
            synthetic["purpose"] = "synthetic-governed-assist"
            synthetic["allowed_callers"] = ["synthetic/workflow"]
            registry["model_profiles"]["synthetic-profile-v1"] = synthetic

            access_plane = access["access_plane"]
            access_plane["allowed_profiles"].append("synthetic-profile-v1")
            access_plane["provider_routes"][0]["allowed_profiles"].append(
                "synthetic-profile-v1"
            )
            access_plane["allowed_callers"].append(
                {
                    "caller_id": "synthetic/workflow",
                    "purpose": "synthetic-governed-assist",
                    "required_profile": "synthetic-profile-v1",
                    "required_provider_output_schema_ref": copy.deepcopy(
                        synthetic["provider_output_schema_ref"]
                    ),
                    "accepted_record_schema_ref": copy.deepcopy(
                        synthetic["accepted_record_schema_ref"]
                    ),
                    "allowed_task_kinds": ["intake_classification"],
                }
            )
            profile_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")
            access_path.write_text(yaml.safe_dump(access, sort_keys=False), encoding="utf-8")

            with self.assertRaisesRegex(
                ModelProfileResolutionError,
                "profile_activations.synthetic-profile-v1 must be a mapping",
            ):
                resolve_model_profile(
                    profile_path,
                    access_path,
                    profile_id="synthetic-profile-v1",
                    environment="dev-integration",
                    require_active=True,
                )

    def test_unknown_profile_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            with self.assertRaisesRegex(
                ModelProfileResolutionError, "unknown governed model profile"
            ):
                self.resolve(Path(temp_dir), profile_id="missing-profile")

    def test_inactive_profile_is_not_activation_eligible(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            root = Path(temp_dir)
            profile_path, access_path = self.prepare_contracts(root)
            registry = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            registry["model_profiles"]["intake-classifier-v1"]["status"] = "suspended"
            profile_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

            inspection = resolve_model_profile(
                profile_path,
                access_path,
                profile_id="intake-classifier-v1",
                environment="dev-integration",
            )
            self.assertFalse(inspection["activation_eligible"])
            self.assertIn("profile-not-active", inspection["activation_denial_reasons"])
            with self.assertRaisesRegex(ModelProfileResolutionError, "profile-not-active"):
                resolve_model_profile(
                    profile_path,
                    access_path,
                    profile_id="intake-classifier-v1",
                    environment="dev-integration",
                    require_active=True,
                )

    def test_work_design_profile_resolves_as_active_devint_binding(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            profile_path, access_path = self.prepare_contracts(Path(temp_dir))

            result = resolve_model_profile(
                profile_path,
                access_path,
                profile_id="delivery-work-design-advisor-v1",
                environment="dev-integration",
            )

            self.assertEqual(result["profile_status"], "active")
            self.assertTrue(result["profile_activation_allowed"])
            self.assertTrue(result["activation_eligible"])
            self.assertIsNone(result["default_task_kind"])
            self.assertEqual(
                set(result["task_contracts"]), {"context_advice", "tree_advice"}
            )

    def test_registry_resolution_preserves_independent_profile_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            profile_path, access_path = self.prepare_contracts(Path(temp_dir))

            result = resolve_model_profile_registry(
                profile_path,
                access_path,
                environment="dev-integration",
            )

            self.assertEqual(
                set(result["profiles"]),
                {
                    "intake-classifier-v1",
                    "delivery-work-design-advisor-v1",
                    "delivery-refinement-advisor-v1",
                },
            )
            self.assertTrue(
                result["profiles"]["intake-classifier-v1"]["activation_eligible"]
            )
            self.assertTrue(
                result["profiles"]["delivery-work-design-advisor-v1"][
                    "activation_eligible"
                ]
            )
            self.assertFalse(
                result["profiles"]["delivery-refinement-advisor-v1"][
                    "activation_eligible"
                ]
            )
            self.assertRegex(
                result["registry_selection_digest"], r"^sha256:[0-9a-f]{64}$"
            )

    def test_refinement_profile_resolves_but_cannot_activate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            profile_path, access_path = self.prepare_contracts(Path(temp_dir))

            result = resolve_model_profile(
                profile_path,
                access_path,
                profile_id="delivery-refinement-advisor-v1",
                environment="dev-integration",
            )

            self.assertEqual(result["profile_status"], "selected-not-active")
            self.assertEqual(result["binding_status"], "selected-not-active")
            self.assertFalse(result["profile_activation_allowed"])
            self.assertFalse(result["activation_eligible"])
            self.assertEqual(result["default_task_kind"], "metadata_advice")
            self.assertEqual(set(result["task_contracts"]), {"metadata_advice"})
            self.assertIn("profile-not-active", result["activation_denial_reasons"])
            with self.assertRaisesRegex(ModelProfileResolutionError, "profile-not-active"):
                resolve_model_profile(
                    profile_path,
                    access_path,
                    profile_id="delivery-refinement-advisor-v1",
                    environment="dev-integration",
                    require_active=True,
                )

    def test_refinement_provider_output_rejects_empty_field_key(self) -> None:
        schema = json.loads(
            (
                REPO_ROOT
                / "security/schemas/delivery-refinement-advice.schema.json"
            ).read_text(encoding="utf-8")
        )
        output = {
            "confidence": "medium",
            "required_operator_action": "review",
            "field_key": "",
            "value": "Example",
            "summary": "A bounded suggestion.",
            "rationale": "The current metadata is incomplete.",
        }

        with self.assertRaisesRegex(OutputSchemaError, "field_key is shorter"):
            validate_output(output, schema)

    def test_missing_environment_binding_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            with self.assertRaisesRegex(
                ModelProfileResolutionError,
                "selected_binding_by_environment.stage must be a non-empty string",
            ):
                self.resolve(Path(temp_dir), environment="stage")

    def test_selected_inactive_binding_does_not_fallback(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            root = Path(temp_dir)
            profile_path, access_path = self.prepare_contracts(root)
            registry = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            profile = registry["model_profiles"]["intake-classifier-v1"]
            selected = profile["bindings"]["local-ollama-qwen3-8b"]
            selected["status"] = "selected-not-active"
            profile["bindings"]["unused-active-binding"] = copy.deepcopy(selected)
            profile["bindings"]["unused-active-binding"]["status"] = "active"
            profile_path.write_text(yaml.safe_dump(registry, sort_keys=False), encoding="utf-8")

            with self.assertRaisesRegex(ModelProfileResolutionError, "binding-not-active"):
                resolve_model_profile(
                    profile_path,
                    access_path,
                    profile_id="intake-classifier-v1",
                    environment="dev-integration",
                    require_active=True,
                )

    def test_provider_route_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            root = Path(temp_dir)
            profile_path, access_path = self.prepare_contracts(root)
            access = yaml.safe_load(access_path.read_text(encoding="utf-8"))
            access["access_plane"]["provider_routes"][0]["provider"] = "different-provider"
            access_path.write_text(yaml.safe_dump(access, sort_keys=False), encoding="utf-8")

            with self.assertRaisesRegex(ModelProfileResolutionError, "does not match route provider"):
                resolve_model_profile(
                    profile_path,
                    access_path,
                    profile_id="intake-classifier-v1",
                    environment="dev-integration",
                )

    def test_direct_provider_access_must_remain_prohibited(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            root = Path(temp_dir)
            profile_path, access_path = self.prepare_contracts(root)
            registry = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            registry["model_profiles"]["intake-classifier-v1"][
                "direct_provider_access_allowed"
            ] = True
            profile_path.write_text(
                yaml.safe_dump(registry, sort_keys=False), encoding="utf-8"
            )

            with self.assertRaisesRegex(
                ModelProfileResolutionError, "must prohibit direct provider access"
            ):
                resolve_model_profile(
                    profile_path,
                    access_path,
                    profile_id="intake-classifier-v1",
                    environment="dev-integration",
                )

    def test_human_approval_must_remain_required(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            root = Path(temp_dir)
            profile_path, access_path = self.prepare_contracts(root)
            registry = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
            registry["model_profiles"]["intake-classifier-v1"][
                "human_approval_required"
            ] = False
            profile_path.write_text(
                yaml.safe_dump(registry, sort_keys=False), encoding="utf-8"
            )

            with self.assertRaisesRegex(
                ModelProfileResolutionError, "must require human approval"
            ):
                resolve_model_profile(
                    profile_path,
                    access_path,
                    profile_id="intake-classifier-v1",
                    environment="dev-integration",
                )

    def test_caller_purpose_must_match_profile(self) -> None:
        with tempfile.TemporaryDirectory(prefix="model-profile-resolution-") as temp_dir:
            root = Path(temp_dir)
            profile_path, access_path = self.prepare_contracts(root)
            access = yaml.safe_load(access_path.read_text(encoding="utf-8"))
            access["access_plane"]["allowed_callers"][0]["purpose"] = "different-purpose"
            access_path.write_text(
                yaml.safe_dump(access, sort_keys=False), encoding="utf-8"
            )

            with self.assertRaisesRegex(
                ModelProfileResolutionError, "purpose does not match profile"
            ):
                resolve_model_profile(
                    profile_path,
                    access_path,
                    profile_id="intake-classifier-v1",
                    environment="dev-integration",
                )


if __name__ == "__main__":
    unittest.main()
