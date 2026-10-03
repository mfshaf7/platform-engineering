#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("console_cross_domain_activation.py")
SPEC = importlib.util.spec_from_file_location("console_cross_domain_activation", SCRIPT)
assert SPEC and SPEC.loader
activation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(activation)


class CrossDomainActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = activation.load_policy()
        self.catalog_policy = activation.load_policy(
            activation.PRODUCT_ROOT / "repository-catalog-commissioning-policy.yaml"
        )

    def test_policy_pins_two_distinct_owner_sources(self) -> None:
        owners = self.policy["owners"]
        self.assertEqual(owners["oos"]["repo"], "operator-orchestration-service")
        self.assertEqual(owners["wgcf"]["repo"], "workspace-governance-control-fabric")
        self.assertNotEqual(owners["oos"]["local_port"], owners["wgcf"]["local_port"])
        self.assertEqual(len(owners["oos"]["revision"]), 40)
        self.assertEqual(len(owners["wgcf"]["revision"]), 40)
        self.assertEqual(self.policy["schema_version"], 2)
        self.assertEqual(
            self.policy["activation"]["security_gate_id"],
            "gate:intake-inventory-controlled-activation",
        )
        self.assertIn(
            "workspace-intake-or-inventory-operating-readiness",
            self.policy["proof_scope"]["excludes"],
        )

    def test_policy_pins_exact_architecture_supersession(self) -> None:
        architecture = self.policy["architecture"]
        review = "\n".join([
            architecture["current"]["uri"],
            architecture["predecessor"]["uri"],
            self.policy["console"]["revision"],
            self.policy["owners"]["oos"]["revision"],
            self.policy["owners"]["wgcf"]["revision"],
            self.policy["authority"]["workspace_governance_revision"],
        ])
        activation.require_architecture_binding(self.policy, review)
        with self.assertRaisesRegex(activation.ActivationError, "predecessor"):
            activation.require_architecture_binding(
                self.policy,
                review.replace(architecture["predecessor"]["uri"], "missing"),
            )

    def test_validation_reads_security_review_text(self) -> None:
        architecture = self.policy["architecture"]
        review = "\n".join([
            architecture["current"]["uri"],
            architecture["predecessor"]["uri"],
            self.policy["console"]["revision"],
            self.policy["owners"]["oos"]["revision"],
            self.policy["owners"]["wgcf"]["revision"],
            self.policy["authority"]["workspace_governance_revision"],
        ])
        completed = activation.subprocess.CompletedProcess([], 0, stdout=review, stderr="")
        with (
            patch.object(activation, "operator", return_value="operator"),
            patch.object(activation, "require_revision"),
            patch.object(activation, "require_manifest"),
            patch.object(activation, "require_clean_platform_source"),
            patch.object(activation, "repo_path", return_value=Path("/security")),
            patch.object(activation, "run", return_value=completed),
        ):
            activation.validate(self.policy)

    def test_repo_path_override_is_explicit_and_absolute(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved = activation.parse_repo_paths([f"workspace-governance={temp_dir}"])
            self.assertEqual(resolved["workspace-governance"], Path(temp_dir).resolve())
        with self.assertRaisesRegex(activation.ActivationError, "absolute repository path"):
            activation.parse_repo_paths(["workspace-governance=relative"])

    def test_units_keep_credentials_in_private_environment_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            units = root / "units"
            console = root / "console"
            console.mkdir()
            env_file = root / "private" / "console.env"
            env_file.parent.mkdir()
            env_file.write_text("OOS_CALLER_SECRET=secret\n", encoding="utf-8")
            with (
                patch.object(activation, "UNIT_ROOT", units),
                patch.object(activation, "repo_path", return_value=console),
                patch.object(activation, "run"),
                patch.object(activation, "operator", return_value="operator"),
                patch.object(
                    activation.shutil,
                    "which",
                    side_effect=lambda command: f"/tools/{command}",
                ),
            ):
                activation.write_units(self.policy, env_file)
            console_unit = (units / activation.unit_name("console")).read_text(encoding="utf-8")
            self.assertIn(f"EnvironmentFile={env_file}", console_unit)
            self.assertIn("ExecStart=/tools/npm run dev", console_unit)
            self.assertNotIn("secret", console_unit)
            self.assertIn("Wants=governance-console-cross-domain-oos.service", console_unit)

    def test_receipt_contains_source_proof_but_no_credentials(self) -> None:
        activity = {
            "mode": "live",
            "status": "current",
            "sources": [
                {"owner": "operator-orchestration-service", "state": "current"},
                {"owner": "workspace-governance-control-fabric", "state": "current"},
            ],
            "events": [{"eventId": "one"}],
            "observedAt": "2026-09-28T00:00:00Z",
            "truncated": False,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(activation, "RECEIPT_ROOT", Path(temp_dir)),
                patch.object(activation, "operator", return_value="operator"),
                patch.object(activation, "git_head", return_value="a" * 40),
            ):
                path = activation.receipt(
                    "status",
                    self.policy,
                    activity,
                    runtime_boundary={
                        "services_active": True,
                        "wgcf_reader_binding_present": True,
                    },
                )
            value = json.loads(path.read_text(encoding="utf-8"))
            serialized = json.dumps(value).casefold()
            self.assertEqual(value["result"], "succeeded")
            self.assertEqual(value["live_proof"]["event_count"], 1)
            self.assertEqual(
                value["architecture"]["current"]["digest"],
                self.policy["architecture"]["current"]["digest"],
            )
            self.assertFalse(value["credential_boundary"]["credentials_embedded"])
            self.assertEqual(value["proof_scope"], self.policy["proof_scope"])
            self.assertEqual(value["source_revisions"]["platform-engineering"], "a" * 40)
            self.assertTrue(value["runtime_boundary"]["services_active"])
            self.assertTrue(value["runtime_boundary"]["wgcf_reader_binding_present"])
            self.assertNotIn("caller_secret", serialized)
            self.assertNotIn("token_urlsafe", serialized)

    def test_live_proof_rejects_fixture_authority(self) -> None:
        fixture = {
            "mode": "live",
            "status": "current",
            "sources": [
                {"owner": "operator-orchestration-service", "state": "current"},
                {"owner": "workspace-governance-control-fabric", "state": "current"},
            ],
            "events": [{"source": {"mode": "prototype-local"}}],
        }
        with (
            patch.object(activation, "http_json", return_value=fixture),
            patch.object(activation.time, "sleep"),
            patch.object(activation.time, "monotonic", side_effect=[0, 1, 181]),
        ):
            with self.assertRaisesRegex(activation.ActivationError, "fixture authority"):
                activation.wait_for_activity(self.policy)

    def test_repository_catalog_policy_binds_exact_security_approved_sources(self) -> None:
        policy = self.catalog_policy
        self.assertEqual(
            policy["activation"]["security_gate_id"],
            "gate:repository-catalog-controlled-activation",
        )
        self.assertEqual(policy["architecture"]["relationship"], "exact-security-binding")
        self.assertEqual(
            policy["owners"]["oos"]["revision"],
            "92f0967242f535b46aad9e585c72694c6ff1863b",
        )
        self.assertEqual(
            policy["console"]["revision"],
            "9347794a138f3649bb6ef5b7db057524d1c1e26d",
        )
        self.assertFalse(policy["credentials"]["browser_credentials_allowed"])
        self.assertIn("first-use-repository-readiness-issuance", policy["proof_scope"]["includes"])

    def test_exact_security_binding_requires_current_packet_and_revisions(self) -> None:
        policy = self.catalog_policy
        review = "\n".join([
            policy["architecture"]["current"]["uri"],
            policy["console"]["revision"],
            policy["owners"]["oos"]["revision"],
            policy["owners"]["wgcf"]["revision"],
            policy["authority"]["workspace_governance_revision"],
        ])
        activation.require_architecture_binding(policy, review)
        with self.assertRaisesRegex(activation.ActivationError, "current"):
            activation.require_architecture_binding(
                policy,
                review.replace(policy["architecture"]["current"]["uri"], "missing"),
            )

    def test_catalog_environment_adds_server_only_session_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (
                patch.object(activation, "PRIVATE_ROOT", root / "private"),
                patch.object(activation, "STATE_ROOT", root),
            ):
                path = activation.write_private_env(
                    self.catalog_policy,
                    "o" * 40,
                    "w" * 40,
                )
            value = path.read_text(encoding="utf-8")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn("GOVERNANCE_CONSOLE_OPERATOR_ID=operator:workspace-owner", value)
            self.assertIn("GOVERNANCE_CONSOLE_SESSION_PROJECTION_PATH=", value)
            self.assertNotIn("BROWSER", value)

    def test_catalog_command_separates_first_use_from_existing_reference(self) -> None:
        record = {
            "id": "workspace-registry-record:repo:context-governance-gateway",
            "lineage": {"source_ref": "git://workspace-governance/contracts/repos.yaml"},
        }
        first = activation.catalog_command(
            "context-governance-gateway",
            record,
            mode="add",
            target_value_id=None,
            prefix="first-use",
        )
        self.assertNotIn("repositoryReadiness", first)
        readiness = {
            "catalog_value_key": "context-governance-gateway",
            "repo_name": "context-governance-gateway",
            "repo_ref": "repo://context-governance-gateway",
            "receipt": {"digest": "sha256:" + "1" * 64},
        }
        existing = activation.catalog_command(
            "context-governance-gateway",
            record,
            mode="edit",
            target_value_id="catalog-value:one",
            readiness=readiness,
            prefix="existing-reference",
        )
        self.assertEqual(existing["repositoryReadiness"], readiness)
        self.assertEqual(existing["targetValueId"], "catalog-value:one")

    def test_denial_proof_cannot_accept_success(self) -> None:
        with self.assertRaisesRegex(activation.ActivationError, "did not fail closed"):
            activation.require_denied(200, {"status": "applied"}, "false success")


if __name__ == "__main__":
    unittest.main()
