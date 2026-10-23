#!/usr/bin/env python3
"""Tests for the Platform-owned Agent source identity controller."""

from __future__ import annotations

import importlib.util
import argparse
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import stat
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
    "sample-owner": 123456789,
    "workspace-governance": 1212447211,
    "workspace-governance-control-fabric": 1225028095,
    "context-governance-gateway": 1229561793,
    "workspace-prototype-studio": 1231020532,
    "governance-operations-console": 1317781281,
    "platform-engineering": 1195328534,
    "security-architecture": 1199398992,
    "openclaw-runtime-distribution": 1211058298,
    "openclaw-host-bridge": 1194541500,
    "openclaw-telegram-enhanced": 1191638177,
    "operator-orchestration-service": 1213863054,
}


class CurrentWorkspaceInventoryTests(unittest.TestCase):
    """Real Git CLI-reader seam; no credential issuance or provider mutation."""
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "workspace-governance"
        self.root.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Synthetic governance author")
        self.git("config", "user.email", "test@example.invalid")
        self.git("remote", "add", "origin", "https://github.com/mfshaf7/workspace-governance.git")
        self.inventory = self.root / "contracts/repos.yaml"
        self.inventory.parent.mkdir()
        self.records = {"schema_version": 2, "repos": {"workspace-governance": {"posture": "active", "lifecycle": "active"}}, "retired_repos": {}}
        self.inventory.write_text(yaml.safe_dump(self.records))
        (self.inventory.parent / "intake-register.yaml").write_text("schema_version: 2\nrepos: {}\n")
        schemas = self.inventory.parent / "schemas"
        schemas.mkdir()
        for name in ("repos", "intake-register"):
            (schemas / f"{name}.schema.json").write_text('{"type":"object"}')
        self.git("add", ".")
        self.git("commit", "-m", "reviewed initial source fixture")
        self.base = self.git("rev-parse", "HEAD")
        definition = module.load_contract(module.DEFAULT_CONTRACT)
        self.contract = replace(definition, repository_inventory_ref={**definition.repository_inventory_ref, "revision": self.base})
        self.git("update-ref", "refs/remotes/origin/main", self.base)

    def git(self, *args):
        return subprocess.check_output(["git", "-c", "core.hooksPath=/dev/null", "-C", str(self.root), *args],
            text=True, stderr=subprocess.DEVNULL).strip()

    def promote(self):
        self.records["repos"]["sample-app"] = {"posture": "active", "lifecycle": "active",
            "provider_repository": {"provider": "github", "provider_repository_id": "900", "full_name": "sample-org/sample-app"},
            "record": {"id": "repo:sample-app", "version": 1, "lineage": {"source": "workspace-intake",
                "source_ref": "repo:sample-app", "source_digest": "sha256:" + "a" * 64, "intake_entry_version": 1}}}
        self.inventory.write_text(yaml.safe_dump(self.records))
        self.git("add", ".")
        self.git("commit", "-m", "native promoted owner fixture")
        head = self.git("rev-parse", "HEAD")
        self.git("update-ref", "refs/remotes/origin/main", head)
        return head

    def test_normal_cli_reuses_record_mode_after_native_promotion_without_definition_repin(self):
        head = self.promote()
        args = argparse.Namespace(contract=module.DEFAULT_CONTRACT, workspace_repo_inventory=self.inventory, sandbox=False)
        with mock.patch.object(module, "load_contract", return_value=self.contract), mock.patch.object(
            module, "observe_public_repository_main", return_value=head) as observe:
            operating = module.load_operating_contract(args)
        self.assertEqual(operating.repository_inventory_ref["revision"], head)
        self.assertEqual(operating.contract_digest, self.contract.contract_digest)
        self.assertEqual([repo.full_name for repo in operating.repositories], ["mfshaf7/workspace-governance"])
        with self.assertRaises(module.IdentityError): module.expected_repository(operating, "sample-org/sample-app")
        self.assertEqual(observe.call_count, 2)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_explicit_maintenance_admits_promoted_owner_but_commission_stays_legacy(self):
        head = self.promote()
        args = argparse.Namespace(contract=module.DEFAULT_CONTRACT, workspace_repo_inventory=self.inventory, sandbox=False)
        with mock.patch.object(module, "load_contract", return_value=self.contract), mock.patch.object(
            module, "observe_public_repository_main", return_value=head):
            maintenance = module.load_operating_contract(args, maintenance=True)
            commission = module.load_operating_contract(args)
        self.assertEqual(module.expected_repository(maintenance, "sample-org/sample-app").provider_repository_id, 900)
        with self.assertRaises(module.IdentityError): module.expected_repository(commission, "sample-org/sample-app")
        with self.assertRaises(module.IdentityError): module.select_installation(maintenance, "sample-org/sample-app")
        self.records["repos"]["sample-app"]["posture"] = "suspended"
        self.inventory.write_text(yaml.safe_dump(self.records)); self.git("add", "."); self.git("commit", "-m", "suspend fixture owner")
        head = self.git("rev-parse", "HEAD"); self.git("update-ref", "refs/remotes/origin/main", head)
        with mock.patch.object(module, "load_contract", return_value=self.contract), mock.patch.object(
            module, "observe_public_repository_main", return_value=head):
            with self.assertRaises(module.IdentityError):
                module.expected_repository(module.load_operating_contract(args, maintenance=True), "sample-org/sample-app")

    def test_dirty_unfetched_wrong_provider_and_midread_changed_source_are_denied(self):
        head = self.promote()
        with mock.patch.object(module, "observe_public_repository_main", return_value="f" * 40):
            with self.assertRaises(module.IdentityError): module.read_current_workspace_inventory(self.contract, self.inventory)
        with mock.patch.object(module, "observe_public_repository_main", side_effect=[head, "f" * 40]):
            with self.assertRaises(module.IdentityError): module.read_current_workspace_inventory(self.contract, self.inventory)
        self.git("update-ref", "refs/remotes/origin/main", self.base)
        with self.assertRaises(module.IdentityError): module.read_current_workspace_inventory(self.contract, self.inventory)
        self.git("update-ref", "refs/remotes/origin/main", head)
        dirty = self.root / "preserve.txt"
        dirty.write_text("unique operator work")
        with self.assertRaises(module.IdentityError): module.read_current_workspace_inventory(self.contract, self.inventory)
        self.assertEqual(dirty.read_text(), "unique operator work")
        dirty.unlink()
        self.git("remote", "set-url", "origin", "https://github.com/foreign/workspace-governance.git")
        with self.assertRaises(module.IdentityError): module.read_current_workspace_inventory(self.contract, self.inventory)


class ProviderState:
    def __init__(self) -> None:
        self.mode = "ok"
        self.app_id = 4907049
        self.installation_id = 160815600
        self.serial = 0
        self.revoked: list[str] = []
        self.issued: list[tuple[str, ...]] = []
        self.workflow_granted = False
        self.issued_permissions: list[dict[str, str]] = []
        self.account_login = "mfshaf7"
        self.account_id = 244414185
        self.account_type = "User"


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
            if state.workflow_granted:
                permissions["workflows"] = "write"
            self._json(
                200,
                {
                    "id": state.installation_id,
                    "app_id": state.app_id,
                    "repository_selection": "selected",
                    "permissions": permissions,
                    "events": [],
                    "suspended_at": None,
                    "account": {"login": self.server.state.account_login,
                                "id": self.server.state.account_id,
                                "type": self.server.state.account_type},
                },
            )
            return
        if self.path == "/installation/repositories?per_page=100":
            requested = self.server.requested
            if state.mode == "broad-token":
                requested = ["platform-engineering", "security-architecture"]
            repositories = [
                {"full_name": f"{state.account_login}/{name}", "id": REPOSITORY_IDS[name]}
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
        state.issued_permissions.append(payload.get("permissions"))
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
                    {"full_name": f"{state.account_login}/{name}", "id": REPOSITORY_IDS[name]}
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

    def deliver(self, receipt: str = "deliver.json", extra: tuple[str, ...] = ()) -> int:
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
                *extra,
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
        self.assertEqual(11, len(contract.repositories))
        self.assertEqual(
            {"metadata": "read", "contents": "write", "pull_requests": "write", "checks": "read"},
            contract.required_permissions,
        )

    def test_receipt_write_preserves_existing_parent_permissions(self) -> None:
        parent = self.work / "shared-receipts"
        parent.mkdir(mode=0o755)
        before = stat.S_IMODE(parent.stat().st_mode)
        receipt = parent / "receipt.json"

        module.write_json_atomic(receipt, {"outcome": "verified"})

        self.assertEqual(before, stat.S_IMODE(parent.stat().st_mode))
        self.assertEqual(0o600, stat.S_IMODE(receipt.stat().st_mode))
        self.assertEqual({"outcome": "verified"}, json.loads(receipt.read_text(encoding="utf-8")))

    def test_workspace_inventory_must_match_exact_active_owner_set(self) -> None:
        contract = module.load_contract(module.DEFAULT_CONTRACT)
        inventory = self.work / "repos.yaml"
        inventory.write_text(
            yaml.safe_dump(
                {
                    "schema_version": 2,
                    "repos": {
                        repository.full_name.split("/", 1)[1]: {
                            "lifecycle": "active",
                            "posture": "active",
                        }
                        for repository in contract.repositories
                    },
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        definition = yaml.safe_load(module.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
        definition["authority"]["repository_inventory"]["digest"] = (
            f"sha256:{module.hashlib.sha256(inventory.read_bytes()).hexdigest()}"
        )
        contract_path = self.work / "contract.yaml"
        contract_path.write_text(yaml.safe_dump(definition, sort_keys=False), encoding="utf-8")
        schema = json.loads(module.SCHEMA.read_text(encoding="utf-8"))
        schema["properties"]["authority"]["const"] = definition["authority"]
        schema_path = self.work / "schema.json"
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        with mock.patch.object(module, "SCHEMA", schema_path):
            resolved = module.load_contract(contract_path)
        module.verify_workspace_repository_inventory(resolved, inventory)

        payload = yaml.safe_load(inventory.read_text(encoding="utf-8"))
        payload["repos"]["unclassified-repo"] = {
            "lifecycle": "active",
            "posture": "active",
        }
        inventory.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
        with self.assertRaisesRegex(module.IdentityError, "digest does not match"):
            module.verify_workspace_repository_inventory(resolved, inventory)

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
        self.assertEqual(11, len(self.state.issued))
        self.assertTrue(all(len(item) == 1 for item in self.state.issued))
        self.assertEqual(11, len(self.state.revoked))
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

    def test_promoted_org_maintenance_selects_exact_installation_and_revokes_without_admission(self):
        contract = module.load_contract(module.DEFAULT_CONTRACT)
        account = next(a for a in contract.installation_accounts if a.login == "mfshaf7-workspace")
        repository = module.Repository("mfshaf7-workspace/sample-owner", REPOSITORY_IDS["sample-owner"])
        admitted = replace(contract, repositories=(*contract.repositories, repository))
        self.state.installation_id = account.installation_id
        self.state.account_login, self.state.account_id, self.state.account_type = account.login, account.account_id, account.account_type
        args = [*self.session("deliver", "org-deliver.json"), "--private-key-file", str(self.private_key),
            "--branch", "fix/profile-baseline", "--fetched-base", "a" * 40, "--human-reviewer-id", "mfshaf7"]
        args[args.index("--repository") + 1] = repository.full_name
        # Admission and Git-reader behavior is independently exercised above;
        # this loopback witness uses the actual issuer, provider and projection.
        with mock.patch.object(module, "load_operating_contract", return_value=admitted) as read:
            self.assertEqual(0, module.main(args))
            self.assertTrue(all(call.kwargs.get("maintenance") is True for call in read.call_args_list))
        path, credential = self.credential()
        self.assertEqual(account.installation_id, credential["installation_id"])
        self.assertEqual(repository.provider_repository_id, credential["repository_id"])
        self.assertEqual([("sample-owner",)], self.state.issued)
        self.assertEqual(contract.required_permissions, self.state.issued_permissions[0])
        revoke = self.session("revoke", "org-revoke.json")
        revoke[revoke.index("--repository") + 1] = repository.full_name
        with mock.patch.object(module, "load_operating_contract", side_effect=module.IdentityError("retired admission unavailable")):
            self.assertEqual(0, module.main(revoke))
        self.assertFalse(path.exists())
        self.assertIn(credential["token"], self.state.revoked)
        receipt = json.loads((self.work / "org-revoke.json").read_text())
        self.assertEqual(account.installation_id, receipt["installation_id"])
        self.assertEqual(repository.provider_repository_id, receipt["repository_id"])
        self.assertNotIn(credential["token"], json.dumps(receipt))

    def test_promoted_maintenance_rechecks_admission_before_minting(self):
        contract = module.load_contract(module.DEFAULT_CONTRACT)
        with mock.patch.object(module, "load_operating_contract", side_effect=[contract, module.IdentityError("admission changed")]):
            self.assertEqual(1, self.deliver())
        self.assertEqual([], self.state.issued)

    def test_absent_legacy_revocation_stays_available_without_current_inventory(self):
        with mock.patch.object(module, "load_operating_contract", side_effect=module.IdentityError("inventory offline")):
            self.assertEqual(0, module.main(self.session("revoke", "absent-legacy.json")))
        self.assertEqual("already-absent", json.loads((self.work / "absent-legacy.json").read_text())["outcome"])
        self.assertEqual([], self.state.issued)

    def test_app_workflow_grant_does_not_broaden_ordinary_token(self) -> None:
        self.state.workflow_granted = True
        self.assertEqual(0, self.deliver())
        self.assertNotIn("workflows", self.state.issued_permissions[-1])
        self.assertNotIn("purpose", self.credential()[1])

    def test_workflow_maintenance_requires_approval_and_installation_grant(self) -> None:
        purpose = ("--purpose", "workflow-maintenance")
        self.assertEqual(1, self.deliver(extra=purpose))
        approved = (*purpose, "--approval-ref", "operator:2026-10-19-gary-workflows")
        self.assertEqual(1, self.deliver(extra=approved))
        self.assertEqual([], self.state.issued)
        self.state.workflow_granted = True
        self.assertEqual(0, self.deliver(extra=approved))
        self.assertEqual("write", self.state.issued_permissions[-1]["workflows"])
        credential = self.credential()[1]
        self.assertEqual("workflow-maintenance", credential["purpose"])
        self.assertEqual("operator:2026-10-19-gary-workflows", credential["approval_ref"])
        receipt = json.loads((self.work / "deliver.json").read_text())
        self.assertEqual("write", receipt["permissions"]["workflows"])
        self.assertNotIn(credential["token"], json.dumps(receipt))
        issued = len(self.state.issued)
        self.assertEqual(1, self.deliver("ordinary.json"))
        self.assertEqual(issued, len(self.state.issued))
        changed = (*purpose, "--approval-ref", "operator:other-approval")
        self.assertEqual(1, self.deliver("changed.json", extra=changed))
        self.assertEqual(issued, len(self.state.issued))
        self.assertEqual(0, module.main(self.session("revoke", "revoke.json")))
        revoked = json.loads((self.work / "revoke.json").read_text())
        self.assertEqual(receipt["purpose"], revoked["purpose"])
        self.assertEqual(receipt["permissions"], revoked["permissions"])

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
