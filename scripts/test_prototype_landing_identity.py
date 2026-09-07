#!/usr/bin/env python3
"""Contract and sandbox-runtime tests for the Prototype Landing identity."""

from __future__ import annotations

import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

import yaml


MODULE_PATH = Path(__file__).with_name("prototype_landing_identity.py")
SPEC = importlib.util.spec_from_file_location("prototype_landing_identity", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.path.insert(0, str(MODULE_PATH.parent))
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)

from test_workspace_intake_identity import (  # noqa: E402
    ProviderServer,
    ProviderState as ExactRepositoryProviderState,
)


class ProviderState(ExactRepositoryProviderState):
    repository = "mfshaf7/workspace-prototype-studio"
    repository_id = 1231020532

    def __init__(self) -> None:
        super().__init__()
        self.token = "ghs_prototype_landing_secret_must_not_escape"


class PrototypeLandingIdentityTests(unittest.TestCase):
    SOURCE_REVISION = "a" * 40
    WGCF_SECRET = "wgcf_prototype_landing_secret_must_not_escape"

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="prototype-landing-identity-")
        cls.root = Path(cls.temp.name)
        cls.private_key = cls.root / "app.pem"
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
                "-out",
                str(cls.private_key),
            ],
            check=True,
            capture_output=True,
        )
        cls.private_key.chmod(0o600)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def setUp(self) -> None:
        self.state = ProviderState()
        self.server = ProviderServer(("127.0.0.1", 0), self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.api_base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.work = Path(tempfile.mkdtemp(prefix="identity-test-", dir=self.root))
        self.workspace = self.work / "workspace"
        self.session_manifest = self.create_dev_integration_target()
        self.kubectl, self.capture, self.commands = self.create_kubectl()
        self.wgcf_secret_file = self.work / "wgcf.secret"
        self.wgcf_secret_file.write_text(self.WGCF_SECRET)
        self.wgcf_secret_file.chmod(0o600)
        self.runtime = module.RuntimeInputs(
            authority_root=self.workspace / "workspace-prototype-studio",
            state_root=self.session_manifest.parent / "prototype-landing/state",
            wgcf_base_url="http://127.0.0.1:8080",
            wgcf_caller_secret=self.WGCF_SECRET,
        )
        self.runtime.authority_root.mkdir(parents=True)
        self.runtime.state_root.mkdir(parents=True)
        os.environ["KUBECTL_CAPTURE"] = str(self.capture)
        os.environ["KUBECTL_COMMANDS"] = str(self.commands)
        os.environ["KUBECTL_CONFIG_JSON"] = json.dumps(
            {"clusters": [{"cluster": {"server": "https://127.0.0.1:6443"}}]}
        )
        os.environ["KUBECTL_NAMESPACE_JSON"] = json.dumps(
            {
                "metadata": {
                    "name": "devint-accepted-idea-delivery-test-operator"
                },
                "status": {"phase": "Active"},
            }
        )

    def tearDown(self) -> None:
        for name in (
            "KUBECTL_CAPTURE",
            "KUBECTL_COMMANDS",
            "KUBECTL_CONFIG_JSON",
            "KUBECTL_NAMESPACE_JSON",
            "KUBECTL_SECRET_JSON",
        ):
            os.environ.pop(name, None)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def identity_args(self, command: str) -> list[str]:
        return [
            command,
            "--app-id",
            str(self.state.app_id),
            "--installation-id",
            str(self.state.installation_id),
            "--private-key-file",
            str(self.private_key),
            "--provider-api-base-url",
            self.api_base_url,
            "--sandbox",
            "--receipt",
            str(self.work / f"{command}.json"),
            "--caller-id",
            "platform-engineering/test-operator",
            "--source-revision",
            f"platform-engineering={self.SOURCE_REVISION}",
        ]

    def target_args(self) -> list[str]:
        return [
            "--session-manifest",
            str(self.session_manifest),
            "--workspace-root",
            str(self.workspace),
            "--kubectl",
            str(self.kubectl),
        ]

    def create_dev_integration_target(self) -> Path:
        registry = (
            self.workspace
            / "workspace-governance/contracts/developer-integration-profiles.yaml"
        )
        registry.parent.mkdir(parents=True)
        registry.write_text(
            "schema_version: 1\nprofiles:\n  accepted-idea-delivery:\n"
            "    lifecycle: active\n    owner_repo: operator-orchestration-service\n"
            "    runtime_owner: platform-engineering\n"
            "    profile_path: dev-integration/profiles/accepted-idea-delivery/profile.yaml\n"
        )
        profile = (
            self.workspace
            / "operator-orchestration-service/dev-integration/profiles/accepted-idea-delivery/profile.yaml"
        )
        profile.parent.mkdir(parents=True)
        profile.write_text(
            "schema_version: 1\nprofile_id: accepted-idea-delivery\n"
            "runtime:\n  namespace_pattern: devint-{profile}-{operator}\n"
        )
        manifest = (
            self.workspace
            / ".dev-integration/accepted-idea-delivery/test-operator/current-session.yaml"
        )
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            "schema_version: 1\nlane: dev-integration\n"
            "profile_id: accepted-idea-delivery\nprofile_lifecycle: active\n"
            "owner_repo: operator-orchestration-service\n"
            "runtime_owner: platform-engineering\naction: up\n"
            "operator: test-operator\n"
            "namespace: devint-accepted-idea-delivery-test-operator\n"
            "session_id: accepted-idea-delivery-test-operator-20260907T000000Z\n"
        )
        manifest.chmod(0o600)
        return manifest

    def create_kubectl(self) -> tuple[Path, Path, Path]:
        capture = self.work / "secret.yaml"
        commands = self.work / "commands.txt"
        script = self.work / "kubectl"
        script.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$*\" >>\"$KUBECTL_COMMANDS\"\n"
            "if [ \"$1\" = config ]; then printf '%s' \"$KUBECTL_CONFIG_JSON\"; exit 0; fi\n"
            "if [ \"$1\" = get ] && [ \"$2\" = namespace ]; then printf '%s' \"$KUBECTL_NAMESPACE_JSON\"; exit 0; fi\n"
            "if [ \"$1\" = apply ]; then cat >\"$KUBECTL_CAPTURE\"; exit 0; fi\n"
            "if [ \"$3\" = get ]; then printf '%s' \"$KUBECTL_SECRET_JSON\"; exit 0; fi\n"
            "if [ \"$3\" = patch ] || [ \"$3\" = rollout ] || [ \"$3\" = delete ]; then exit 0; fi\n"
            "exit 2\n"
        )
        script.chmod(0o700)
        return script, capture, commands

    def test_selected_definition_and_stable_validation(self) -> None:
        original = module.DEFAULT_CONTRACT.read_bytes()
        result = module.validate_definition(module.DEFAULT_CONTRACT)
        self.assertEqual(result, module.validate_definition(module.DEFAULT_CONTRACT))
        self.assertEqual("selected-not-active", result["state"])
        self.assertFalse(result["identity_projection_enabled"])
        self.assertFalse(result["workflow_runtime_enabled"])
        self.assertFalse(result["provider_verified"])
        self.assertEqual(original, module.DEFAULT_CONTRACT.read_bytes())

    def test_definition_rejects_broader_authority_without_leaking_value(self) -> None:
        source = yaml.safe_load(module.DEFAULT_CONTRACT.read_text())
        changed = copy.deepcopy(source)
        changed["identity"]["required_permissions"]["administration"] = "write"
        path = self.work / "invalid.yaml"
        path.write_text(yaml.safe_dump(changed, sort_keys=False))
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--contract", str(path), "validate"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(1, result.returncode)
        self.assertNotIn("administration", result.stdout + result.stderr)

    def test_commission_proves_exact_installation_without_secret_evidence(self) -> None:
        self.assertEqual(0, module.main(self.identity_args("commission")))
        rendered = (self.work / "commission.json").read_text()
        receipt = json.loads(rendered)
        self.assertEqual(self.state.repository_id, receipt["repository_id"])
        self.assertEqual(
            {"platform-engineering": self.SOURCE_REVISION},
            receipt["source_revisions"],
        )
        self.assertFalse(receipt["workflow_runtime_enabled"])
        self.assertEqual(
            ["workspace-prototype-studio"], self.state.token_request["repositories"]
        )
        self.assertNotIn(self.state.token, rendered)
        self.assertEqual(1, self.state.revocations)

    def test_provider_scope_and_permission_mismatches_fail_closed(self) -> None:
        for mode in (
            "wrong-owner",
            "wrong-owner-id",
            "wrong-installation-owner",
            "all-repositories",
            "overprivileged",
            "events",
            "suspended",
            "wrong-repository-id",
            "extra-repository",
        ):
            with self.subTest(mode=mode):
                self.state.mode = mode
                self.assertEqual(1, module.main(self.identity_args("commission")))
                self.state.mode = "ok"

    def test_deployment_projection_is_bounded_and_fail_closed(self) -> None:
        contract = module.load_contract(module.DEFAULT_CONTRACT)
        patch = json.loads(module.deployment_patch(contract, self.runtime))
        container = patch["spec"]["template"]["spec"]["containers"][0]
        env = {item["name"]: item for item in container["env"]}
        self.assertEqual("false", env["OOS_PROTOTYPE_LANDING_ENABLED"]["value"])
        self.assertEqual(
            "/var/lib/oos/prototype-landing/authority",
            env["OOS_PROTOTYPE_LANDING_AUTHORITY_ROOT"]["value"],
        )
        mounts = {item["name"]: item for item in container["volumeMounts"]}
        self.assertTrue(mounts["prototype-landing-authority"]["readOnly"])
        self.assertTrue(mounts["prototype-landing-identity"]["readOnly"])
        self.assertNotIn(self.WGCF_SECRET, json.dumps(patch))

        revoke_patch = json.loads(module.deployment_revoke_patch(contract))
        revoke_container = revoke_patch["spec"]["template"]["spec"]["containers"][0]
        revoke_mounts = {
            item["name"]: item for item in revoke_container["volumeMounts"]
        }
        self.assertEqual(
            contract.runtime_directory,
            revoke_mounts["prototype-landing-identity"]["mountPath"],
        )
        self.assertEqual(
            contract.state_mount_path,
            revoke_mounts["prototype-landing-state"]["mountPath"],
        )
        self.assertEqual(
            contract.authority_mount_path,
            revoke_mounts["prototype-landing-authority"]["mountPath"],
        )
        self.assertTrue(
            all(item["$patch"] == "delete" for item in revoke_mounts.values())
        )

    def test_delivery_and_revocation_bind_and_remove_projection(self) -> None:
        with mock.patch.object(module, "_runtime_inputs", return_value=self.runtime), mock.patch.object(
            module, "runtime_binding_digest", return_value="sha256:" + "c" * 64
        ):
            self.assertEqual(
                0,
                module.main(
                    [
                        *self.identity_args("deliver"),
                        *self.target_args(),
                        "--wgcf-base-url",
                        self.runtime.wgcf_base_url,
                        "--wgcf-caller-secret-file",
                        str(self.wgcf_secret_file),
                    ]
                ),
            )
        manifest = yaml.safe_load(self.capture.read_text())
        self.assertEqual(
            self.state.token, manifest["stringData"]["installation-token"]
        )
        self.assertEqual(
            self.WGCF_SECRET, manifest["stringData"]["wgcf-caller-secret"]
        )
        rendered = (self.work / "deliver.json").read_text()
        self.assertNotIn(self.state.token, rendered)
        self.assertNotIn(self.WGCF_SECRET, rendered)
        self.assertIn(
            "apply --server-side --field-manager=platform-prototype-landing -f -",
            self.commands.read_text(),
        )

        secret = dict(manifest)
        secret["data"] = {
            "installation-token": base64.b64encode(self.state.token.encode()).decode(),
            "wgcf-caller-secret": base64.b64encode(self.WGCF_SECRET.encode()).decode(),
        }
        secret.pop("stringData")
        os.environ["KUBECTL_SECRET_JSON"] = json.dumps(secret)
        revoke_args = [
            "revoke",
            "--app-id",
            str(self.state.app_id),
            "--installation-id",
            str(self.state.installation_id),
            "--provider-api-base-url",
            self.api_base_url,
            "--sandbox",
            "--receipt",
            str(self.work / "revoke.json"),
            "--caller-id",
            "platform-engineering/test-operator",
            "--source-revision",
            f"platform-engineering={self.SOURCE_REVISION}",
            "--rollback-receipt-ref",
            "sha256:" + "b" * 64,
            *self.target_args(),
        ]
        self.assertEqual(0, module.main(revoke_args))
        self.assertEqual(1, self.state.revocations)
        self.assertIn(
            "delete secret operator-orchestration-service-prototype-landing",
            self.commands.read_text(),
        )
        revoke_receipt = (self.work / "revoke.json").read_text()
        self.assertNotIn(self.state.token, revoke_receipt)
        self.assertNotIn(self.WGCF_SECRET, revoke_receipt)

    def test_delivery_failure_removes_deployment_projection_before_secret(self) -> None:
        with mock.patch.object(
            module, "_runtime_inputs", return_value=self.runtime
        ), mock.patch.object(
            module, "runtime_binding_digest", return_value="sha256:" + "c" * 64
        ), mock.patch.object(
            module, "write_receipt", side_effect=OSError("receipt unavailable")
        ):
            self.assertEqual(
                1,
                module.main(
                    [
                        *self.identity_args("deliver"),
                        *self.target_args(),
                        "--wgcf-base-url",
                        self.runtime.wgcf_base_url,
                        "--wgcf-caller-secret-file",
                        str(self.wgcf_secret_file),
                    ]
                ),
            )

        commands = self.commands.read_text().splitlines()
        patch_indexes = [
            index
            for index, command in enumerate(commands)
            if " patch deployment " in f" {command} "
        ]
        rollout_indexes = [
            index
            for index, command in enumerate(commands)
            if " rollout status " in f" {command} "
        ]
        delete_index = next(
            index
            for index, command in enumerate(commands)
            if "delete secret operator-orchestration-service-prototype-landing" in command
        )
        self.assertEqual(2, len(patch_indexes))
        self.assertEqual(2, len(rollout_indexes))
        self.assertLess(patch_indexes[-1], rollout_indexes[-1])
        self.assertLess(rollout_indexes[-1], delete_index)
        self.assertEqual(1, self.state.revocations)


if __name__ == "__main__":
    unittest.main()
