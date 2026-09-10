#!/usr/bin/env python3
"""Filesystem conformance for the selected Prototype Maturity identity."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import yaml

import prototype_maturity_identity as module
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
        self.assertTrue(result["workflow_runtime_enabled"])
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
            ("readiness_runtime.deployment", "unrelated"),
            ("readiness_runtime.container", "unrelated"),
            ("readiness_runtime.enabled_env", "UNRELATED_ENABLED"),
            (
                "readiness_runtime.service_identity_env",
                "UNRELATED_SERVICE_IDENTITY_REF",
            ),
            ("activation.security_gate", None),
            ("activation.required_evidence", []),
            ("activation.workflow_runtime_enabled", False),
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
        self.assertTrue(result["workflow_runtime_enabled"])

    def test_rejected_secret_is_not_logged(self):
        self.source["token"] = "sensitive-test-value"
        self.write(self.source)
        command = [
            sys.executable,
            str(Path(__file__).with_name("prototype_maturity_identity.py")),
            "--contract",
            str(self.path),
            "validate",
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(1, result.returncode)
        self.assertNotIn("sensitive-test-value", result.stdout + result.stderr)
        self.assertIn("invalid-identity-definition", result.stdout)

    def test_runtime_projection_is_active_and_isolated_from_landing(self):
        contract = module.load_contract(DEFAULT_CONTRACT)
        runtime = module.RuntimeInputs(
            authority_root=Path("/workspace/workspace-prototype-studio"),
            state_root=Path("/session/prototype-maturity/state"),
            wgcf_base_url="http://workspace-governance-control-fabric-api.test.svc.cluster.local",
            wgcf_caller_secret="not-rendered",
        )
        patch = json.loads(module.deployment_patch(contract, runtime))
        container = patch["spec"]["template"]["spec"]["containers"][0]
        env = {item["name"]: item for item in container["env"]}
        mounts = {item["name"]: item for item in container["volumeMounts"]}
        self.assertEqual("true", env["OOS_PROTOTYPE_MATURITY_ENABLED"]["value"])
        self.assertNotIn("OOS_PROTOTYPE_LANDING_ENABLED", env)
        self.assertTrue(mounts["prototype-maturity-identity"]["readOnly"])
        self.assertTrue(mounts["prototype-maturity-authority"]["readOnly"])
        self.assertIn("prototype-maturity-state", mounts)
        self.assertNotIn("prototype-landing-identity", mounts)

        readiness = json.loads(module.workflow.readiness_runtime_patch(contract, enabled=True))
        readiness_container = readiness["spec"]["template"]["spec"]["containers"][0]
        self.assertEqual("api", readiness_container["name"])
        readiness_env = {item["name"]: item for item in readiness_container["env"]}
        self.assertEqual(
            "true",
            readiness_env["WGCF_PROTOTYPE_MATURITY_READINESS_ENABLED"]["value"],
        )
        self.assertEqual(
            "service-identity://workspace-governance-control-fabric/dev-integration",
            readiness_env["WGCF_PROTOTYPE_MATURITY_SERVICE_IDENTITY_REF"]["value"],
        )
        self.assertNotIn("WGCF_PROTOTYPE_LANDING_READINESS_ENABLED", readiness_env)

        readiness_suspended = json.loads(
            module.workflow.readiness_runtime_patch(contract, enabled=False)
        )
        self.assertEqual(
            "false",
            readiness_suspended["spec"]["template"]["spec"]["containers"][0][
                "env"
            ][0]["value"],
        )
        readiness_revoked = json.loads(
            module.workflow.readiness_runtime_patch(contract, enabled=None)
        )
        self.assertEqual(
            {"$patch": "delete", "name": "WGCF_PROTOTYPE_MATURITY_READINESS_ENABLED"},
            readiness_revoked["spec"]["template"]["spec"]["containers"][0][
                "env"
            ][0],
        )
        self.assertEqual(
            "test",
            module.workflow.readiness_namespace(runtime.wgcf_base_url),
        )

    def test_readiness_runtime_reconciliation_is_ordered_and_exact(self):
        contract = module.load_contract(DEFAULT_CONTRACT)
        commands = []
        workspace = Path(self.temp.name) / "workspace"
        readiness_manifest = (
            workspace
            / ".dev-integration/governance-control-fabric/test-operator/current-session.yaml"
        )
        readiness_manifest.parent.mkdir(parents=True)
        readiness_manifest.write_text(
            "schema_version: 1\nlane: dev-integration\n"
            "profile_id: governance-control-fabric\nprofile_lifecycle: active\n"
            "runtime_owner: platform-engineering\naction: up\n"
            "operator: test-operator\n"
            "namespace: devint-governance-control-fabric-test-operator\n"
            "session_id: governance-control-fabric-test-operator-20260910T000000Z\n"
        )
        readiness_manifest.chmod(0o600)
        target = module.workflow.DevIntegrationTarget(
            profile_id="accepted-idea-delivery",
            operator="test-operator",
            session_id="accepted-idea-delivery-test-operator-20260910T000000Z",
            namespace="devint-accepted-idea-delivery-test-operator",
            cluster_server="https://127.0.0.1:6443",
        )

        def capture(_kubectl, arguments, **_kwargs):
            commands.append(arguments)

        with mock.patch.object(module.workflow, "run_kubectl", side_effect=capture):
            module.workflow.reconcile_readiness_runtime(
                "k3s kubectl",
                contract,
                "http://workspace-governance-control-fabric-api.devint-governance-control-fabric-test-operator.svc.cluster.local:8080",
                workspace,
                target,
                enabled=True,
                require_running=True,
            )

        self.assertEqual("patch", commands[0][2])
        self.assertEqual("workspace-governance-control-fabric-api", commands[0][4])
        self.assertEqual("rollout", commands[1][2])
        self.assertEqual("devint-governance-control-fabric-test-operator", commands[0][1])

        with self.assertRaisesRegex(
            module.workflow.IdentityError,
            "WGCF base URL is required",
        ):
            module.workflow.validate_readiness_runtime_target(
                contract,
                None,
                workspace,
                target,
                require_running=True,
            )

        with self.assertRaisesRegex(
            module.workflow.IdentityError,
            "active operator session",
        ):
            module.workflow.validate_readiness_runtime_target(
                contract,
                "http://workspace-governance-control-fabric-api.devint-governance-control-fabric-other-operator.svc.cluster.local:8080",
                workspace,
                target,
                require_running=True,
            )

        suspended = json.loads(module.deployment_suspend_patch(contract))
        suspended_env = suspended["spec"]["template"]["spec"]["containers"][0][
            "env"
        ]
        self.assertEqual(
            [{"name": "OOS_PROTOTYPE_MATURITY_ENABLED", "value": "false"}],
            suspended_env,
        )
        revoked = json.loads(module.deployment_revoke_patch(contract))
        revoked_container = revoked["spec"]["template"]["spec"]["containers"][0]
        revoked_env = {item["name"] for item in revoked_container["env"]}
        self.assertIn("OOS_PROTOTYPE_MATURITY_ENABLED", revoked_env)
        self.assertNotIn("OOS_PROTOTYPE_LANDING_ENABLED", revoked_env)
        self.assertNotIn("OOS_RUNTIME_PROFILE", revoked_env)

    def test_activation_revisions_are_exact(self):
        contract = module.load_contract(DEFAULT_CONTRACT)
        exact = {
            "operator-orchestration-service": "6e47866e041cd62406ef2d646ced846b1cb0a5a4",
            "workspace-governance-control-fabric": "4136e643dc05b0df02cf860c3cbd3052fae8df55",
            "security-architecture": "087118a5f79034684f0ca895a85cb735d1298627",
        }
        module.workflow.validate_activation_source_revisions(contract, exact)
        for repository in exact:
            with self.subTest(repository=repository):
                changed = dict(exact)
                changed[repository] = "0" * 40
                with self.assertRaisesRegex(
                    module.workflow.IdentityError,
                    "activation source revisions do not match",
                ):
                    module.workflow.validate_activation_source_revisions(
                        contract, changed
                    )

    def test_receipt_and_secret_metadata_are_maturity_specific(self):
        contract = module.load_contract(DEFAULT_CONTRACT)
        repository = module.workflow.ProviderRepository(
            contract.repository, contract.repository_id
        )
        value = module.workflow.receipt(
            contract,
            action="commission",
            app_id=1,
            installation_id=2,
            repository=repository,
            outcome="verified-and-proof-token-revoked",
            source_revisions={"platform-engineering": "a" * 40},
            caller_id="operator:test",
        )
        self.assertEqual("prototype-maturity-identity-receipt", value["artifact_type"])
        self.assertFalse(value["secret_values_embedded"])


if __name__ == "__main__":
    unittest.main()
