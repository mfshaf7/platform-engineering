"""Negative checks for the inactive Prototype Closure identity boundary."""

from __future__ import annotations

from copy import deepcopy
import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import yaml

from prototype_closure_identity import commission, validate_definition


ROOT = Path(__file__).resolve().parents[1]
DEFINITION = yaml.safe_load((ROOT / "security/prototype-closure-identity.yaml").read_text())
SCHEMA = json.loads((ROOT / "security/schemas/prototype-closure-identity.schema.json").read_text())


class PrototypeClosureIdentityTests(unittest.TestCase):
    def test_definition_is_inactive(self) -> None:
        self.assertEqual([], validate_definition(DEFINITION, SCHEMA))
        self.assertIsNone(DEFINITION["selection"]["app_id"])
        self.assertFalse(DEFINITION["consumer"]["workflow_enabled"])

    def test_cannot_borrow_maturity_identity(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["identity"]["id"] = "prototype-maturity-github-app-v1"
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_cannot_broaden_repository_or_write_paths(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["identity"]["maximum_repository_count"] = 2
        changed["source_boundary"]["allowed_write_paths"].append("prototypes/**")
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_cannot_claim_activation_or_commissioned_credential(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["selection"]["runtime_enabled"] = True
        changed["secret_custody"]["key_commissioned"] = True
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_cannot_drop_provider_or_denial_controls(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["source_boundary"]["provider_enforcement_required"].remove(
            "prototype-closure-app-has-no-bypass"
        )
        changed["source_boundary"]["denied_actions"].remove("prototype-maturity-write")
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_cannot_skip_security_or_cleanup_evidence(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["security_authority"]["normal_availability_gate"] = None
        changed["activation"]["required_evidence"].remove(
            "exact-active-resource-revocation-or-absence-proof"
        )
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_cannot_drop_receipt_binding(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["audit"]["receipt_fields"].remove("security_receipt_ref")
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_cannot_rewrite_durable_source(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["rollback"]["delete_durable_owner_source"] = True
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_commission_requires_security_and_exact_source_revisions(self) -> None:
        with TemporaryDirectory() as directory:
            args = self.commission_args(Path(directory) / "receipt.json")
            args.security_receipt_ref = ""
            with self.assertRaisesRegex(Exception, "Security approval"):
                commission(args, b"definition", DEFINITION)
            args.security_receipt_ref = "security://approved"
            args.source_revision.pop()
            with self.assertRaisesRegex(Exception, "exact WGCF"):
                commission(args, b"definition", DEFINITION)

    def test_commission_revokes_proof_token_before_receipt(self) -> None:
        with TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "receipt.json"
            args = self.commission_args(receipt_path)
            client = Mock()
            token = SimpleNamespace(token="secret-proof-token", expires_at="2026-09-20T05:00:00Z")
            repository = SimpleNamespace(provider_repository_id=1231020532)
            with patch("prototype_closure_identity.remote_head", return_value="a" * 40), patch(
                "prototype_closure_identity.validated_token",
                return_value=(client, token, repository),
            ):
                commission(args, b"definition", DEFINITION)
            client.revoke_token.assert_called_once_with("secret-proof-token")
            receipt = json.loads(receipt_path.read_text())
            self.assertEqual("prototype-closure-identity-commission-receipt", receipt["artifact_type"])
            self.assertFalse(receipt["runtime_enabled"])
            self.assertEqual("platform-operator", receipt["caller_id"])
            self.assertEqual("2026-09-20T05:00:00Z", receipt["expires_at"])
            self.assertNotIn("secret-proof-token", receipt_path.read_text())

    def test_stale_source_cannot_request_provider_token(self) -> None:
        with TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "receipt.json"
            args = self.commission_args(receipt_path)
            with patch("prototype_closure_identity.remote_head", return_value="b" * 40), patch(
                "prototype_closure_identity.validated_token",
            ) as issue_token:
                with self.assertRaisesRegex(Exception, "not current remote main"):
                    commission(args, b"definition", DEFINITION)
            issue_token.assert_not_called()
            self.assertFalse(receipt_path.exists())

    def test_failed_revocation_writes_no_receipt(self) -> None:
        with TemporaryDirectory() as directory:
            receipt_path = Path(directory) / "receipt.json"
            args = self.commission_args(receipt_path)
            client = Mock()
            client.revoke_token.side_effect = RuntimeError("provider rejected revocation")
            token = SimpleNamespace(token="secret-proof-token", expires_at="2026-09-20T05:00:00Z")
            repository = SimpleNamespace(provider_repository_id=1231020532)
            with patch("prototype_closure_identity.remote_head", return_value="a" * 40), patch(
                "prototype_closure_identity.validated_token",
                return_value=(client, token, repository),
            ):
                with self.assertRaises(RuntimeError):
                    commission(args, b"definition", DEFINITION)
            self.assertFalse(receipt_path.exists())

    @staticmethod
    def commission_args(receipt: Path) -> argparse.Namespace:
        return argparse.Namespace(
            security_receipt_ref="security://approved",
            source_revision=[
                f"{repo}={'a' * 40}" for repo in (
                    "workspace-governance-control-fabric",
                    "operator-orchestration-service",
                    "platform-engineering",
                    "security-architecture",
                )
            ],
            app_id=123,
            installation_id=456,
            private_key_file=Path("unused-in-mock.pem"),
            provider_api_base_url=None,
            sandbox=False,
            receipt=receipt,
            caller_id="platform-operator",
            workspace_root=ROOT.parent,
        )


if __name__ == "__main__":
    unittest.main()
