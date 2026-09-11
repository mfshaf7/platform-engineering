#!/usr/bin/env python3
"""Tests for the Platform-owned Agent source identity controller."""

from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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


SCRIPT = Path(__file__).with_name("agent_source_identity.py")
SPEC = importlib.util.spec_from_file_location("agent_source_identity", SCRIPT)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


REPOSITORY_IDS = {
    "platform-engineering": 1195328534,
    "security-architecture": 1199398992,
    "workspace-governance": 1212447211,
    "operator-orchestration-service": 1213863054,
    "workspace-prototype-studio": 1231020532,
}


class ProviderState:
    def __init__(self) -> None:
        self.mode = "ok"
        self.app_id = 4907049
        self.installation_id = 160815600
        self.serial = 0
        self.revoked: list[str] = []
        self.issued: list[tuple[str, ...]] = []


class ProviderHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:  # noqa: A002
        return

    def _json(self, status: int, payload: object | None = None) -> None:
        encoded = b"" if payload is None else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        state = self.server.state
        if self.path == "/app":
            self._json(
                200,
                {
                    "id": state.app_id + (1 if state.mode == "wrong-app" else 0),
                    "slug": "mfshaf7-agent-gary",
                    "owner": {"login": "mfshaf7", "id": 244414185, "type": "User"},
                },
            )
            return
        if self.path == f"/app/installations/{state.installation_id}":
            permissions = {
                "metadata": "read",
                "contents": "write",
                "pull_requests": "write",
                "checks": "read",
            }
            if state.mode == "overprivileged":
                permissions["administration"] = "write"
            self._json(
                200,
                {
                    "id": state.installation_id,
                    "app_id": state.app_id,
                    "repository_selection": "selected",
                    "permissions": permissions,
                    "events": [],
                    "suspended_at": None,
                    "account": {"login": "mfshaf7", "id": 244414185, "type": "User"},
                },
            )
            return
        if self.path == "/installation/repositories?per_page=100":
            requested = self.server.requested
            if state.mode == "broad-token":
                requested = ["platform-engineering", "security-architecture"]
            repositories = [
                {"full_name": f"mfshaf7/{name}", "id": REPOSITORY_IDS[name]}
                for name in requested
            ]
            self._json(200, {"total_count": len(repositories), "repositories": repositories})
            return
        self._json(404, {"message": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        state = self.server.state
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        requested = tuple(payload.get("repositories") or ())
        self.server.requested = list(requested)
        state.issued.append(requested)
        state.serial += 1
        expiry = datetime.now(timezone.utc) + timedelta(minutes=45)
        if state.mode == "expired":
            expiry = datetime.now(timezone.utc) - timedelta(minutes=1)
        self._json(
            201,
            {
                "token": f"agent-source-secret-{state.serial}",
                "expires_at": expiry.isoformat().replace("+00:00", "Z"),
                "permissions": payload.get("permissions"),
                "repositories": [
                    {"full_name": f"mfshaf7/{name}", "id": REPOSITORY_IDS[name]}
                    for name in requested
                ],
            },
        )

    def do_DELETE(self) -> None:  # noqa: N802
        if self.path != "/installation/token":
            self._json(404, {"message": "not found"})
            return
        token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        if self.server.state.mode == "revoke-failure":
            self._json(503, {"message": "unavailable"})
            return
        self.server.state.revoked.append(token)
        self._json(204)


class ProviderServer(ThreadingHTTPServer):
    def __init__(self, address, state: ProviderState):
        super().__init__(address, ProviderHandler)
        self.state = state
        self.requested: list[str] = []


class AgentSourceIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="agent-source-identity-")
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
        os.chmod(cls.private_key, 0o600)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="case-", dir=self.root))
        self.runtime = self.work / "runtime"
        self.state = ProviderState()
        self.server = ProviderServer(("127.0.0.1", 0), self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.api = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def common(self, command: str, receipt: str) -> list[str]:
        return [
            command,
            "--sandbox",
            "--provider-api-base-url",
            self.api,
            "--runtime-root",
            str(self.runtime),
            "--receipt",
            str(self.work / receipt),
        ]

    def session(self, command: str, receipt: str = "receipt.json") -> list[str]:
        return [
            *self.common(command, receipt),
            "--landing-unit-id",
            "delivery-892-agent-gary-platform-identity",
            "--repository",
            "mfshaf7/platform-engineering",
        ]

    def deliver(self, receipt: str = "deliver.json") -> int:
        return module.main(
            [
                *self.session("deliver", receipt),
                "--private-key-file",
                str(self.private_key),
                "--branch",
                "feature/1136-agent-gary-platform-identity",
                "--fetched-base",
                "a" * 40,
                "--human-reviewer-id",
                "mfshaf7",
            ]
        )

    def credential(self) -> tuple[Path, dict]:
        contract = module.load_contract(module.DEFAULT_CONTRACT)
        directory = module.session_directory(
            self.runtime,
            "delivery-892-agent-gary-platform-identity",
        )
        path = directory / contract.credential_filename
        return path, json.loads(path.read_text(encoding="utf-8"))

    def test_contract_is_exact_and_inactive(self) -> None:
        contract = module.load_contract(module.DEFAULT_CONTRACT)
        self.assertEqual("agent-gary", contract.logical_agent_id)
        self.assertEqual("mfshaf7-agent-gary[bot]", contract.provider_principal)
        self.assertEqual(5, len(contract.repositories))
        self.assertEqual(
            {"metadata": "read", "contents": "write", "pull_requests": "write", "checks": "read"},
            contract.required_permissions,
        )

    def test_contract_rejects_activation_or_scope_drift(self) -> None:
        definition = yaml.safe_load(module.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
        definition["activation"]["normal_runtime_enabled"] = True
        path = self.work / "bad.yaml"
        path.write_text(yaml.safe_dump(definition), encoding="utf-8")
        with self.assertRaisesRegex(module.IdentityError, "definition is invalid"):
            module.load_contract(path)

    def test_commission_proves_each_repository_with_single_repo_tokens(self) -> None:
        receipt = self.work / "commission.json"
        result = module.main(
            [
                *self.common("commission", "commission.json"),
                "--private-key-file",
                str(self.private_key),
            ]
        )
        self.assertEqual(0, result)
        self.assertEqual(5, len(self.state.issued))
        self.assertTrue(all(len(item) == 1 for item in self.state.issued))
        self.assertEqual(5, len(self.state.revoked))
        content = receipt.read_text(encoding="utf-8")
        self.assertNotIn("agent-source-secret", content)
        self.assertFalse(json.loads(content)["secret_values_embedded"])

    def test_wrong_app_overprivilege_and_broad_token_fail_closed(self) -> None:
        for mode in ("wrong-app", "overprivileged", "broad-token"):
            with self.subTest(mode=mode):
                self.state.mode = mode
                receipt = self.work / f"{mode}.json"
                args = [
                    *self.common("commission", f"{mode}.json"),
                    "--private-key-file",
                    str(self.private_key),
                ]
                self.assertEqual(1, module.main(args))
                self.assertFalse(receipt.exists())
                self.state.mode = "ok"

    def test_delivery_projects_one_atomic_ephemeral_credential(self) -> None:
        self.assertEqual(0, self.deliver())
        path, credential = self.credential()
        self.assertEqual(0o600, path.stat().st_mode & 0o777)
        self.assertEqual("mfshaf7/platform-engineering", credential["repository"])
        self.assertEqual("agent-source-secret-1", credential["token"])
        receipt = (self.work / "deliver.json").read_text(encoding="utf-8")
        self.assertNotIn(credential["token"], receipt)
        self.assertEqual("delivered", json.loads(receipt)["outcome"])

    def test_delivery_rejects_wrong_repository_branch_or_reviewer_before_issue(self) -> None:
        cases = (
            ("--repository", "mfshaf7/not-approved"),
            ("--branch", "main"),
            ("--human-reviewer-id", "agent-gary"),
        )
        base = [
            *self.session("deliver"),
            "--private-key-file",
            str(self.private_key),
            "--branch",
            "feature/1136-agent-gary-platform-identity",
            "--fetched-base",
            "a" * 40,
            "--human-reviewer-id",
            "mfshaf7",
        ]
        for flag, value in cases:
            with self.subTest(flag=flag):
                args = list(base)
                index = args.index(flag)
                args[index + 1] = value
                self.assertEqual(1, module.main(args))
        self.assertEqual([], self.state.issued)

    def test_rotation_revokes_old_token_and_publishes_new_token(self) -> None:
        self.assertEqual(0, self.deliver("first.json"))
        _, first = self.credential()
        self.assertEqual(0, self.deliver("second.json"))
        _, second = self.credential()
        self.assertNotEqual(first["token"], second["token"])
        self.assertIn(first["token"], self.state.revoked)
        self.assertEqual("rotated", json.loads((self.work / "second.json").read_text())["outcome"])

    def test_failed_old_token_revocation_keeps_existing_projection(self) -> None:
        self.assertEqual(0, self.deliver("first.json"))
        _, first = self.credential()
        self.state.mode = "revoke-failure"
        self.assertEqual(1, self.deliver("failed.json"))
        _, current = self.credential()
        self.assertEqual(first, current)
        self.assertFalse((self.work / "failed.json").exists())

    def test_failed_projection_write_revokes_new_token(self) -> None:
        with mock.patch.object(module, "write_json_atomic", side_effect=OSError("write failed")):
            self.assertEqual(1, self.deliver("failed.json"))
        self.assertEqual(["agent-source-secret-1"], self.state.revoked)
        path, _ = self.credential_path_without_read()
        self.assertFalse(path.exists())
        self.assertFalse((self.work / "failed.json").exists())

    def test_suspend_revokes_projection_and_blocks_new_delivery(self) -> None:
        self.assertEqual(0, self.deliver("first.json"))
        self.assertEqual(0, module.main(self.common("suspend", "suspend.json")))
        path, _ = self.credential_path_without_read()
        self.assertFalse(path.exists())
        self.assertEqual(1, self.deliver("blocked.json"))
        self.assertEqual(1, len(self.state.issued))

    def credential_path_without_read(self) -> tuple[Path, object]:
        contract = module.load_contract(module.DEFAULT_CONTRACT)
        directory = module.session_directory(
            self.runtime,
            "delivery-892-agent-gary-platform-identity",
        )
        return directory / contract.credential_filename, contract

    def test_revoke_is_idempotent_and_removes_projection(self) -> None:
        self.assertEqual(0, self.deliver())
        self.assertEqual(0, module.main(self.session("revoke", "revoke.json")))
        path, _ = self.credential_path_without_read()
        self.assertFalse(path.exists())
        self.assertEqual(0, module.main(self.session("revoke", "revoke-again.json")))
        self.assertEqual("already-absent", json.loads((self.work / "revoke-again.json").read_text())["outcome"])

    def test_bootstrap_key_is_imported_to_vault_and_retired(self) -> None:
        bootstrap = self.work / "bootstrap.pem"
        bootstrap.write_bytes(self.private_key.read_bytes())
        os.chmod(bootstrap, 0o600)
        store = self.work / "vault.pem"
        vault = self.work / "vault"
        vault.write_text(
            "#!/bin/sh\n"
            "if [ \"$2\" = put ]; then cp \"${5#privateKey=@}\" \"$VAULT_TEST_STORE\"; exit 0; fi\n"
            "if [ \"$2\" = get ]; then cat \"$VAULT_TEST_STORE\"; exit 0; fi\n"
            "exit 2\n",
            encoding="utf-8",
        )
        os.chmod(vault, 0o700)
        old = os.environ.get("VAULT_TEST_STORE")
        os.environ["VAULT_TEST_STORE"] = str(store)
        try:
            result = module.main(
                [
                    *self.common("commission", "vault-commission.json"),
                    "--vault-command",
                    str(vault),
                    "--bootstrap-private-key-file",
                    str(bootstrap),
                    "--retire-bootstrap-key",
                ]
            )
        finally:
            if old is None:
                os.environ.pop("VAULT_TEST_STORE", None)
            else:
                os.environ["VAULT_TEST_STORE"] = old
        self.assertEqual(0, result)
        self.assertFalse(bootstrap.exists())
        self.assertTrue(store.exists())

    def test_direct_private_key_is_rejected_outside_sandbox(self) -> None:
        args = [
            "commission",
            "--private-key-file",
            str(self.private_key),
            "--receipt",
            str(self.work / "normal.json"),
        ]
        self.assertEqual(1, module.main(args))


if __name__ == "__main__":
    unittest.main()
