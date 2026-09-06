#!/usr/bin/env python3
"""Contract and sandbox-runtime tests for the Workspace Intake identity."""

from __future__ import annotations

import base64
import copy
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

import yaml


MODULE_PATH = Path(__file__).with_name("workspace_intake_identity.py")
SPEC = importlib.util.spec_from_file_location("workspace_intake_identity", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.path.insert(0, str(MODULE_PATH.parent))
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class ProviderState:
    app_id = 1234
    installation_id = 5678
    repository = "mfshaf7/workspace-governance"
    repository_id = 1212447211
    owner_id = 244414185

    def __init__(self) -> None:
        self.mode = "ok"
        self.revocations = 0
        self.token = "ghs_workspace_intake_secret_must_not_escape"
        self.token_request: dict = {}


class ProviderHandler(BaseHTTPRequestHandler):
    server: "ProviderServer"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def respond(self, status: int, payload: dict | None = None) -> None:
        self.send_response(status)
        if payload is None:
            self.end_headers()
            return
        encoded = json.dumps(payload).encode()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        state = self.server.state
        permissions = {
            "metadata": "read",
            "contents": "write",
            "pull_requests": "write",
            "checks": "read",
        }
        if self.path == "/app":
            self.respond(
                200,
                {
                    "id": state.app_id,
                    "owner": {
                        "login": "wrong-owner" if state.mode == "wrong-owner" else "mfshaf7",
                        "id": state.owner_id + (1 if state.mode == "wrong-owner-id" else 0),
                        "type": "User",
                    },
                },
            )
            return
        if self.path == f"/app/installations/{state.installation_id}":
            observed_permissions = dict(permissions)
            if state.mode == "overprivileged":
                observed_permissions["administration"] = "write"
            self.respond(
                200,
                {
                    "id": state.installation_id,
                    "app_id": state.app_id,
                    "account": {
                        "login": "other" if state.mode == "wrong-installation-owner" else "mfshaf7",
                        "id": state.owner_id,
                        "type": "User",
                    },
                    "repository_selection": "all" if state.mode == "all-repositories" else "selected",
                    "permissions": observed_permissions,
                    "events": ["push"] if state.mode == "events" else [],
                    "suspended_at": "2026-09-05T00:00:00Z" if state.mode == "suspended" else None,
                },
            )
            return
        if self.path == "/installation/repositories?per_page=100":
            repository_id = state.repository_id + (1 if state.mode == "wrong-repository-id" else 0)
            repositories = [{"id": repository_id, "full_name": state.repository}]
            if state.mode == "extra-repository":
                repositories.append({"id": 99, "full_name": "mfshaf7/unrelated"})
            self.respond(200, {"total_count": len(repositories), "repositories": repositories})
            return
        self.respond(404, {"message": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        state = self.server.state
        length = int(self.headers.get("Content-Length", "0"))
        state.token_request = json.loads(self.rfile.read(length) or b"{}")
        expires = datetime.now(timezone.utc) + timedelta(minutes=45)
        self.respond(
            201,
            {
                "token": state.token,
                "expires_at": expires.isoformat().replace("+00:00", "Z"),
                "permissions": state.token_request["permissions"],
                "repositories": [{"id": state.repository_id, "full_name": state.repository}],
            },
        )

    def do_DELETE(self) -> None:  # noqa: N802
        if self.path == "/installation/token":
            self.server.state.revocations += 1
            self.respond(204)
            return
        self.respond(404, {"message": "not found"})


class ProviderServer(ThreadingHTTPServer):
    def __init__(self, address, state: ProviderState):
        super().__init__(address, ProviderHandler)
        self.state = state


class WorkspaceIntakeIdentityTests(unittest.TestCase):
    SOURCE_REVISION = "a" * 40

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="workspace-intake-identity-")
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
        os.environ["KUBECTL_CAPTURE"] = str(self.capture)
        os.environ["KUBECTL_COMMANDS"] = str(self.commands)
        os.environ["KUBECTL_CONFIG_JSON"] = json.dumps(
            {"clusters": [{"cluster": {"server": "https://127.0.0.1:6443"}}]}
        )
        os.environ["KUBECTL_NAMESPACE_JSON"] = json.dumps(
            {
                "metadata": {"name": "devint-accepted-idea-delivery-test-operator"},
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
        registry = self.workspace / "workspace-governance/contracts/developer-integration-profiles.yaml"
        registry.parent.mkdir(parents=True)
        registry.write_text(
            "schema_version: 1\nprofiles:\n  accepted-idea-delivery:\n"
            "    lifecycle: active\n    owner_repo: operator-orchestration-service\n"
            "    runtime_owner: platform-engineering\n"
            "    profile_path: dev-integration/profiles/accepted-idea-delivery/profile.yaml\n"
        )
        profile = self.workspace / "operator-orchestration-service/dev-integration/profiles/accepted-idea-delivery/profile.yaml"
        profile.parent.mkdir(parents=True)
        profile.write_text(
            "schema_version: 1\nprofile_id: accepted-idea-delivery\n"
            "runtime:\n  namespace_pattern: devint-{profile}-{operator}\n"
        )
        manifest = self.workspace / ".dev-integration/accepted-idea-delivery/test-operator/current-session.yaml"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(
            "schema_version: 1\nlane: dev-integration\nprofile_id: accepted-idea-delivery\n"
            "profile_lifecycle: active\nowner_repo: operator-orchestration-service\n"
            "runtime_owner: platform-engineering\naction: up\noperator: test-operator\n"
            "namespace: devint-accepted-idea-delivery-test-operator\n"
            "session_id: accepted-idea-delivery-test-operator-20260905T000000Z\n"
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
        self.assertFalse(result["runtime_enabled"])
        self.assertFalse(result["provider_verified"])
        self.assertEqual(original, module.DEFAULT_CONTRACT.read_bytes())

    def test_definition_denials_do_not_leak_rejected_values(self) -> None:
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
        self.assertEqual("platform-engineering/test-operator", receipt["caller_id"])
        self.assertIsNotNone(receipt["issued_at"])
        self.assertEqual(["workspace-governance"], self.state.token_request["repositories"])
        self.assertNotIn(self.state.token, rendered)
        self.assertEqual(1, self.state.revocations)

    def test_identity_scope_and_permission_mismatches_fail_closed(self) -> None:
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

    def test_delivery_and_revocation_bind_runtime_and_remove_projection(self) -> None:
        self.assertEqual(
            0,
            module.main([*self.identity_args("deliver"), *self.target_args()]),
        )
        manifest = yaml.safe_load(self.capture.read_text())
        self.assertEqual(
            self.state.token,
            manifest["stringData"]["installation-token"],
        )
        deliver_receipt = (self.work / "deliver.json").read_text()
        self.assertNotIn(self.state.token, deliver_receipt)
        self.assertIn(
            "apply --server-side --field-manager=platform-workspace-intake -f -",
            self.commands.read_text(),
        )
        self.assertIn("patch deployment operator-orchestration-service", self.commands.read_text())
        revoke_patch = json.loads(
            module.deployment_revoke_patch(module.load_contract(module.DEFAULT_CONTRACT))
        )
        mount = revoke_patch["spec"]["template"]["spec"]["containers"][0][
            "volumeMounts"
        ][0]
        self.assertEqual("/var/run/oos/workspace-intake", mount["mountPath"])
        secret = dict(manifest)
        secret["data"] = {
            "installation-token": base64.b64encode(self.state.token.encode()).decode()
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
        self.assertIn("delete secret operator-orchestration-service-workspace-intake", self.commands.read_text())
        self.assertNotIn(self.state.token, (self.work / "revoke.json").read_text())
        self.assertEqual(
            "sha256:" + "b" * 64,
            json.loads((self.work / "revoke.json").read_text())["rollback_receipt_ref"],
        )


if __name__ == "__main__":
    unittest.main()
