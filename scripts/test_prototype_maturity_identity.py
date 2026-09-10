#!/usr/bin/env python3
"""Filesystem conformance for the selected Prototype Maturity identity."""

import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

from prototype_maturity_identity import DEFAULT_CONTRACT, validate_definition


class DefinitionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "identity.yaml"
        self.source = yaml.safe_load(DEFAULT_CONTRACT.read_text())

    def write(self, value):
        self.path.write_text(yaml.safe_dump(value, sort_keys=False))

    def test_selected_definition_and_stable_validation(self):
        self.write(self.source)
        original = self.path.read_bytes()
        result = validate_definition(self.path)
        self.assertEqual(result, validate_definition(self.path))
        self.assertEqual("selected-not-active", result["state"])
        self.assertFalse(result["identity_projection_enabled"])
        self.assertFalse(result["workflow_runtime_enabled"])
        self.assertFalse(result["provider_verified"])
        self.assertEqual(original, self.path.read_bytes())

    def test_denials_and_restore(self):
        mutations = [
            ("identity.id", "prototype-landing-github-app-v1"),
            ("identity.repository_selection", "all"),
            ("identity.repository.full_name", "mfshaf7/unrelated"),
            ("identity.repository.id", 2),
            ("identity.maximum_repository_count", 2),
            ("identity.required_permissions.administration", "write"),
            ("identity.required_permissions.checks", "write"),
            ("identity.credential_kind", "personal-token"),
            ("identity.api_base_url", "https://other.invalid"),
            ("identity.maximum_token_lifetime_seconds", 7200),
            ("selection.runtime_enabled", True),
            ("selection.app_id", 1),
            ("security_authority.review.ref", "openproject://work_packages/1125"),
            ("security_authority.review.revision", "0" * 40),
            ("security_authority.standards.paths", []),
            ("security_authority.final_normal_availability_gate", None),
            ("source_boundary.allowed_branch_pattern", ".*"),
            ("source_boundary.allowed_write_paths", ["prototypes/**"]),
            ("source_boundary.merge_authority", "oos"),
            ("source_boundary.provider_enforcement_required", []),
            ("source_boundary.denied_actions", []),
            (
                "secret_custody.private_key_source.path",
                "components/operator-orchestration-service/dev-integration/prototype-landing",
            ),
            ("secret_custody.values_in_receipts", True),
            ("secret_custody.private_key_in_oos", True),
            ("secret_custody.runtime_projection.sub_path_allowed", True),
            ("consumer.runtime_lane", "prod"),
            ("consumer.token_file_env", "OOS_PROTOTYPE_LANDING_TOKEN_FILE"),
            ("activation.security_gate", None),
            ("activation.required_evidence", []),
            ("activation.workflow_runtime_enabled", True),
            ("audit.receipt_fields", []),
            ("rollback.revoke_issued_token", False),
            ("rollback.preserve_prototype_landing_identity", False),
        ]
        for dotted, value in mutations:
            with self.subTest(field=dotted):
                changed = copy.deepcopy(self.source)
                target = changed
                parts = dotted.split(".")
                for key in parts[:-1]:
                    target = target[key]
                target[parts[-1]] = value
                self.write(changed)
                with self.assertRaises(ValueError):
                    validate_definition(self.path)
        self.write(self.source)
        result = validate_definition(self.path)
        self.assertFalse(result["identity_projection_enabled"])
        self.assertFalse(result["workflow_runtime_enabled"])

    def test_rejected_secret_is_not_logged(self):
        self.source["token"] = "sensitive-test-value"
        self.write(self.source)
        command = [
            sys.executable,
            str(Path(__file__).with_name("prototype_maturity_identity.py")),
            "validate",
            "--contract",
            str(self.path),
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(1, result.returncode)
        self.assertNotIn("sensitive-test-value", result.stdout + result.stderr)
        self.assertIn("invalid-identity-definition", result.stdout)


if __name__ == "__main__":
    unittest.main()
