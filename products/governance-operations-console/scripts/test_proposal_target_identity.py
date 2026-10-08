#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest

import yaml


SCRIPT = Path(__file__).with_name("proposal_target_identity.py")
SPEC = importlib.util.spec_from_file_location("proposal_target_identity", SCRIPT)
assert SPEC and SPEC.loader
identity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(identity)


class ProposalTargetIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = identity.load_contract(identity.DEFAULT_CONTRACT)

    def test_contract_is_exact_repository_and_workflow_specific(self) -> None:
        value = identity.validate_definition(identity.DEFAULT_CONTRACT)
        self.assertEqual(value["identity_id"], "proposal-target-github-app-v1")
        self.assertEqual(self.contract.repository, "mfshaf7/workspace-prototype-studio")
        self.assertEqual(self.contract.workflow_slug, "proposal-target-application")
        self.assertEqual(
            self.contract.allowed_dev_integration_profiles,
            ("accepted-idea-delivery",),
        )
        self.assertTrue(self.contract.workflow_runtime_enabled)
        self.assertIsNone(self.contract.wgcf_base_url_env)
        self.assertIsNone(self.contract.wgcf_secret_key)

    def test_runtime_patch_projects_only_target_identity_and_owner_source(self) -> None:
        runtime = identity.RuntimeInputs(
            authority_root=Path("/workspace/workspace-prototype-studio"),
            state_root=Path("/state/proposal-target-application"),
        )
        patch = json.loads(identity.deployment_patch(self.contract, runtime))
        pod = patch["spec"]["template"]["spec"]
        container = pod["containers"][0]
        env = {item["name"]: item for item in container["env"]}
        self.assertEqual(env["OOS_PROPOSAL_TARGET_APPLICATION_ENABLED"]["value"], "true")
        self.assertEqual(
            env["OOS_PROPOSAL_TARGET_APPLICATION_TOKEN_FILE"]["value"],
            "/var/run/oos/proposal-target-application/installation-token",
        )
        self.assertNotIn("WGCF_PROPOSAL_TARGET_APPLICATION_CALLER_SECRET", env)
        self.assertEqual(
            {item["name"] for item in pod["volumes"]},
            {
                "proposal-target-application-identity",
                "proposal-target-application-state",
                "proposal-target-application-authority",
            },
        )

    def test_source_revision_set_is_closed_and_exact(self) -> None:
        expected = self.contract.approved_source_revisions
        identity.workflow.validate_activation_source_revisions(
            self.contract,
            dict(sorted(expected.items())),
        )
        wrong = dict(expected)
        wrong["operator-orchestration-service"] = "0" * 40
        with self.assertRaisesRegex(Exception, "exact approved source set"):
            identity.workflow.validate_activation_source_revisions(
                self.contract,
                dict(sorted(wrong.items())),
            )

    def test_security_revision_matches_commissioning_policy(self) -> None:
        policy_path = SCRIPT.parent.parent / "proposal-target-commissioning-policy.yaml"
        policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
        expected = policy["authority"]["security_revision"]
        self.assertEqual(self.contract.normal_availability_review_revision, expected)
        self.assertEqual(
            self.contract.approved_source_revisions["security-architecture"],
            expected,
        )

    def test_revoke_patch_removes_only_proposal_target_bindings(self) -> None:
        patch = json.loads(identity.deployment_revoke_patch(self.contract))
        pod = patch["spec"]["template"]["spec"]
        env = {item["name"] for item in pod["containers"][0]["env"]}
        self.assertIn("OOS_PROPOSAL_TARGET_APPLICATION_ENABLED", env)
        self.assertNotIn("OOS_PROTOTYPE_LANDING_ENABLED", env)
        self.assertEqual(
            {item["name"] for item in pod["volumes"]},
            {
                "proposal-target-application-identity",
                "proposal-target-application-state",
                "proposal-target-application-authority",
            },
        )


if __name__ == "__main__":
    unittest.main()
