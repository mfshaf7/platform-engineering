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


MODULE_PATH = Path(__file__).with_name("repository_provider_identity.py")
SPEC = importlib.util.spec_from_file_location("repository_provider_identity", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


class ProviderState:
    app_id = 1234
    installation_id = 5678

    def __init__(self) -> None:
        self.mode = "ok"
        self.revocations = 0
        self.requested_repositories: list[str] = []
        self.token = "ghs_test_secret_must_not_escape"


class ProviderHandler(BaseHTTPRequestHandler):
    server: "ProviderServer"

    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def _json(self, status: int, payload: dict | None = None, headers: dict | None = None) -> None:
        self.send_response(status)
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        if payload is None:
            self.end_headers()
            return
        encoded = json.dumps(payload).encode("utf-8")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        state = self.server.state
        if state.mode == "unavailable":
            self._json(503, {"message": "unavailable"})
            return
        if self.path == f"/app/installations/{state.installation_id}":
            permissions = {"metadata": "read"}
            if state.mode == "overprivileged":
                permissions["contents"] = "read"
            self._json(
                200,
                {
                    "id": state.installation_id + (1 if state.mode == "mismatched" else 0),
                    "app_id": state.app_id,
                    "repository_selection": "selected",
                    "permissions": permissions,
                    "events": ["push"] if state.mode == "event-subscribed" else [],
                    "suspended_at": "2026-08-29T00:00:00Z" if state.mode == "suspended" else None,
                },
            )
            return
        if self.path == "/installation/repositories?per_page=100":
            repositories = [
                {"id": index + 100, "full_name": f"mfshaf7/{name}"}
                for index, name in enumerate(state.requested_repositories)
            ]
            if state.mode == "repository-mismatch":
                repositories = [{"id": 999, "full_name": "mfshaf7/not-requested"}]
            self._json(200, {"total_count": len(repositories), "repositories": repositories})
            return
        self._json(404, {"message": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        state = self.server.state
        if state.mode == "redirect":
            self._json(302, headers={"Location": "http://example.invalid/token"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        state.requested_repositories = list(payload.get("repositories") or [])
        expiry = datetime.now(timezone.utc) + timedelta(minutes=45)
        if state.mode == "expired":
            expiry = datetime.now(timezone.utc) - timedelta(minutes=1)
        self._json(
            201,
            {
                "token": state.token,
                "expires_at": expiry.isoformat().replace("+00:00", "Z"),
                "permissions": payload.get("permissions"),
                "repositories": [
                    {"id": index + 100, "full_name": f"mfshaf7/{name}"}
                    for index, name in enumerate(state.requested_repositories)
                ],
            },
        )

    def do_DELETE(self) -> None:  # noqa: N802
        if self.path == "/installation/token":
            if self.server.state.mode == "revoke-unavailable":
                self._json(503, {"message": "unavailable"})
                return
            self.server.state.revocations += 1
            self._json(204)
            return
        self._json(404, {"message": "not found"})


class ProviderServer(ThreadingHTTPServer):
    def __init__(self, address, handler, state: ProviderState):
        super().__init__(address, handler)
        self.state = state


class RepositoryProviderIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="repository-provider-identity-")
        cls.root = Path(cls.temp.name)
        cls.private_key = cls.root / "app.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(cls.private_key)],
            check=True,
            capture_output=True,
        )
        os.chmod(cls.private_key, 0o600)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def setUp(self) -> None:
        self.state = ProviderState()
        self.server = ProviderServer(("127.0.0.1", 0), ProviderHandler, self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.api_base_url = f"http://127.0.0.1:{self.server.server_port}"
        self.work = Path(tempfile.mkdtemp(prefix="repository-provider-test-", dir=self.root))
        self.workspace = self.work / "workspace"
        self.session_manifest = self.create_dev_integration_target()
        self.saved_target_environment = {
            name: os.environ.get(name)
            for name in ("KUBECTL_CONFIG_JSON", "KUBECTL_NAMESPACE_JSON")
        }
        os.environ["KUBECTL_CONFIG_JSON"] = json.dumps(
            {
                "clusters": [
                    {
                        "name": "default",
                        "cluster": {"server": "https://127.0.0.1:6443"},
                    }
                ]
            }
        )
        os.environ["KUBECTL_NAMESPACE_JSON"] = json.dumps(
            {
                "metadata": {"name": "devint-accepted-idea-delivery-test-operator"},
                "status": {"phase": "Active"},
            }
        )

    def tearDown(self) -> None:
        for name, value in self.saved_target_environment.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def identity_args(self, command: str, *, receipt: Path | None = None) -> list[str]:
        return [
            command,
            "--app-id",
            str(self.state.app_id),
            "--installation-id",
            str(self.state.installation_id),
            "--repository",
            "mfshaf7/governance-operations-console",
            "--private-key-file",
            str(self.private_key),
            "--provider-api-base-url",
            self.api_base_url,
            "--sandbox",
            "--receipt",
            str(receipt or self.work / "receipt.json"),
        ]

    def target_args(self) -> list[str]:
        return [
            "--session-manifest",
            str(self.session_manifest),
            "--workspace-root",
            str(self.workspace),
        ]

    def create_dev_integration_target(self) -> Path:
        registry_path = (
            self.workspace
            / "workspace-governance/contracts/developer-integration-profiles.yaml"
        )
        registry_path.parent.mkdir(parents=True)
        registry_path.write_text(
            "schema_version: 1\n"
            "profiles:\n"
            "  accepted-idea-delivery:\n"
            "    lifecycle: active\n"
            "    owner_repo: operator-orchestration-service\n"
            "    runtime_owner: platform-engineering\n"
            "    profile_path: dev-integration/profiles/accepted-idea-delivery/profile.yaml\n",
            encoding="utf-8",
        )
        profile_path = (
            self.workspace
            / "operator-orchestration-service/dev-integration/profiles/accepted-idea-delivery/profile.yaml"
        )
        profile_path.parent.mkdir(parents=True)
        profile_path.write_text(
            "schema_version: 1\n"
            "profile_id: accepted-idea-delivery\n"
            "runtime:\n"
            "  namespace_pattern: devint-{profile}-{operator}\n",
            encoding="utf-8",
        )
        manifest_path = (
            self.workspace
            / ".dev-integration/accepted-idea-delivery/test-operator/current-session.yaml"
        )
        manifest_path.parent.mkdir(parents=True)
        manifest_path.write_text(
            "schema_version: 1\n"
            "lane: dev-integration\n"
            "profile_id: accepted-idea-delivery\n"
            "profile_lifecycle: active\n"
            "owner_repo: operator-orchestration-service\n"
            "runtime_owner: platform-engineering\n"
            "action: up\n"
            "operator: test-operator\n"
            "namespace: devint-accepted-idea-delivery-test-operator\n"
            "session_id: accepted-idea-delivery-test-operator-20260829T000000Z\n",
            encoding="utf-8",
        )
        os.chmod(manifest_path, 0o600)
        return manifest_path

    def test_contract_is_valid(self) -> None:
        contract = module.load_contract(module.DEFAULT_CONTRACT)
        self.assertEqual({"metadata": "read"}, contract.required_permissions)
        self.assertEqual("https://api.github.com", contract.api_base_url)
        self.assertEqual(("accepted-idea-delivery",), contract.allowed_dev_integration_profiles)

    def test_contract_rejects_normal_runtime_activation(self) -> None:
        import yaml

        payload = yaml.safe_load(module.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
        payload["activation"]["normal_runtime_enabled"] = True
        path = self.work / "activated.yaml"
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")
        with self.assertRaisesRegex(module.IdentityError, "normal runtime activation"):
            module.load_contract(path)

    def test_commission_records_redacted_evidence_and_revokes_proof_token(self) -> None:
        receipt_path = self.work / "commission.json"
        self.assertEqual(0, module.main(self.identity_args("commission", receipt=receipt_path)))
        payload = json.loads(receipt_path.read_text(encoding="utf-8"))
        self.assertEqual("verified-and-proof-token-revoked", payload["outcome"])
        self.assertRegex(payload["contract_digest"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(["mfshaf7/governance-operations-console"], payload["repositories"])
        self.assertEqual(
            [
                {
                    "full_name": "mfshaf7/governance-operations-console",
                    "provider_repository_id": 100,
                }
            ],
            payload["provider_repositories"],
        )
        self.assertFalse(payload["secret_values_embedded"])
        self.assertNotIn(self.state.token, receipt_path.read_text(encoding="utf-8"))
        self.assertEqual(1, self.state.revocations)

    def test_commission_does_not_write_success_when_proof_token_revocation_fails(self) -> None:
        self.state.mode = "revoke-unavailable"
        receipt_path = self.work / "commission.json"
        self.assertEqual(1, module.main(self.identity_args("commission", receipt=receipt_path)))
        self.assertFalse(receipt_path.exists())

    def test_overprivileged_installation_fails_before_token_issue(self) -> None:
        self.state.mode = "overprivileged"
        self.assertEqual(1, module.main(self.identity_args("commission")))
        self.assertEqual([], self.state.requested_repositories)

    def test_event_subscribed_installation_fails_before_token_issue(self) -> None:
        self.state.mode = "event-subscribed"
        self.assertEqual(1, module.main(self.identity_args("commission")))
        self.assertEqual([], self.state.requested_repositories)

    def test_mismatched_installation_fails(self) -> None:
        self.state.mode = "mismatched"
        self.assertEqual(1, module.main(self.identity_args("commission")))

    def test_expired_token_fails_and_is_revoked(self) -> None:
        self.state.mode = "expired"
        self.assertEqual(1, module.main(self.identity_args("commission")))
        self.assertEqual(1, self.state.revocations)

    def test_repository_scope_mismatch_fails_and_is_revoked(self) -> None:
        self.state.mode = "repository-mismatch"
        self.assertEqual(1, module.main(self.identity_args("commission")))
        self.assertEqual(1, self.state.revocations)

    def test_provider_unavailability_fails_closed(self) -> None:
        self.state.mode = "unavailable"
        self.assertEqual(1, module.main(self.identity_args("commission")))

    def test_provider_redirect_is_denied(self) -> None:
        self.state.mode = "redirect"
        self.assertEqual(1, module.main(self.identity_args("commission")))

    def make_kubectl(self) -> tuple[Path, Path]:
        capture = self.work / "kubectl-input.yaml"
        script = self.work / "kubectl"
        script.write_text(
            "#!/bin/sh\n"
            "if [ \"$1\" = config ]; then printf '%s' \"$KUBECTL_CONFIG_JSON\"; exit 0; fi\n"
            "if [ \"$1\" = get ] && [ \"$2\" = namespace ]; then printf '%s' \"$KUBECTL_NAMESPACE_JSON\"; exit 0; fi\n"
            "if [ \"$1\" = apply ]; then cat >\"$KUBECTL_CAPTURE\"; exit 0; fi\n"
            "if [ \"$3\" = get ]; then printf '%s' \"$KUBECTL_SECRET_JSON\"; exit 0; fi\n"
            "if [ \"$3\" = delete ]; then exit 0; fi\n"
            "exit 2\n",
            encoding="utf-8",
        )
        os.chmod(script, 0o700)
        return script, capture

    def test_delivery_projects_secret_without_printing_token(self) -> None:
        kubectl, capture = self.make_kubectl()
        old_capture = os.environ.get("KUBECTL_CAPTURE")
        os.environ["KUBECTL_CAPTURE"] = str(capture)
        try:
            args = [
                *self.identity_args("deliver"),
                *self.target_args(),
                "--kubectl",
                str(kubectl),
            ]
            self.assertEqual(0, module.main(args))
        finally:
            if old_capture is None:
                os.environ.pop("KUBECTL_CAPTURE", None)
            else:
                os.environ["KUBECTL_CAPTURE"] = old_capture
        manifest = yaml_safe_load(capture)
        self.assertEqual(
            "devint-accepted-idea-delivery-test-operator",
            manifest["metadata"]["namespace"],
        )
        self.assertEqual(self.state.token, manifest["stringData"]["OOS_REPOSITORY_PROVIDER_INSTALLATION_TOKEN"])
        self.assertEqual(
            '[{"full_name":"mfshaf7/governance-operations-console","provider_repository_id":100}]',
            manifest["metadata"]["annotations"]["workspace-governance/provider-repositories"],
        )
        receipt_text = (self.work / "receipt.json").read_text(encoding="utf-8")
        self.assertNotIn(self.state.token, receipt_text)
        self.assertEqual(0, self.state.revocations)

    def test_delivery_rejects_nonlocal_kubernetes_target_before_token_issue(self) -> None:
        kubectl, _ = self.make_kubectl()
        os.environ["KUBECTL_CONFIG_JSON"] = json.dumps(
            {
                "clusters": [
                    {
                        "name": "stage",
                        "cluster": {"server": "https://stage.example.invalid:6443"},
                    }
                ]
            }
        )
        args = [
            *self.identity_args("deliver"),
            *self.target_args(),
            "--kubectl",
            str(kubectl),
        ]
        self.assertEqual(1, module.main(args))
        self.assertEqual([], self.state.requested_repositories)

    def test_normal_delivery_rejects_noncanonical_kubectl_command(self) -> None:
        with self.assertRaisesRegex(module.IdentityError, "platform-owned k3s kubectl"):
            module.verify_kubectl_command(str(self.work / "kubectl"), sandbox=False)
        module.verify_kubectl_command("k3s kubectl", sandbox=False)

    def test_revoke_removes_projection_and_accepts_already_revoked_token(self) -> None:
        kubectl, _ = self.make_kubectl()
        old_secret = os.environ.get("KUBECTL_SECRET_JSON")
        os.environ["KUBECTL_SECRET_JSON"] = json.dumps(self.projected_secret())
        try:
            args = [
                "revoke",
                "--app-id",
                str(self.state.app_id),
                "--installation-id",
                str(self.state.installation_id),
                "--repository",
                "mfshaf7/governance-operations-console",
                "--provider-api-base-url",
                self.api_base_url,
                "--sandbox",
                "--receipt",
                str(self.work / "revoke.json"),
                *self.target_args(),
                "--kubectl",
                str(kubectl),
            ]
            self.assertEqual(0, module.main(args))
        finally:
            if old_secret is None:
                os.environ.pop("KUBECTL_SECRET_JSON", None)
            else:
                os.environ["KUBECTL_SECRET_JSON"] = old_secret
        self.assertEqual(1, self.state.revocations)
        payload = json.loads((self.work / "revoke.json").read_text())
        self.assertEqual("revoked", payload["outcome"])
        self.assertEqual(100, payload["provider_repositories"][0]["provider_repository_id"])

    def test_revoke_rejects_tampered_credential_binding(self) -> None:
        kubectl, _ = self.make_kubectl()
        projected_secret = self.projected_secret()
        projected_secret["metadata"]["annotations"][
            "workspace-governance/credential-binding-digest"
        ] = "sha256:" + ("0" * 64)
        old_secret = os.environ.get("KUBECTL_SECRET_JSON")
        os.environ["KUBECTL_SECRET_JSON"] = json.dumps(projected_secret)
        try:
            args = [
                "revoke",
                "--app-id",
                str(self.state.app_id),
                "--installation-id",
                str(self.state.installation_id),
                "--repository",
                "mfshaf7/governance-operations-console",
                "--provider-api-base-url",
                self.api_base_url,
                "--sandbox",
                "--receipt",
                str(self.work / "revoke.json"),
                *self.target_args(),
                "--kubectl",
                str(kubectl),
            ]
            self.assertEqual(1, module.main(args))
        finally:
            if old_secret is None:
                os.environ.pop("KUBECTL_SECRET_JSON", None)
            else:
                os.environ["KUBECTL_SECRET_JSON"] = old_secret
        self.assertEqual(0, self.state.revocations)
        self.assertFalse((self.work / "revoke.json").exists())

    def projected_secret(self) -> dict:
        contract = module.load_contract(module.DEFAULT_CONTRACT)
        repositories = (
            module.ProviderRepository("mfshaf7/governance-operations-console", 100),
        )
        token = module.IssuedToken(
            token=self.state.token,
            expires_at="2026-08-29T23:59:59Z",
            repositories=(),
            permissions={"metadata": "read"},
        )
        manifest = module.secret_manifest(
            contract,
            token,
            repositories,
            module.binding_digest(
                contract,
                self.state.app_id,
                self.state.installation_id,
                repositories,
            ),
            self.dev_integration_target(),
        )
        secret = yaml_safe_load_text(manifest)
        secret["data"] = {
            contract.runtime_secret_key: base64.b64encode(self.state.token.encode()).decode()
        }
        secret.pop("stringData")
        return secret

    def dev_integration_target(self):
        return module.DevIntegrationTarget(
            profile_id="accepted-idea-delivery",
            session_id="accepted-idea-delivery-test-operator-20260829T000000Z",
            namespace="devint-accepted-idea-delivery-test-operator",
            cluster_server="https://127.0.0.1:6443",
        )

    def test_private_key_permissions_fail_closed(self) -> None:
        insecure = self.work / "insecure.pem"
        insecure.write_bytes(self.private_key.read_bytes())
        os.chmod(insecure, 0o644)
        args = self.identity_args("commission")
        index = args.index(str(self.private_key))
        args[index] = str(insecure)
        self.assertEqual(1, module.main(args))


def yaml_safe_load(path: Path) -> dict:
    import yaml

    return yaml.safe_load(path.read_text(encoding="utf-8"))


def yaml_safe_load_text(value: str) -> dict:
    import yaml

    return yaml.safe_load(value)


if __name__ == "__main__":
    unittest.main()
