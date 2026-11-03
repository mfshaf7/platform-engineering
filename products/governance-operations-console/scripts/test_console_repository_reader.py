"""Renewal, delivery recovery and core-isolation proof for the Console reader."""
import base64
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import yaml
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import repository_provider_identity as identity
import repository_provider_account as account
from test_repository_provider_account import token
import console_repository_reader as runtime
import console_complete_runtime as complete
import console_workflow_credentials as workflows


class ReaderMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.definition = account.contract(ROOT / "security/repository-provider-identity.yaml")
        self.target = identity.DevIntegrationTarget("accepted-idea-delivery", "synthetic", "session", "devint-test", "https://127.0.0.1:6443")
        self.args = SimpleNamespace(app_id=123, installation_id=456, account="example-owner")
        self.calls, self.renewals, self.consumed = [], 0, True
        self.key = self.root / "key.pem"
        self.key.write_text("synthetic key"); self.key.chmod(0o600)
        self.reader = runtime.Reader(repo_root=ROOT, workspace_root=self.root, state_root=self.root,
            session_manifest=self.root / "session.yaml", run=self.run_command, private_key=lambda _: self.key)
        self.install(token())
        self.guards = [patch.object(runtime.identity, "load_dev_integration_target", return_value=self.target),
            patch.object(runtime.identity, "verify_dev_integration_cluster", return_value=self.target)]
        for guard in self.guards: guard.start(); self.addCleanup(guard.stop)

    def install(self, issued, *, outcome="delivered", version="1"):
        self.missing = False
        self.value = account.receipt(self.args, self.definition, "deliver", outcome, token=issued, target=self.target)
        identity.write_receipt(self.reader.path, self.value)
        self.secret = yaml.safe_load(account.secret_manifest(self.args, self.definition, issued, self.target))
        self.secret["data"] = {key: base64.b64encode(value.encode()).decode() for key, value in self.secret.pop("stringData").items()}
        self.secret["metadata"]["resourceVersion"] = version

    def run_command(self, args, **kwargs):
        self.calls.append(args)
        if "get" in args and "secret" in args: return SimpleNamespace(stdout="" if self.missing else json.dumps(self.secret))
        if args[0] == sys.executable:
            self.renewals += 1
            self.install(token("ghs_rotated_metadata_only"), version="2")
            return SimpleNamespace(stdout="")
        if "exec" in args: return SimpleNamespace(stdout=json.dumps({"consumed": self.consumed}))
        raise AssertionError("unexpected command")

    def test_healthy_tick_and_restart_reuse_the_existing_delivery(self):
        for _ in range(2):
            result = self.reader.maintain()
            self.assertEqual(result["binding"], {"account": "example-owner", "version": "1"})
            self.assertEqual(self.reader.probe()["state"], "consumed")
        self.assertEqual(self.renewals, 0)
        self.assertFalse(any("patch" in call for call in self.calls))

    def test_expiry_renews_same_account_and_retires_old_token_only_after_consumption(self):
        old = token(minutes=5); self.install(old)
        result = self.reader.maintain()
        self.assertEqual(result["state"], "renewed"); self.assertEqual(self.renewals, 1)
        command = next(call for call in self.calls if call[0] == sys.executable)
        self.assertIn("--account", command); self.assertNotIn("--repository", command)
        self.assertFalse(self.key.exists())
        self.consumed = False
        provider = Mock()
        with patch.object(runtime.identity, "ProviderClient", return_value=provider):
            with self.assertRaises(identity.IdentityError): self.reader.probe()
            provider.revoke_token.assert_not_called()
            self.consumed = True; self.reader.probe()
            provider.revoke_token.assert_called_once_with(old.token)
        self.assertNotIn(old.token, json.dumps(self.calls))

    def test_crash_after_secret_projection_recovers_without_issuing_another_token(self):
        self.install(token(), outcome="prepared")
        self.reader.maintain()
        self.assertEqual(json.loads(self.reader.path.read_text())["outcome"], "delivered")
        self.assertEqual(self.renewals, 0)

    def test_mismatch_or_unsafe_selection_never_renews_or_reports_consumed(self):
        self.secret["data"][runtime.ACCOUNT_ENV] = base64.b64encode(b"foreign-owner").decode()
        with self.assertRaises(identity.IdentityError): self.reader.maintain()
        self.assertEqual(self.renewals, 0)
        self.reader.path.chmod(0o644)
        with self.assertRaises(identity.IdentityError): self.reader.maintain()

    def test_missing_selection_does_not_enable_anything(self):
        self.reader.path.unlink()
        self.assertEqual(self.reader.maintain(), {"state": "not-selected"})
        self.assertEqual(self.calls, [])

    def test_missing_secret_is_restored_only_from_the_existing_approved_selection(self):
        self.missing = True
        result = self.reader.maintain()
        self.assertEqual(result["state"], "renewed")
        self.assertEqual(result["binding"]["account"], "example-owner")
        self.assertEqual(self.renewals, 1)
        self.assertEqual(self.reader.probe()["state"], "consumed")

    def test_disconnect_before_renewal_projection_is_preserved(self):
        self.install(token(minutes=5))
        original = self.reader.run
        def run(args, **kwargs):
            if args[0] == sys.executable:
                identity.write_receipt(self.reader.path, {**self.value, "outcome": "revoked"})
                account.command(SimpleNamespace(receipt=self.reader.path,
                    expected_selection_digest=args[args.index('--expected-selection-digest')+1]), 'deliver')
            return original(args, **kwargs)
        self.reader.run = run
        with self.assertRaisesRegex(identity.IdentityError, 'stale renewal'):
            self.reader.maintain()
        self.assertEqual(json.loads(self.reader.path.read_text())['outcome'], 'revoked')
        self.assertEqual(self.renewals, 0)
        self.assertFalse(self.key.exists())

    def test_disconnect_after_delivery_does_not_resurrect_the_reader(self):
        old = token(minutes=5); self.install(old)
        original = self.reader.run
        def run(args, **kwargs):
            result = original(args, **kwargs)
            if args[0] == sys.executable:
                identity.write_receipt(self.reader.path, {**self.value, "outcome": "revoked"})
            return result
        self.reader.run = run
        provider = Mock()
        with patch.object(runtime.identity, 'ProviderClient', return_value=provider):
            self.assertEqual(self.reader.maintain(), {'state':'revoked'})
            provider.revoke_token.assert_called_once_with(old.token)
        self.assertEqual(self.reader.maintain(), {'state':'revoked'})
        self.assertEqual(self.renewals, 1)

    def test_malformed_json_value_withholds_only_the_reader(self):
        identity.write_receipt(self.reader.path, [])
        with self.assertRaises(identity.IdentityError): self.reader.maintain()
        self.assertEqual(self.renewals, 0)


class ExistingTimerIntegrationTests(unittest.TestCase):
    def test_revoked_selection_clears_reader_consumption_without_disabling_other_identities(self):
        manager = Mock(); manager.renew.return_value = {'refreshed': []}
        selected = Mock(); selected.maintain.return_value = {'state':'revoked'}
        with patch.object(complete.repository_reader, 'Reader', return_value=selected), patch.object(complete, 'workflow_credential_manager', return_value=manager), patch.object(complete, 'dev_integration_session_manifest', return_value=ROOT / 'unused'):
            result = complete.renew_workflow_credentials({}, {'token_expires_at':'expiry'})
        self.assertEqual(manager.renew.call_args.kwargs['reader_binding'], {'revoked':True})
        self.assertEqual(result['repository_reader'], {'state':'revoked'})
        selected.probe.assert_not_called()

    def test_optional_reader_failure_does_not_block_existing_identity_maintenance(self):
        manager = Mock(); manager.renew.return_value = {"refreshed": []}
        selected = Mock(); selected.maintain.side_effect = identity.IdentityError("reader unavailable")
        with patch.object(complete.repository_reader, "Reader", return_value=selected), patch.object(complete, "workflow_credential_manager", return_value=manager), patch.object(complete, "dev_integration_session_manifest", return_value=ROOT / "unused"):
            result = complete.renew_workflow_credentials({}, {"token_expires_at": "synthetic-expiry"})
        manager.renew.assert_called_once_with(extra_annotations={"workspace-governance/repository-token-expires-at": "synthetic-expiry"})
        self.assertEqual(result["repository_reader"], {"state": "unavailable"})

    def test_same_rollout_consumes_only_the_two_optional_reader_fields(self):
        commands = []
        manager = workflows.Credentials(repo_root=ROOT, workspace_root=ROOT, session_manifest=ROOT / "unused",
            run=lambda args, **_: commands.append(args), private_key=None, readiness_revision="a" * 40)
        target = SimpleNamespace(namespace="devint-test")
        secret = {"metadata": {"resourceVersion": "1", "annotations": {workflows.ANNOTATION + "token-expires-at": "expiry"}}}
        bindings = {slug: (SimpleNamespace(wgcf_implementation_ref_env="WGCF_" + slug.upper().replace("-", "_") + "_IMPLEMENTATION_REF"), target, secret)
            for slug in workflows.READINESS_WORKFLOWS}
        manager.consume(bindings, None, reader_binding={"account": "example-owner", "version": "2"})
        payload = json.loads(commands[0][-1])
        env = payload["spec"]["template"]["spec"]["containers"][0]["env"]
        fields = [item for item in env if item["name"].startswith("OOS_REPOSITORY_")]
        self.assertEqual({item["name"] for item in fields}, {runtime.TOKEN_ENV, runtime.ACCOUNT_ENV})
        self.assertTrue(all(item["valueFrom"]["secretKeyRef"]["optional"] is True for item in fields))
        self.assertFalse(any("ENABLED" in item["name"] for item in env))


if __name__ == "__main__": unittest.main()
