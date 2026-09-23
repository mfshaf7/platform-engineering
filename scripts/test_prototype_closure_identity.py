#!/usr/bin/env python3
"""Filesystem conformance for the selected Prototype Closure identity."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

import yaml

import prototype_closure_identity as module


class PrototypeClosureIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.definition = yaml.safe_load(module.DEFAULT_CONTRACT.read_text())

    def test_selected_definition_is_stable_and_source_activated(self) -> None:
        original = module.DEFAULT_CONTRACT.read_bytes()
        result = module.validate_definition(module.DEFAULT_CONTRACT)
        self.assertEqual(result, module.validate_definition(module.DEFAULT_CONTRACT))
        self.assertEqual("selected-not-active", result["state"])
        self.assertFalse(result["identity_projection_enabled"])
        self.assertTrue(result["workflow_runtime_enabled"])
        self.assertFalse(result["provider_verified"])
        self.assertEqual(original, module.DEFAULT_CONTRACT.read_bytes())

    def test_definition_rejects_broader_or_cross_workflow_authority(self) -> None:
        mutations = [
            ("identity.id", "prototype-maturity-github-app-v1"),
            ("identity.maximum_repository_count", 2),
            ("identity.required_permissions.administration", "write"),
            ("source_boundary.allowed_write_paths", ["prototypes/**"]),
            ("source_boundary.merge_authority", "operator-orchestration-service"),
            ("source_boundary.operator_authorization.reauthorize_on_change", False),
            ("secret_custody.runtime_projection.sub_path_allowed", True),
            ("consumer.runtime_lane", "prod"),
            ("consumer.platform_evidence_file_env", "UNRELATED"),
            ("readiness_runtime.oos_url_env", "UNRELATED"),
            ("activation.security_gate", None),
            ("activation.workflow_runtime_enabled", False),
            ("rollback.preserve_prototype_maturity_identity", False),
            ("rollback.delete_durable_owner_source", True),
        ]
        for dotted, value in mutations:
            with self.subTest(field=dotted):
                changed = copy.deepcopy(self.definition)
                target = changed
                parts = dotted.split(".")
                for key in parts[:-1]:
                    target = target[key]
                target[parts[-1]] = value
                path = self.root / "changed.yaml"
                path.write_text(yaml.safe_dump(changed, sort_keys=False))
                with self.assertRaises(ValueError):
                    module.validate_definition(path)

    def test_runtime_projection_binds_platform_evidence_and_owner_readback(self) -> None:
        contract = module.load_contract(module.DEFAULT_CONTRACT)
        runtime = module.RuntimeInputs(
            authority_root=Path("/workspace/workspace-prototype-studio"),
            state_root=Path("/session/prototype-closure/state"),
            wgcf_base_url=(
                "http://workspace-governance-control-fabric-api."
                "devint-governance-control-fabric-test.svc.cluster.local"
            ),
            wgcf_caller_secret="not-rendered",
            oos_reader_secret="not-rendered-reader",
        )
        patch = json.loads(module.deployment_patch(contract, runtime))
        container = patch["spec"]["template"]["spec"]["containers"][0]
        env = {entry["name"]: entry for entry in container["env"]}
        self.assertEqual("true", env["OOS_PROTOTYPE_CLOSURE_ENABLED"]["value"])
        self.assertEqual(
            "/var/lib/oos/prototype-closure/state/platform-evidence.json",
            env["OOS_PROTOTYPE_CLOSURE_PLATFORM_EVIDENCE_FILE"]["value"],
        )
        self.assertNotIn(runtime.wgcf_caller_secret, json.dumps(patch))
        self.assertNotIn(runtime.oos_reader_secret, json.dumps(patch))

        oos_url = (
            "http://operator-orchestration-service."
            "devint-accepted-idea-delivery-test.svc.cluster.local:8080"
        )
        readiness = json.loads(
            module.workflow.readiness_runtime_patch(
                contract, enabled=True, oos_base_url=oos_url
            )
        )
        readiness_spec = readiness["spec"]["template"]["spec"]
        readiness_container = readiness_spec["containers"][0]
        readiness_env = {
            entry["name"]: entry for entry in readiness_container["env"]
        }
        self.assertEqual(
            oos_url, readiness_env["WGCF_PROTOTYPE_CLOSURE_OOS_URL"]["value"]
        )
        self.assertEqual(
            "/var/run/wgcf/prototype-closure-oos/caller-secret",
            readiness_env["WGCF_PROTOTYPE_CLOSURE_OOS_CREDENTIAL_FILE"]["value"],
        )
        self.assertTrue(readiness_container["volumeMounts"][0]["readOnly"])
        self.assertEqual(
            contract.readiness_oos_secret_name,
            readiness_spec["volumes"][0]["secret"]["secretName"],
        )

        suspended = json.loads(module.deployment_suspend_patch(contract))
        self.assertEqual(
            "false",
            suspended["spec"]["template"]["spec"]["containers"][0]["env"][0][
                "value"
            ],
        )
        revoked = json.loads(module.deployment_revoke_patch(contract))
        revoked_env = {
            entry["name"]
            for entry in revoked["spec"]["template"]["spec"]["containers"][0]["env"]
        }
        self.assertIn("OOS_PROTOTYPE_CLOSURE_PLATFORM_EVIDENCE_FILE", revoked_env)
        readiness_revoked = json.loads(
            module.workflow.readiness_runtime_patch(contract, enabled=None)
        )
        revoked_readiness_env = {
            entry["name"]
            for entry in readiness_revoked["spec"]["template"]["spec"]["containers"][0][
                "env"
            ]
        }
        self.assertIn("WGCF_PROTOTYPE_CLOSURE_OOS_URL", revoked_readiness_env)

    def test_runtime_inputs_initialize_bounded_platform_evidence(self) -> None:
        contract = module.load_contract(module.DEFAULT_CONTRACT)
        workspace = self.root / "workspace"
        authority = workspace / "workspace-prototype-studio"
        (authority / ".git").mkdir(parents=True)
        session = workspace / ".dev-integration/session/current-session.yaml"
        session.parent.mkdir(parents=True)
        session.write_text("session")
        wgcf_secret = self.root / "wgcf.secret"
        reader_secret = self.root / "reader.secret"
        for path, value in (
            (wgcf_secret, "wgcf-secret"),
            (reader_secret, "reader-secret"),
        ):
            path.write_text(value)
            path.chmod(0o600)
        args = argparse.Namespace(
            workspace_root=workspace,
            session_manifest=session,
            wgcf_base_url="http://127.0.0.1:8080",
            wgcf_caller_secret_file=wgcf_secret,
            oos_reader_secret_file=reader_secret,
            sandbox=True,
        )
        with mock.patch.object(
            module.workflow, "_git", return_value="a" * 40
        ):
            runtime = module.workflow._runtime_inputs(args, contract)
        evidence = runtime.state_root / "platform-evidence.json"
        self.assertEqual(
            {"schema_version": 1, "records": []},
            json.loads(evidence.read_text()),
        )
        self.assertEqual(0, stat.S_IMODE(evidence.stat().st_mode) & 0o077)
        self.assertEqual("reader-secret", runtime.oos_reader_secret)


if __name__ == "__main__":
    unittest.main()
