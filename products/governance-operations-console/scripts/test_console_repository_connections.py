"""Account isolation and renewable connection projection in the existing timer."""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import console_repository_connections as runtime


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.calls = []; self.issued = 0; self.revoked = []; self.denied = set(); self.selected = set()
        self.secret = {"metadata": {"resourceVersion": "1"}, "data": {}}
        self.manager = runtime.Connections(state_root=self.root, namespace="devint-synthetic", run=self.run_command,
            private_key=self.key, client_factory=lambda _: self.client())
        self.value = {"schema_version": 1, "default_connection_id": "github:company", "connections": [
            {"account": "solo", "account_type": "personal", "grants": {"metadata": {"app_id": 1, "installation_id": 11}}},
            {"account": "company", "account_type": "organization", "grants": {"provisioning": {"app_id": 2, "installation_id": 22}}},
        ]}
        self.write_selection()
        guard = patch.object(runtime.identity, "create_app_jwt", side_effect=lambda app, _: f"jwt-{app}")
        guard.start(); self.addCleanup(guard.stop)

    def write_selection(self):
        self.manager.path.parent.mkdir(parents=True, exist_ok=True)
        self.manager.path.write_text(json.dumps(self.value)); self.manager.path.chmod(0o600)

    def key(self, _):
        path = self.root / "temporary-key"; path.write_text("synthetic"); return path

    def client(self):
        outer = self
        class Client:
            def authenticated_app(self, jwt):
                app = int(jwt.split('-')[1]); role = {1: "metadata", 2: "provisioning", 3: "lifecycle"}[app]
                return {"id": app, "permissions": runtime.PERMISSIONS[role], "events": []}
            def installation(self, identifier, jwt):
                if identifier in outer.denied: raise runtime.identity.IdentityError("provider access denied")
                app = int(jwt.split('-')[1]); role = {1: "metadata", 2: "provisioning", 3: "lifecycle"}[app]
                return {"id": identifier, "app_id": app, "account": {"id": 11 if identifier == 11 else 22, "login": "solo" if identifier == 11 else "company", "type": "User" if identifier == 11 else "Organization"},
                    "permissions": runtime.PERMISSIONS[role], "events": [], "repository_selection": "selected" if identifier in outer.selected else "all", "suspended_at": None}
            def issue_token(self, identifier, jwt, repositories, permissions):
                scoped = [{"id": 901, "full_name": "company/todo"}] if repositories == ["todo"] else []
                if repositories is not None and repositories != ["todo"]: raise AssertionError("unexpected per-repository filter")
                outer.issued += 1
                return runtime.identity.IssuedToken(f"ghs_synthetic_{identifier}_{outer.issued}",
                    (datetime.now(timezone.utc) + timedelta(minutes=50)).isoformat(), tuple(scoped), permissions,
                    "selected" if repositories or identifier in outer.selected else "all")
            def revoke_token(self, token): outer.revoked.append(token)
        return Client()

    def run_command(self, args, **kwargs):
        self.calls.append(args)
        self.assertFalse(any("ghs_" in str(arg) for arg in args))
        if "get" in args: return SimpleNamespace(stdout=json.dumps(self.secret))
        if "patch" in args:
            self.assertIn("--patch-file", args)
            payload = json.loads(kwargs['input_value'])
            self.assertEqual(payload['metadata']['resourceVersion'], self.secret['metadata']['resourceVersion'])
            self.secret['data'][runtime.ENV] = base64.b64encode(payload['stringData'][runtime.ENV].encode()).decode()
            self.secret['metadata']['resourceVersion'] = str(int(self.secret['metadata']['resourceVersion']) + 1)
            return SimpleNamespace(stdout="patched")
        if "exec" in args:
            raw = base64.b64decode(self.secret['data'][runtime.ENV])
            return SimpleNamespace(stdout=json.dumps({'digest': 'sha256:' + hashlib.sha256(raw).hexdigest()}))
        raise AssertionError("unexpected operation")

    def test_both_account_types_are_verified_and_restart_reuses_current_delivery(self):
        result = self.manager.maintain(); self.manager.probe(result['digest'])
        self.assertEqual(self.issued, 2)
        self.assertNotIn('ghs_', self.manager.state.read_text())
        self.assertEqual(self.manager.maintain()['state'], 'current')
        self.assertEqual(self.issued, 2)
        result = self.manager.maintain(force=True)
        self.assertEqual(self.revoked, [])
        self.manager.probe(result['digest'])
        self.assertEqual(len(self.revoked), 2)

    def test_one_denied_account_does_not_disable_a_healthy_account_or_choose_a_fallback(self):
        self.denied.add(11)
        result = self.manager.maintain(); self.manager.probe(result['digest'])
        payload = json.loads(base64.b64decode(self.secret['data'][runtime.ENV]))
        self.assertEqual([item['account'] for item in payload['connections']], ['company'])
        self.assertEqual(payload['default_connection_id'], 'github:company')
        self.assertEqual(json.loads(self.manager.state.read_text())['unavailable'], [{'account': 'solo', 'role': 'metadata'}])

    def test_disconnect_removes_grants_and_retires_previous_tokens_after_consumption(self):
        result = self.manager.maintain(); self.manager.probe(result['digest'])
        self.value['connections'] = []; self.value['default_connection_id'] = None; self.write_selection()
        result = self.manager.maintain(); self.manager.probe(result['digest'])
        payload = json.loads(base64.b64decode(self.secret['data'][runtime.ENV]))
        self.assertEqual(payload['connections'], []); self.assertEqual(len(self.revoked), 2)

    def test_selection_denies_duplicate_accounts_unknown_grants_and_nonprivate_files(self):
        for change in [lambda v: v['connections'].append(v['connections'][0]), lambda v: v['connections'][0]['grants'].update({'admin': {}}),
                       lambda v: v['connections'][0]['grants']['metadata'].update({'key_slot': '../outside'})]:
            original = json.loads(json.dumps(self.value)); change(self.value); self.write_selection()
            with self.assertRaises(runtime.identity.IdentityError): runtime.selection(self.manager.path)
            self.value = original
        self.write_selection(); self.manager.path.chmod(0o644)
        with self.assertRaises(runtime.identity.IdentityError): runtime.selection(self.manager.path)

    def test_lifecycle_keeps_exactly_one_repository_and_provisioning_retains_selected_installation(self):
        self.value['connections'][1]['grants']['lifecycle'] = {"app_id": 3, "installation_id": 33,
            "repository": {"name": "todo", "provider_repository_id": "901"}}
        self.selected.update({22,33}); self.write_selection()
        result = self.manager.maintain(); self.manager.probe(result['digest'])
        payload = json.loads(base64.b64decode(self.secret['data'][runtime.ENV]))
        self.assertEqual(payload['connections'][1]['grants']['lifecycle']['repository_id'], '901')
        self.assertEqual(self.issued, 3)
        del self.value['connections'][1]['grants']['lifecycle']['repository']; self.write_selection()
        with self.assertRaises(runtime.identity.IdentityError): runtime.selection(self.manager.path)


if __name__ == '__main__': unittest.main()
