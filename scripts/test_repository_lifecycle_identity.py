#!/usr/bin/env python3

from __future__ import annotations

import base64
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


MODULE_PATH = Path(__file__).with_name("repository_lifecycle_identity.py")
SPEC = importlib.util.spec_from_file_location("repository_lifecycle_identity", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.path.insert(0, str(MODULE_PATH.parent))
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class ProviderState:
    app_id = 1234
    installation_id = 5678
    organization = "example-organization"
    repository = "example-organization/lifecycle-target"
    repository_id = 9012

    def __init__(self) -> None:
        self.mode = "ok"
        self.revocations = 0
        self.token = "ghs_lifecycle_secret_must_not_escape"
        self.token_request: dict = {}


class ProviderHandler(BaseHTTPRequestHandler):
    server: "ProviderServer"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def respond(self, status: int, payload: dict | None = None, headers: dict | None = None) -> None:
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
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
        if self.path == "/app":
            self.respond(
                200,
                {
                    "id": state.app_id,
                    "owner": {
                        "login": "personal-owner" if state.mode == "wrong-app-owner" else state.organization,
                        "type": "User" if state.mode == "wrong-app-owner" else "Organization",
                    },
                },
            )
            return
        if self.path == f"/app/installations/{state.installation_id}":
            permissions = {"administration": "write", "metadata": "read"}
            if state.mode == "overprivileged":
                permissions["contents"] = "write"
            self.respond(
                200,
                {
                    "id": state.installation_id,
                    "app_id": state.app_id,
                    "account": {
                        "login": "another-organization" if state.mode == "wrong-org" else state.organization,
                        "type": "Organization",
                    },
                    "permissions": permissions,
                    "events": [],
                    "suspended_at": None,
                },
            )
            return
        if self.path == "/installation/repositories?per_page=100":
            repository_id = state.repository_id + 1 if state.mode == "wrong-repository-id" else state.repository_id
            repositories = [{"id": repository_id, "full_name": state.repository}]
            if state.mode == "extra-repository":
                repositories.append(
                    {"id": repository_id + 1, "full_name": f"{state.organization}/unexpected"}
                )
            self.respond(200, {"total_count": len(repositories), "repositories": repositories})
            return
        self.respond(404, {"message": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        state = self.server.state
        if state.mode == "redirect":
            self.respond(302, headers={"Location": "http://example.invalid/token"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        state.token_request = json.loads(self.rfile.read(length) or b"{}")
        expires = datetime.now(timezone.utc) + timedelta(minutes=45)
        self.respond(
            201,
            {
                "token": state.token,
                "expires_at": expires.isoformat().replace("+00:00", "Z"),
                "permissions": state.token_request.get("permissions"),
                "repositories": [
                    {"id": state.repository_id, "full_name": state.repository}
                ],
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


class RepositoryLifecycleIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="repository-lifecycle-identity-")
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
        self.work = Path(tempfile.mkdtemp(prefix="lifecycle-test-", dir=self.root))
        self.workspace = self.work / "workspace"
        self.session_manifest = self.create_dev_integration_target()
        self.kubectl, self.capture = self.create_kubectl()
        os.environ["KUBECTL_CAPTURE"] = str(self.capture)
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
            "KUBECTL_CONFIG_JSON",
            "KUBECTL_NAMESPACE_JSON",
            "KUBECTL_SECRET_JSON",
        ):
            os.environ.pop(name, None)
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def identity_args(self, command: str, *, repository_id: int | None = None) -> list[str]:
        return [
            command,
            "--app-id",
            str(self.state.app_id),
            "--installation-id",
            str(self.state.installation_id),
            "--organization",
            self.state.organization,
            "--repository",
            self.state.repository,
            "--repository-id",
            str(repository_id or self.state.repository_id),
            "--private-key-file",
            str(self.private_key),
            "--provider-api-base-url",
            self.api_base_url,
            "--sandbox",
            "--receipt",
            str(self.work / f"{command}.json"),
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
            "session_id: accepted-idea-delivery-test-operator-20260829T000000Z\n"
        )
        manifest.chmod(0o600)
        return manifest

    def create_kubectl(self) -> tuple[Path, Path]:
        capture = self.work / "secret.yaml"
        script = self.work / "kubectl"
        script.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = config ]; then printf '%s' \"$KUBECTL_CONFIG_JSON\"; exit 0; fi\n"
            "if [ \"$1\" = get ] && [ \"$2\" = namespace ]; then printf '%s' \"$KUBECTL_NAMESPACE_JSON\"; exit 0; fi\n"
            "if [ \"$1\" = apply ]; then cat >\"$KUBECTL_CAPTURE\"; exit 0; fi\n"
            "if [ \"$3\" = get ]; then printf '%s' \"$KUBECTL_SECRET_JSON\"; exit 0; fi\n"
            "if [ \"$3\" = delete ]; then exit 0; fi\nexit 2\n"
        )
        script.chmod(0o700)
        return script, capture

    def test_contract_is_exact_repository_scoped_and_runtime_disabled(self) -> None:
        contract = module.load_contract(module.DEFAULT_CONTRACT)
        self.assertEqual(
            {"administration": "write", "metadata": "read"},
            contract.required_permissions,
        )
        self.assertEqual(1, contract.maximum_repository_count)
        payload = yaml.safe_load(module.DEFAULT_CONTRACT.read_text())
        self.assertFalse(payload["activation"]["normal_runtime_enabled"])

    def test_commission_proves_repository_identity_without_secret_evidence(self) -> None:
        self.assertEqual(0, module.main(self.identity_args("commission")))
        receipt = (self.work / "commission.json").read_text()
        payload = json.loads(receipt)
        self.assertEqual(self.state.repository_id, payload["repository"]["provider_repository_id"])
        self.assertEqual(["lifecycle-target"], self.state.token_request["repositories"])
        self.assertNotIn(self.state.token, receipt)
        self.assertEqual(1, self.state.revocations)

    def test_identity_and_scope_mismatches_fail_closed(self) -> None:
        for mode in (
            "wrong-app-owner",
            "wrong-org",
            "overprivileged",
            "wrong-repository-id",
            "extra-repository",
            "redirect",
        ):
            with self.subTest(mode=mode):
                self.state.mode = mode
                self.assertEqual(1, module.main(self.identity_args("commission")))
                self.assertFalse((self.work / "commission.json").exists())

    def test_requested_immutable_repository_id_must_match(self) -> None:
        self.assertEqual(
            1,
            module.main(
                self.identity_args(
                    "commission", repository_id=self.state.repository_id + 20
                )
            ),
        )

    def test_delivery_and_revocation_keep_token_out_of_receipts(self) -> None:
        self.assertEqual(
            0,
            module.main([*self.identity_args("deliver"), *self.target_args()]),
        )
        manifest = yaml.safe_load(self.capture.read_text())
        self.assertEqual(
            self.state.token,
            manifest["stringData"]["OOS_REPOSITORY_LIFECYCLE_INSTALLATION_TOKEN"],
        )
        self.assertNotIn(self.state.token, (self.work / "deliver.json").read_text())
        secret = dict(manifest)
        secret["data"] = {
            "OOS_REPOSITORY_LIFECYCLE_INSTALLATION_TOKEN": base64.b64encode(
                self.state.token.encode()
            ).decode()
        }
        secret.pop("stringData")
        os.environ["KUBECTL_SECRET_JSON"] = json.dumps(secret)
        revoke_args = [
            "revoke",
            "--app-id",
            str(self.state.app_id),
            "--installation-id",
            str(self.state.installation_id),
            "--organization",
            self.state.organization,
            "--repository",
            self.state.repository,
            "--repository-id",
            str(self.state.repository_id),
            "--provider-api-base-url",
            self.api_base_url,
            "--sandbox",
            "--receipt",
            str(self.work / "revoke.json"),
            *self.target_args(),
        ]
        self.assertEqual(0, module.main(revoke_args))
        self.assertEqual(1, self.state.revocations)
        self.assertNotIn(self.state.token, (self.work / "revoke.json").read_text())


if __name__ == "__main__":
    unittest.main()
