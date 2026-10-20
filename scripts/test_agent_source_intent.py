#!/usr/bin/env python3
"""Actual issuer/projection proof against the existing loopback GitHub fixture."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import importlib.util
from http.server import ThreadingHTTPServer
from pathlib import Path
import stat
import threading
import unittest
import yaml
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import patch

import agent_source_intent as intents
import test_agent_source_identity as fixture


CALLER = "oos-console-operations"
OPERATOR = "operator:workspace-owner"


def source_input(*, prototype: bool = False) -> dict:
    subject = {
        "kind": "delivery", "work_item_ref": "work-item-1298", "snapshot_digest": "sha256:" + "b" * 64,
    }
    if prototype:
        subject = {
            "kind": "prototype", "prototype_id": "prototype:sample", "registry_ref": "record://prototypes/sample",
            "registry_revision": "b" * 40, "source_ref": "repo://workspace-prototype-studio/prototypes/sample",
            "source_revision": "c" * 40,
        }
    return {"session_id": None, "source_intent": {
        "schema_version": 1, "purpose": "ordinary-source", "intent_id": "source-intent:sample:1",
        "caller_id": CALLER, "operator_id": OPERATOR, "subject": subject,
        "source_start_digest": "sha256:" + "a" * 64,
        "supersedes_intent_digest": None,
        "repository": "mfshaf7/platform-engineering", "repository_id": 1195328534,
        "installation_id": 160815600, "landing_unit_id": "sample-source-credential",
        "branch": "feature/sample-source-credential", "fetched_base": "a" * 40, "human_reviewer_id": "mfshaf7",
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
    }}


def admission_snapshot() -> intents.identity.RepositoryInventorySnapshot:
    """Small closed test schema, not an assertion of full Workspace validation."""
    binding = {"provider": "github", "provider_repository_id": "123456789",
               "full_name": "mfshaf7-workspace/sample-owner"}
    inventory = {"schema_version": 2, "repos": {"sample-owner": {
        "lifecycle": "active", "posture": "active", "provider_repository": binding,
        "record": {"id": "repo:sample-owner", "lineage": {
            "source": "workspace-intake", "source_ref": "repo:sample-owner", "intake_entry_version": 2,
            "source_digest": "sha256:" + "f" * 64,
        }},
    }}, "retired_repos": {}}
    intake = {"schema_version": 2, "repos": {}}
    schema = {"type": "object", "required": ["schema_version", "repos"], "properties": {
        "schema_version": {"const": 2}, "repos": {"type": "object"}, "retired_repos": {"type": "object"},
    }, "additionalProperties": False}
    return intents.identity.RepositoryInventorySnapshot(
        inventory=yaml.safe_dump(inventory).encode(), inventory_schema=schema,
        intake=yaml.safe_dump(intake).encode(), intake_schema=schema,
        revision="d" * 40, reviewed_revision="e" * 40,
    )


def proposed_snapshot() -> intents.identity.RepositoryInventorySnapshot:
    snapshot = admission_snapshot()
    inventory = yaml.safe_load(snapshot.inventory)
    binding = inventory["repos"].pop("sample-owner")["provider_repository"]
    intake = {"schema_version": 2, "repos": {"sample-owner": {
        "status": "proposed", "repo_class": "product-source", "requires_security_bindings": False,
        "security_owner": None, "provider_repository": binding,
        "validation_behavior": {"posture": "covered-by-owner-repo", "wgcf_graph_role": "product-runtime-source",
                                "catalog_refs": [], "notes": "Synthetic source-only project validation."},
        "notes": "Synthetic proposed source; no control-plane or runtime authority.",
        "record": {"id": "repo:sample-owner", "version": 1},
    }}}
    return intents.identity.replace(snapshot, inventory=yaml.safe_dump(inventory).encode(), intake=yaml.safe_dump(intake).encode())


class SourceIntentTests(unittest.TestCase):
    setUpClass = classmethod(fixture.AgentSourceIdentityTests.setUpClass.__func__)
    tearDownClass = classmethod(fixture.AgentSourceIdentityTests.tearDownClass.__func__)
    setUp = fixture.AgentSourceIdentityTests.setUp
    tearDown = fixture.AgentSourceIdentityTests.tearDown

    def args(self) -> argparse.Namespace:
        return argparse.Namespace(
            contract=intents.identity.DEFAULT_CONTRACT, sandbox=True, runtime_root=self.runtime,
            workspace_repo_inventory=None, provider_api_base_url=self.api,
            vault_command="vault", private_key_file=self.private_key,
        )

    def operate(self, action="issue", *, value=None, command="command:credential:1", inventory_reader=None) -> dict:
        if value is None:
            value = self.value
        return intents.operate(
            self.args(), state_root=self.work / "provider", action=f"agent-source.{action}",
            command_id=command, input_value=value, caller_id=CALLER, operator_id=OPERATOR,
            inventory_reader=inventory_reader,
        )

    def credential(self) -> tuple[Path, dict]:
        contract = intents.identity.load_contract(self.args().contract)
        path = intents.identity.session_directory(self.runtime, self.value["source_intent"]["landing_unit_id"]) / contract.credential_filename
        return path, json.loads(path.read_text())

    def test_delivery_before_session_uses_existing_exact_issuer_and_private_projection(self):
        self.value = source_input()
        result = self.operate()
        path, credential = self.credential()
        self.assertIsNone(result["session_id"])
        self.assertEqual(self.state.issued, [("platform-engineering",)])
        self.assertEqual(credential["repository_id"], result["repository_id"])
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        for record in (self.work / "provider").rglob("*.json"):
            text = record.read_text()
            self.assertNotIn(credential["token"], text)
            self.assertNotIn("PRIVATE KEY", text)
            self.assertEqual(stat.S_IMODE(record.stat().st_mode), 0o600)
        self.assertNotIn("token", result)
        self.assertFalse(any(self.work.rglob(".git")))

    def organization_source(self):
        self.value = source_input()
        self.value["source_intent"].update(repository="mfshaf7-workspace/sample-owner",
            repository_id=123456789, installation_id=172173010)
        self.state.installation_id = 172173010
        self.state.account_login = "mfshaf7-workspace"
        self.state.account_id = 322605984
        self.state.account_type = "Organization"
        self.state.workflow_granted = True

    def test_organization_installation_is_not_the_app_owner_and_token_stays_ordinary(self):
        self.organization_source()
        result = self.operate(inventory_reader=admission_snapshot)
        _, credential = self.credential()
        self.assertEqual(self.state.issued, [("sample-owner",)])
        self.assertEqual(result["installation_id"], 172173010)
        self.assertEqual(credential["repository"], "mfshaf7-workspace/sample-owner")
        self.assertNotIn("workflows", result["permissions"])
        self.assertNotIn("workflows", self.state.issued_permissions[-1])
        self.assertNotIn("purpose", credential)

    def test_selected_organization_repository_without_canonical_admission_cannot_issue(self):
        self.organization_source()
        with self.assertRaises(intents.identity.IdentityError):
            self.operate()
        self.assertEqual(self.state.issued, [])

    def test_intake_and_active_inventory_cannot_coexist_after_atomic_promotion(self):
        self.organization_source()
        for status in ("proposed", "out-of-scope", "admitted"):
            with self.subTest(status=status):
                snapshot = admission_snapshot()
                intake = yaml.safe_load(snapshot.intake)
                intake["repos"]["sample-owner"] = {"status": status,
                    "provider_repository": yaml.safe_load(snapshot.inventory)["repos"]["sample-owner"]["provider_repository"]}
                snapshot = intents.identity.replace(snapshot, intake=yaml.safe_dump(intake).encode())
                with self.assertRaises(intents.identity.IdentityError):
                    self.operate(inventory_reader=lambda: snapshot)
                self.assertEqual(self.state.issued, [])

    def test_canonical_provider_binding_lineage_and_lifecycle_must_match(self):
        self.organization_source()
        for mode in ("suspended", "retired", "provider-id", "lineage", "missing-source-digest", "duplicate-retired", "schema"):
            with self.subTest(mode=mode):
                snapshot = admission_snapshot()
                inventory = yaml.safe_load(snapshot.inventory)
                item = inventory["repos"]["sample-owner"]
                if mode in {"suspended", "retired"}:
                    item["posture"] = mode
                elif mode == "provider-id":
                    item["provider_repository"]["provider_repository_id"] = "987654321"
                elif mode == "lineage":
                    item["record"]["lineage"]["source_ref"] = "repo:other"
                elif mode == "missing-source-digest":
                    item["record"]["lineage"].pop("source_digest")
                elif mode == "duplicate-retired":
                    inventory["retired_repos"]["another-key"] = deepcopy(item)
                else:
                    inventory["schema_version"] = 3
                snapshot = intents.identity.replace(snapshot, inventory=yaml.safe_dump(inventory).encode())
                with self.assertRaises(intents.identity.IdentityError):
                    self.operate(inventory_reader=lambda: snapshot)
                self.assertEqual(self.state.issued, [])

    def test_wrong_installation_account_or_numeric_provider_id_is_denied(self):
        self.organization_source()
        self.state.account_id += 1
        with self.assertRaisesRegex(intents.identity.IdentityError, "installation account"):
            self.operate(inventory_reader=admission_snapshot)
        self.assertEqual(self.state.issued, [])
        self.state.account_id -= 1
        self.value["source_intent"]["repository_id"] += 1
        with self.assertRaisesRegex(intents.identity.IdentityError, "exact Platform provider"):
            self.operate(inventory_reader=admission_snapshot)
        self.assertEqual(self.state.issued, [])

    def test_new_owner_revoke_survives_inventory_loss_and_retirement_without_minting(self):
        self.organization_source()
        self.operate(inventory_reader=admission_snapshot)
        def unavailable():
            raise AssertionError("revocation must not require current inventory or freshness")
        result = self.operate("revoke", command="command:credential:revoke", inventory_reader=unavailable)
        self.assertEqual(result["outcome"], "revoked")
        self.assertEqual(len(self.state.issued), 1)
        self.assertEqual(self.state.revoked, ["agent-source-secret-1"])
        with self.assertRaisesRegex(intents.identity.IdentityError, "revoked source intent"):
            self.operate("renew", command="command:credential:renew", inventory_reader=admission_snapshot)

    def test_admission_is_rechecked_after_custody_preflight_before_remote_mint(self):
        self.organization_source()
        calls = []
        def reader():
            calls.append(True)
            snapshot = admission_snapshot()
            if len(calls) > 1:
                inventory = yaml.safe_load(snapshot.inventory)
                inventory["repos"]["sample-owner"]["posture"] = "suspended"
                snapshot = intents.identity.replace(snapshot, inventory=yaml.safe_dump(inventory).encode())
            return snapshot
        with self.assertRaises(intents.identity.IdentityError):
            self.operate(inventory_reader=reader)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.state.issued, [])

    def test_real_prototype_subject_is_not_disguised_as_delivery(self):
        self.value = source_input(prototype=True)
        result = self.operate()
        self.assertEqual(result["subject"], self.value["source_intent"]["subject"])
        self.assertNotIn("work_item_ref", result["subject"])
        self.assertNotEqual(result["subject"]["registry_revision"], result["subject"]["source_revision"])

    def test_ordinary_intent_cannot_adopt_workflow_maintenance_projection(self):
        self.state.workflow_granted = True
        self.value = source_input()
        self.operate()
        path, credential = self.credential()
        credential.update(purpose="workflow-maintenance", approval_ref="operator:workflow-approval")
        intents.identity.write_json_atomic(path, credential)
        issued = len(self.state.issued)
        with self.assertRaisesRegex(intents.identity.IdentityError, "differs from the approved source intent"):
            self.operate(action="renew", command="command:credential:renew")
        self.assertEqual(issued, len(self.state.issued))

    def test_lost_ack_and_concurrent_issue_replay_do_not_mint_again(self):
        self.value = source_input()
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda _: self.operate(), range(3)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])
        self.assertEqual(len(self.state.issued), 1)

    def test_session_binds_once_and_current_renewal_does_not_rotate(self):
        self.value = source_input()
        self.operate()
        self.value["session_id"] = "source-session:sample:1"
        result = self.operate("renew", command="command:credential:renew")
        self.assertEqual(result["outcome"], "current")
        self.assertEqual(result["session_id"], self.value["session_id"])
        self.assertEqual(len(self.state.issued), 1)
        for session in (None, "source-session:other:1"):
            wrong = deepcopy(self.value)
            wrong["session_id"] = session
            with self.assertRaisesRegex(intents.identity.IdentityError, "different session"):
                self.operate("renew", value=wrong, command="command:credential:other")

    def test_near_expiry_renewal_revokes_old_and_replays_without_rotation(self):
        self.value = source_input()
        self.operate()
        path, credential = self.credential()
        credential["token_expires_at"] = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()
        intents.identity.write_json_atomic(path, credential)
        with self.assertRaisesRegex(intents.identity.IdentityError, "renewal is required"):
            self.operate(command="command:credential:reissue")
        result = self.operate("renew", command="command:credential:renew")
        self.assertEqual(result["outcome"], "renewed")
        self.assertIn(credential["token"], self.state.revoked)
        self.assertEqual(len(self.state.issued), 2)
        self.assertEqual(result, self.operate("renew", command="command:credential:renew"))
        self.assertEqual(len(self.state.issued), 2)

    def test_revoke_survives_projection_loss_and_delayed_issue(self):
        self.value = source_input()
        original = self.operate()
        path, credential = self.credential()
        result = self.operate("revoke", command="command:credential:revoke")
        self.assertEqual(result["outcome"], "revoked")
        self.assertFalse(path.exists())
        self.assertIn(credential["token"], self.state.revoked)
        # Historical acknowledgement is recoverable; it does not recreate a token.
        self.assertEqual(original, self.operate())
        for action in ("issue", "renew"):
            with self.assertRaisesRegex(intents.identity.IdentityError, "revoked"):
                self.operate(action, command=f"command:credential:late-{action}")
        self.assertEqual(len(self.state.issued), 1)

    def test_cancel_before_issuance_prevents_delayed_issue(self):
        self.value = source_input()
        self.operate("revoke", command="command:credential:cancel")
        with self.assertRaisesRegex(intents.identity.IdentityError, "revoked"):
            self.operate()
        self.assertEqual(self.state.issued, [])

    def test_missing_projection_requires_explicit_renew_not_issue_replay(self):
        self.value = source_input()
        original = self.operate()
        path, _ = self.credential()
        path.unlink()
        self.assertEqual(original, self.operate())
        self.assertFalse(path.exists())
        with self.assertRaisesRegex(intents.identity.IdentityError, "renewal is required"):
            self.operate(command="command:credential:reissue")
        self.operate("renew", command="command:credential:renew")
        self.assertTrue(path.exists())

    def test_expired_approval_denies_issue_but_allows_tombstone(self):
        self.value = source_input()
        self.value["source_intent"]["expires_at"] = "2000-01-01T00:00:00Z"
        with self.assertRaisesRegex(intents.identity.IdentityError, "expired"):
            self.operate()
        self.operate("revoke", command="command:credential:cancel")
        self.assertEqual(self.state.issued, [])

    def test_changed_intent_and_cross_landing_unit_identity_are_denied(self):
        self.value = source_input()
        self.operate()
        for key, changed in (
            ("branch", "feature/other"), ("fetched_base", "c" * 40),
            ("intent_id", "source-intent:other:1"), ("source_start_digest", "sha256:" + "c" * 64),
            ("landing_unit_id", "other-source-credential"),
        ):
            wrong = deepcopy(self.value)
            wrong["source_intent"][key] = changed
            with self.subTest(key=key), self.assertRaises(intents.identity.IdentityError):
                self.operate("renew", value=wrong, command=f"command:changed:{key}")
        self.assertEqual(len(self.state.issued), 1)

    def test_bad_scope_subject_and_provider_inputs_fail_before_mint(self):
        cases = [
            ("purpose", "trusted-bootstrap"), ("caller_id", "other"), ("operator_id", "other"),
            ("repository", "mfshaf7/unadmitted"), ("repository_id", 1), ("installation_id", 1),
            ("branch", "main"), ("fetched_base", "main"), ("human_reviewer_id", "agent-gary"),
            ("expires_at", "2026-10-18T00:00:00"), ("repository_id", True),
            ("subject", {"kind": "delivery", "work_item_ref": "prototype:fake", "snapshot_digest": "sha256:" + "a" * 64}),
            ("subject", {"kind": "prototype", "work_item_ref": "work-item-1298"}),
        ]
        for key, changed in cases:
            self.value = source_input()
            self.value["source_intent"][key] = changed
            with self.subTest(key=key, changed=changed), self.assertRaises(intents.identity.IdentityError):
                self.operate()
        self.assertEqual(self.state.issued, [])

    def test_suspended_and_ambient_credentials_cannot_be_borrowed(self):
        self.value = source_input()
        contract = intents.identity.load_contract(self.args().contract)
        self.runtime.mkdir(mode=0o700)
        (self.runtime / contract.suspension_filename).write_text("suspended")
        with self.assertRaisesRegex(intents.identity.IdentityError, "suspended"):
            self.operate()
        (self.runtime / contract.suspension_filename).unlink()
        args = self.args()
        intent = self.value["source_intent"]
        for key in ("landing_unit_id", "branch", "fetched_base", "human_reviewer_id"):
            setattr(args, key, intent[key])
        directory = intents.identity.session_directory(self.runtime, intent["landing_unit_id"])
        repository = intents.identity.expected_repository(contract, intent["repository"])
        with intents.identity.projection_lock(contract, self.runtime):
            intents.identity.deliver_locked(contract, args, repository, directory, None)
        with self.assertRaisesRegex(intents.identity.IdentityError, "cannot be borrowed"):
            self.operate()

    def test_projection_written_but_receipt_lost_recovers_without_mint(self):
        self.value = source_input()
        original_write = intents.identity.write_json_atomic
        def fail_final_receipt(path, payload):
            if path.parent.name == "source-intents" and payload.get("operations"):
                raise OSError("injected final receipt failure")
            return original_write(path, payload)
        with patch.object(intents.identity, "write_json_atomic", side_effect=fail_final_receipt):
            with self.assertRaisesRegex(OSError, "injected"):
                self.operate()
        self.assertEqual(len(self.state.issued), 1)
        result = self.operate()
        self.assertIn(result["outcome"], {"issued", "current"})
        self.assertEqual(len(self.state.issued), 1)

    def test_unknown_issuance_is_not_reminted_and_cancel_does_not_claim_revoke(self):
        self.value = source_input()
        def lose_during_issue(*args, before_issue=None):
            before_issue()
            raise OSError("simulated process loss")
        with patch.object(intents.identity, "deliver_locked", side_effect=lose_during_issue):
            with self.assertRaises(OSError):
                self.operate()
        with self.assertRaisesRegex(intents.identity.IdentityError, "outcome uncertain"):
            self.operate()
        with self.assertRaisesRegex(intents.identity.IdentityError, "intent revoked; unprojected"):
            self.operate("revoke", command="command:credential:revoke")
        with self.assertRaisesRegex(intents.identity.IdentityError, "revoked"):
            self.operate("renew", command="command:credential:renew")
        self.assertEqual(self.state.issued, [])

    def test_custody_preflight_failure_does_not_create_an_hour_long_recovery_wait(self):
        self.value = source_input()
        with patch.object(intents.identity, "private_key_file", side_effect=intents.identity.IdentityError("synthetic Vault unavailable")):
            with self.assertRaisesRegex(intents.identity.IdentityError, "Vault unavailable"):
                self.operate()
        self.assertEqual(self.state.issued, [])
        result = self.operate()
        self.assertEqual(result["outcome"], "issued")
        self.assertEqual(len(self.state.issued), 1)

    def test_existing_authenticated_provider_runs_actual_issuer_and_recovers_cold_read(self):
        product_tests = Path(__file__).parents[1] / "products/governance-operations-console/scripts/test_platform_operation_provider.py"
        spec = importlib.util.spec_from_file_location("source_intent_provider_fixture", product_tests)
        fixtures = importlib.util.module_from_spec(spec)
        assert spec.loader
        spec.loader.exec_module(fixtures)
        provider = fixtures.provider
        policy = fixtures.accepted_policy(self.work)
        # Real Git producer -> immutable current canonical records -> actual
        # authenticated provider -> actual one-repository issuer. No inventory
        # caller assertions or stubbed freshness/schema checks.
        snapshot = admission_snapshot()
        source = self.work / "canonical-source"
        source.mkdir()
        git = provider.record_authority.git
        git(source, "init", "-b", "main")
        git(source, "config", "user.name", "Synthetic reviewed source")
        git(source, "config", "user.email", "synthetic@example.invalid")
        files = {"contracts/repos.yaml": snapshot.inventory,
                 "contracts/intake-register.yaml": snapshot.intake,
                 "contracts/schemas/repos.schema.json": json.dumps(snapshot.inventory_schema).encode(),
                 "contracts/schemas/intake-register.schema.json": json.dumps(snapshot.intake_schema).encode()}
        for name, content in files.items():
            path = source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        git(source, "add", ".")
        git(source, "commit", "-m", "synthetic reviewed owner admission")
        reviewed = git(source, "rev-parse", "HEAD")
        policy["security"]["reviewed_revisions"]["workspace-governance"] = reviewed
        cache = Path(policy["runtime_state_root"]) / "record-authority"
        provider.record_authority.refresh_snapshot(cache, source, "workspace-governance", reviewed, remote_for_test=source)
        marker = Path(policy["runtime_state_root"]) / "active.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({
            "schema_version": 1, "platform_revision": fixtures.SOURCE, "platform_tree": provider.git_tree(),
            "security_decision_digest": policy["security"]["decision_digest"],
            "security_decision_uri": policy["security"]["decision_uri"],
            "activated_at": datetime.now(timezone.utc).isoformat(),
        }))
        caller = policy["platform_operation_provider"]["caller_id"]
        self.organization_source()
        self.value["source_intent"]["caller_id"] = caller
        command = fixtures.command(policy, action="agent-source.issue", input_value=self.value)
        command["capability_id"] = "agent-source.issue"
        command["intent_digest"] = provider.canonical_digest(provider.command_intent(command))
        command["approval"]["intent_digest"] = command["intent_digest"]
        store = provider.OperationStore(self.work / "provider")
        service = provider.ProviderService(policy, self.work / "policy.yaml", store, fixtures.SOURCE)
        server = ThreadingHTTPServer(("127.0.0.1", 0), provider.handler_for(service, caller, "synthetic-test-secret"))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        headers = {"content-type": "application/json", "x-platform-caller-id": caller, "x-platform-caller-secret": "synthetic-test-secret"}
        def send(path, payload=None, *, auth=True):
            request = Request(base + path, data=json.dumps(payload).encode() if payload is not None else None,
                              headers=headers if auth else {"content-type": "application/json"})
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        original_operate = intents.operate
        def sandbox_issuer(_args, **kwargs):
            # Only custody transport is replaced: the actual issuer, provider HTTP,
            # projection, journal and receipt implementation run unchanged.
            return original_operate(self.args(), **kwargs)
        try:
            with self.assertRaises(HTTPError) as rejected:
                send("/v1/console-operations/commands", {"command": command}, auth=False)
            self.assertEqual(rejected.exception.code, 403)
            self.assertEqual(self.state.issued, [])
            with patch.object(provider, "spawn_worker"):
                status, queued = send("/v1/console-operations/commands", {"command": command})
                self.assertEqual(status, 202)
            self.assertFalse(queued["cancel_available"])
            with patch.object(provider, "git_head", return_value=fixtures.SOURCE), patch.object(provider.source_credentials, "operate", side_effect=sandbox_issuer):
                self.assertEqual(provider.execute_worker(store, policy, command["command_id"]), 0)
            _, completed = send("/v1/console-operations/by-command/" + command["command_id"])
            self.assertEqual(completed["state"], "succeeded")
            result = completed["receipt"]["source_credential"]
            self.assertEqual(result["source_intent_digest"], intents.digest(self.value["source_intent"]))
            _, credential = self.credential()
            self.assertNotIn(credential["token"], json.dumps(completed))
            self.assertNotIn(credential["token"], "".join(path.read_text() for path in store.logs.glob("*.log")))
            # A recreated service uses the same private operation journal, no issuer
            # call or fresh command, and recovers the exact historical receipt.
            cold = provider.ProviderService(policy, self.work / "policy.yaml", provider.OperationStore(store.root), fixtures.SOURCE)
            self.assertEqual(cold.read(command["command_id"]), completed)
            self.assertEqual(len(self.state.issued), 1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_failure_after_remote_issue_without_projection_requires_expiry_not_remint(self):
        self.value = source_input()
        original_write = intents.identity.write_json_atomic
        contract = intents.identity.load_contract(self.args().contract)
        def fail_projection(path, payload):
            if path.name == contract.credential_filename:
                raise OSError("injected projection failure")
            return original_write(path, payload)
        with patch.object(intents.identity, "write_json_atomic", side_effect=fail_projection):
            with self.assertRaises(OSError):
                self.operate()
        self.assertEqual(len(self.state.issued), 1)
        # Existing issuer attempts provider revocation on projection failure.
        self.assertEqual(len(self.state.revoked), 1)
        # Still no fabricated proof: process-loss recovery cannot assume that
        # compensation succeeded just because this particular fixture did.
        with self.assertRaises(intents.SourceIntentError) as uncertain:
            self.operate()
        self.assertIsNotNone(uncertain.exception.retry_after)
        self.assertEqual(len(self.state.issued), 1)

    def test_state_file_symlinks_and_public_permissions_are_denied(self):
        self.value = source_input()
        self.operate()
        state = next((self.work / "provider/source-intents").glob("*.json"))
        state.chmod(0o644)
        with self.assertRaisesRegex(intents.identity.IdentityError, "private regular"):
            self.operate("renew", command="command:credential:unsafe")
        state.chmod(0o600)
        target = state.with_suffix(".retained")
        state.rename(target)
        state.symlink_to(target)
        with self.assertRaises(OSError):
            self.operate("renew", command="command:credential:symlink")

    def test_command_replay_cannot_change_action_or_subject(self):
        self.value = source_input()
        self.operate()
        with self.assertRaisesRegex(intents.identity.IdentityError, "replay conflicts"):
            self.operate("revoke")
        changed = deepcopy(self.value)
        changed["source_intent"]["subject"]["snapshot_digest"] = "sha256:" + "c" * 64
        with self.assertRaises(intents.identity.IdentityError):
            self.operate(value=changed)
        self.assertEqual(len(self.state.issued), 1)

    def test_approved_recovery_keeps_landing_unit_rotates_branch_and_preserves_history(self):
        self.value = source_input()
        first = self.operate()
        self.operate("revoke", command="command:first:revoke")
        old = deepcopy(self.value)
        self.value["source_intent"].update({
            "intent_id": "source-intent:sample:2", "branch": "feature/sample-source-recovery-2",
            "source_start_digest": "sha256:" + "c" * 64,
            "supersedes_intent_digest": first["source_intent_digest"],
        })
        second = self.operate(command="command:second:issue")
        self.assertEqual(first["landing_unit_id"], second["landing_unit_id"])
        self.assertNotEqual(first["branch"], second["branch"])
        self.assertEqual(len(self.state.issued), 2)
        _, current = self.credential()
        self.assertEqual(self.operate(value=old), first)
        # An old revoke can replay its old receipt, but cannot revoke the new token.
        replay = self.operate("revoke", value=old, command="command:first:revoke")
        self.assertEqual(replay["source_intent_digest"], first["source_intent_digest"])
        self.assertNotIn(current["token"], self.state.revoked)
        with self.assertRaisesRegex(intents.identity.IdentityError, "superseded"):
            self.operate("revoke", value=old, command="command:first:late-revoke")
        self.assertNotIn(current["token"], self.state.revoked)

    def test_successor_requires_exact_revoked_predecessor_not_a_new_name(self):
        self.value = source_input()
        first = self.operate()
        next_value = deepcopy(self.value)
        next_value["source_intent"].update({"intent_id": "source-intent:sample:2", "branch": "feature/recovery-2",
                                          "source_start_digest": "sha256:" + "c" * 64,
                                          "supersedes_intent_digest": first["source_intent_digest"]})
        with self.assertRaises(intents.identity.IdentityError):
            self.operate(value=next_value, command="command:next:premature")
        self.operate("revoke", command="command:first:revoke")
        next_value["source_intent"]["supersedes_intent_digest"] = "sha256:" + "f" * 64
        with self.assertRaises(intents.identity.IdentityError):
            self.operate(value=next_value, command="command:next:wrong-predecessor")
        next_value["source_intent"]["supersedes_intent_digest"] = first["source_intent_digest"]
        next_value["source_intent"]["subject"]["work_item_ref"] = "work-item-1300"
        with self.assertRaises(intents.identity.IdentityError):
            self.operate(value=next_value, command="command:next:wrong-subject")
        self.assertEqual(len(self.state.issued), 1)

    def test_fresh_approval_can_reauthorize_unchanged_work_without_source_or_branch_churn(self):
        self.value = source_input()
        self.value["session_id"] = "source-session:sample:existing"
        first = self.operate()
        original = deepcopy(self.value)
        self.operate("revoke", command="command:first:explicit-revoke")
        self.value["source_intent"].update({
            "intent_id": "source-intent:sample:reauthorized",
            "supersedes_intent_digest": first["source_intent_digest"],
            "expires_at": (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat().replace("+00:00", "Z"),
        })
        second = self.operate(command="command:reauthorized:explicit-issue")
        self.assertEqual(second["source_start_digest"], first["source_start_digest"])
        self.assertEqual(second["branch"], first["branch"])
        self.assertEqual(second["session_id"], first["session_id"])
        self.assertNotEqual(second["source_intent_digest"], first["source_intent_digest"])
        self.assertEqual(len(self.state.issued), 2)
        self.assertEqual(self.operate(value=original), first)
        with self.assertRaisesRegex(intents.identity.IdentityError, "superseded"):
            self.operate("renew", value=original, command="command:old:late-renew")
        self.assertEqual(len(self.state.issued), 2)


class BootstrapSourceIntentTests(unittest.TestCase):
    setUpClass = classmethod(fixture.AgentSourceIdentityTests.setUpClass.__func__)
    tearDownClass = classmethod(fixture.AgentSourceIdentityTests.tearDownClass.__func__)
    setUp = fixture.AgentSourceIdentityTests.setUp
    tearDown = fixture.AgentSourceIdentityTests.tearDown
    args = SourceIntentTests.args
    operate = SourceIntentTests.operate
    credential = SourceIntentTests.credential
    organization_source = SourceIntentTests.organization_source

    def bootstrap_source(self, *, workflow=False):
        self.organization_source()
        snapshot = proposed_snapshot()
        entry = yaml.safe_load(snapshot.intake)["repos"]["sample-owner"]
        self.value["source_intent"].update(purpose="trusted-owner-bootstrap", subject={
            "kind": "repository-bootstrap", "owner_repo": "sample-owner",
            "intake_entry_ref": {"id": entry["record"]["id"], "version": entry["record"]["version"], "digest": intents.digest(entry)},
            "custody_receipt_digest": "sha256:" + "c" * 64, "template_digest": "sha256:" + "d" * 64,
            "plan_digest": "sha256:" + "e" * 64, "decision_ref": "operator:fixture-owner-bootstrap",
            "allowed_paths": sorted(["AGENTS.md", "contracts/delivery-art-work-session/evidence-profile.json"] +
                                    ([".github/workflows/validate.yaml"] if workflow else [])),
            "workflow_write": workflow, "workflow_approval_ref": "operator:fixture-workflows-grant" if workflow else None,
        })
        return snapshot

    def test_bootstrap_uses_the_same_exact_issuer_but_a_separately_marked_four_permission_projection(self):
        snapshot = self.bootstrap_source()
        result = self.operate(inventory_reader=lambda: snapshot)
        _, credential = self.credential()
        self.assertEqual(result["purpose"], "trusted-owner-bootstrap")
        self.assertEqual(credential["purpose"], result["purpose"])
        self.assertEqual(credential["bootstrap_plan_digest"], self.value["source_intent"]["subject"]["plan_digest"])
        self.assertFalse(credential["workflow_write"])
        self.assertEqual(self.state.issued, [("sample-owner",)])
        self.assertEqual(set(self.state.issued_permissions[-1]), {"metadata", "contents", "pull_requests", "checks"})
        self.assertEqual(result, self.operate(inventory_reader=lambda: snapshot))
        self.assertEqual(len(self.state.issued), 1)
        self.assertFalse(any(self.work.rglob(".git")), "The issuer must not create source checkouts")
        for record in (self.work / "provider").rglob("*.json"):
            self.assertNotIn(credential["token"], record.read_text())

    def test_ordinary_parser_and_ordinary_issuance_cannot_borrow_proposed_bootstrap(self):
        snapshot = self.bootstrap_source()
        with self.assertRaisesRegex(intents.identity.IdentityError, "ordinary source"):
            intents.validate_input(self.value, caller_id=CALLER, operator_id=OPERATOR)
        with self.assertRaisesRegex(intents.identity.IdentityError, "canonical record reader"):
            self.operate()
        self.value["source_intent"]["purpose"] = "ordinary-source"
        with self.assertRaisesRegex(intents.identity.IdentityError, "subject kind"):
            self.operate(inventory_reader=lambda: snapshot)
        self.value["source_intent"]["subject"] = source_input()["source_intent"]["subject"]
        with self.assertRaises(intents.identity.IdentityError):
            self.operate(inventory_reader=lambda: snapshot)
        self.assertEqual(self.state.issued, [])

    def test_optional_workflow_needs_separate_approval_and_actual_provider_grant(self):
        snapshot = self.bootstrap_source(workflow=True)
        subject = self.value["source_intent"]["subject"]
        subject["workflow_approval_ref"] = None
        with self.assertRaisesRegex(intents.identity.IdentityError, "separate operator"):
            self.operate(inventory_reader=lambda: snapshot)
        subject["workflow_approval_ref"] = "operator:fixture-workflows-grant"
        self.state.workflow_granted = False
        with self.assertRaises(intents.identity.IdentityError):
            self.operate(inventory_reader=lambda: snapshot)
        self.assertEqual(self.state.issued, [])
        self.state.workflow_granted = True
        result = self.operate(inventory_reader=lambda: snapshot)
        self.assertEqual(result["permissions"]["workflows"], "write")
        self.assertTrue(self.credential()[1]["workflow_write"])

    def test_source_only_proposed_authority_is_rechecked_before_mint_and_preflight_failure_is_recoverable(self):
        snapshot = self.bootstrap_source()
        calls = []
        def changed():
            calls.append(True)
            if len(calls) == 1:
                return snapshot
            intake = yaml.safe_load(snapshot.intake)
            intake["repos"]["sample-owner"]["status"] = "admitted"
            return intents.identity.replace(snapshot, intake=yaml.safe_dump(intake).encode())
        with self.assertRaisesRegex(intents.identity.IdentityError, "current proposed"):
            self.operate(inventory_reader=changed)
        self.assertEqual(self.state.issued, [])
        self.assertEqual(self.operate(inventory_reader=lambda: snapshot)["outcome"], "issued")
        self.assertEqual(len(self.state.issued), 1)

    def test_bootstrap_refuses_status_security_provider_and_finite_path_substitution(self):
        for mode in ("admitted", "out-of-scope", "security", "control-owner", "entry-version", "provider", "inventory", "retired", "duplicate"):
            with self.subTest(mode=mode):
                snapshot = self.bootstrap_source()
                intake, inventory = yaml.safe_load(snapshot.intake), yaml.safe_load(snapshot.inventory)
                entry = intake["repos"]["sample-owner"]
                if mode in {"admitted", "out-of-scope"}: entry["status"] = mode
                elif mode == "security": entry["requires_security_bindings"] = True
                elif mode == "control-owner": entry["validation_behavior"]["wgcf_graph_role"] = "control-owner"
                elif mode == "entry-version": entry["record"]["version"] += 1
                elif mode == "provider": entry["provider_repository"]["provider_repository_id"] = "42"
                elif mode in {"inventory", "retired"}:
                    inventory["repos" if mode == "inventory" else "retired_repos"]["sample-owner"] = {
                        "posture": "suspended", "lifecycle": "suspended"}
                else:
                    intake["repos"]["duplicate"] = deepcopy(entry)
                snapshot = intents.identity.replace(snapshot, intake=yaml.safe_dump(intake).encode(), inventory=yaml.safe_dump(inventory).encode())
                with self.assertRaises(intents.identity.IdentityError): self.operate(inventory_reader=lambda: snapshot)
                self.assertEqual(self.state.issued, [])
        snapshot = self.bootstrap_source()
        self.value["source_intent"]["subject"]["allowed_paths"].append("app/arbitrary-code.js")
        with self.assertRaisesRegex(intents.identity.IdentityError, "trusted owner-control"):
            self.operate(inventory_reader=lambda: snapshot)
        self.assertEqual(self.state.issued, [])

    def test_revocation_does_not_depend_on_proposed_authority_and_revoked_purpose_cannot_renew(self):
        snapshot = self.bootstrap_source()
        self.operate(inventory_reader=lambda: snapshot)
        def unavailable(): raise AssertionError("revocation must not read current records")
        result = self.operate("revoke", command="command:bootstrap:stop", inventory_reader=unavailable)
        self.assertEqual(result["outcome"], "revoked")
        self.assertEqual(result["purpose"], "trusted-owner-bootstrap")
        self.assertEqual(self.state.revoked, ["agent-source-secret-1"])
        with self.assertRaisesRegex(intents.identity.IdentityError, "revoked source intent"):
            self.operate("renew", command="command:bootstrap:late-renew", inventory_reader=lambda: snapshot)
        self.assertEqual(len(self.state.issued), 1)

    def test_selected_entry_not_global_register_revision_binds_bootstrap_authority(self):
        snapshot = self.bootstrap_source()
        def unrelated_changes():
            intake = yaml.safe_load(snapshot.intake)
            intake["repos"]["unrelated-no-provider"] = {"status": "out-of-scope"}
            return intents.identity.replace(snapshot, intake=yaml.safe_dump(intake).encode(), revision="f" * 40)
        self.assertEqual(self.operate(inventory_reader=unrelated_changes)["outcome"], "issued")


if __name__ == "__main__":
    unittest.main()
