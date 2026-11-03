"""Scope, renewal and recovery proof for the existing metadata reader."""
from datetime import datetime, timedelta, timezone
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import yaml
import repository_provider_identity as identity
import repository_provider_account as account

ROOT = Path(__file__).resolve().parents[1]


def token(value="ghs_synthetic_metadata_only", minutes=45):
    return identity.IssuedToken(value, (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat(), (), {"metadata": "read"}, "all")


class AccountScopeTests(unittest.TestCase):
    def setUp(self):
        self.definition = account.contract(ROOT / "security/repository-provider-identity.yaml")
        self.args = SimpleNamespace(app_id=123, installation_id=456, account="Example-Owner", repository=None,
            provider_api_base_url=None, sandbox=False, private_key_file=Path("unused-private-key"))
        self.client = Mock()
        self.client.authenticated_app.return_value = {"id": 123, "permissions": {"metadata": "read"}, "events": []}
        self.installation = {"id": 456, "app_id": 123, "account": {"login": "example-owner", "type": "Organization"},
            "permissions": {"metadata": "read"}, "events": [], "repository_selection": "all", "suspended_at": None}
        self.client.installation.return_value = self.installation
        self.client.issue_token.return_value = token()
        self.factory = patch.object(account.identity, "ProviderClient", return_value=self.client)
        self.signer = patch.object(account.identity, "create_app_jwt", return_value="synthetic-jwt")
        self.factory.start(); self.signer.start()
        self.addCleanup(self.factory.stop); self.addCleanup(self.signer.stop)

    def test_user_and_organization_connections_have_no_repository_snapshot(self):
        for kind in ("User", "Organization"):
            with self.subTest(kind=kind):
                self.installation["account"]["type"] = kind
                _, issued = account.issued(self.args, self.definition)
                self.assertEqual(issued.permissions, {"metadata": "read"})
                self.client.issue_token.assert_called_with(456, "synthetic-jwt", None, {"metadata": "read"})
        self.client.accessible_repositories.assert_not_called()

    def test_unapproved_scope_or_permissions_cannot_fall_back_to_broader_access(self):
        cases = [lambda: self.installation.update(repository_selection="selected"),
            lambda: self.installation.update(suspended_at="2026-11-03T00:00:00Z"),
            lambda: self.installation.update(permissions={"metadata": "read", "contents": "read"}),
            lambda: self.installation["account"].update(login="different-owner"),
            lambda: self.installation["account"].update(type="Enterprise"),
            lambda: self.client.authenticated_app.return_value.update(permissions={"metadata": "read", "administration": "write"})]
        original = json.loads(json.dumps(self.installation))
        for change in cases:
            self.installation.clear(); self.installation.update(json.loads(json.dumps(original)))
            self.client.authenticated_app.return_value = {"id": 123, "permissions": {"metadata": "read"}, "events": []}
            change()
            with self.assertRaises(identity.IdentityError): account.issued(self.args, self.definition)
        self.client.issue_token.assert_not_called()

    def test_invalid_issued_token_is_revoked_before_projection(self):
        for issued in (token(minutes=-1), identity.IssuedToken("ghs_bad_scope", token().expires_at, (), {"contents": "write"}),
                identity.IssuedToken("ghs_changed_selection", token().expires_at, (), {"metadata": "read"}, "selected"),
                identity.IssuedToken("ghs_missing_scope", token().expires_at, (), {"metadata": "read"})):
            self.client.issue_token.return_value = issued
            with self.assertRaises(identity.IdentityError): account.issued(self.args, self.definition)
            self.client.revoke_token.assert_called_with(issued.token)

    def test_receipts_and_secret_bind_the_account_without_credential_exposure(self):
        target = identity.DevIntegrationTarget("accepted-idea-delivery", "synthetic", "session", "devint-test", "https://127.0.0.1:6443")
        issued = token()
        receipt = account.receipt(self.args, self.definition, "deliver", "delivered", token=issued, target=target)
        self.assertEqual(receipt["scope"], {"kind": "account-metadata", "account": "example-owner"})
        self.assertEqual(receipt["provider_repositories"], [])
        self.assertNotIn(issued.token, json.dumps(receipt))
        manifest = yaml.safe_load(account.secret_manifest(self.args, self.definition, issued, target))
        self.assertEqual(set(manifest["stringData"]), {self.definition.runtime_secret_key, account.ACCOUNT_ENV})
        self.assertEqual(manifest["stringData"][account.ACCOUNT_ENV], "example-owner")
        self.assertNotEqual(receipt["credential_binding_digest"], account.binding_digest(self.definition, 123, 456, "another-owner"))

    def test_stale_renewal_cannot_overwrite_a_disconnected_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            self.args.receipt = Path(directory) / 'selection.json'
            identity.write_receipt(self.args.receipt, {"outcome": "revoked"})
            self.args.expected_selection_digest = 'sha256:' + '0' * 64
            with self.assertRaisesRegex(identity.IdentityError, 'stale renewal'):
                account.command(self.args, 'deliver')
            self.assertEqual(json.loads(self.args.receipt.read_text()), {"outcome": "revoked"})
            self.client.issue_token.assert_not_called()


if __name__ == "__main__": unittest.main()
