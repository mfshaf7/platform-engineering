import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import console_instance_records as records


class InstanceBindingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.state = Path(temporary.name) / "runtime"
        self.policy = {"runtime_state_root": str(self.state), "instance_records": {"enabled": True},
            "runtime": {"provider_port": 38491, "namespace_pattern": "oos-{operator}", "oos_deployment": "operator-orchestration-service"},
            "repository_provisioning": {"wgcf": {"namespace_pattern": "wgcf-{operator}", "deployment": "workspace-governance-control-fabric-api",
                "service": "workspace-governance-control-fabric-api", "port": 8080}}}

    def prepare(self):
        return records.prepare(self.policy, state_root=self.state, gateway="10.42.0.1", provider_secret="p" * 32, wgcf_port=38181)

    def test_default_off_is_inert_and_restart_keeps_original_identity_and_distinct_scoped_connection(self):
        self.policy["instance_records"]["enabled"] = False
        self.assertIsNone(self.prepare()); self.assertFalse(self.state.exists())
        self.policy["instance_records"]["enabled"] = True
        first = self.prepare(); self.assertEqual(self.prepare(), first)
        private = self.state / "private"
        host = json.loads((private / "instance-source-host.json").read_text())
        reader = json.loads((private / "instance-source-reader.json").read_text())
        self.assertEqual(host["instance_id"], reader["instance_id"])
        self.assertNotEqual(reader["caller_secret"], host["connection"]["callerSecret"])
        self.assertEqual(reader["base_url"], "http://127.0.0.1:38181")
        self.assertEqual(reader["caller_id"], "platform-engineering-source-reader")
        for file in private.iterdir(): self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        (private / "instance-source-host.json").unlink()
        self.assertEqual(self.prepare(), first)  # Derived projection can be repaired.
        (private / "instance-installation.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "original installation identity is missing"): self.prepare()

    def test_linked_or_public_bindings_and_public_or_link_local_provider_destinations_are_denied(self):
        for gateway in ("8.8.8.8", "169.254.1.2", "127.0.0.1"):
            with self.assertRaises(RuntimeError): records.prepare(self.policy, state_root=self.state, gateway=gateway, provider_secret="p" * 32, wgcf_port=38181)
        self.prepare(); original = self.state / "private/instance-installation.json"
        original.chmod(0o644)
        with self.assertRaisesRegex(RuntimeError, "original installation binding is invalid"): self.prepare()
        original.chmod(0o600)
        target = self.state / "private/instance-source-host.json"
        target.unlink(); target.symlink_to(original)
        with self.assertRaisesRegex(RuntimeError, "binding is linked"): self.prepare()

    def test_runtime_binding_waits_for_real_migration_then_enables_exact_existing_roles_without_secrets_in_argv(self):
        original = self.prepare(); calls = []
        def run(args, **kwargs):
            calls.append((args, kwargs))
            self.assertNotIn(original["source_reader_secret"], " ".join(args))
            return SimpleNamespace(stdout="0016_instance_records (head)\n")
        records.bind(self.policy, state_root=self.state, operator="test", run=run)
        self.assertEqual(calls[0][0][-2:], ["alembic", "current"])
        manifests = [json.loads(options["input_value"]) for _, options in calls if "input_value" in options]
        self.assertEqual(len(manifests), 2)
        self.assertEqual(manifests[0]["stringData"]["WGCF_INSTANCE_ID"], original["instance_id"])
        self.assertEqual(manifests[0]["stringData"]["WGCF_INSTANCE_SOURCE_CALLER_ID"], "platform-engineering-source-reader")
        self.assertNotIn("WGCF_ARTIFACT_REGISTRY_OOS_CALLER_SECRET", manifests[0]["stringData"])
        self.assertEqual(manifests[1]["stringData"]["OOS_INSTANCE_ID"], original["instance_id"])
        self.assertNotIn("WGCF_INSTANCE_SOURCE_CALLER_SECRET", manifests[1]["stringData"])
        calls.clear()
        def stale(args, **kwargs):
            calls.append(args)
            return SimpleNamespace(stdout="0015_product_publication (head)\n" if args[-1] == "current" else "")
        with self.assertRaises(RuntimeError): records.bind(self.policy, state_root=self.state, operator="test", run=stale)
        self.assertTrue(all("apply" not in call for call in calls))

    def test_a_future_database_revision_is_accepted_only_after_positive_migration_ancestry(self):
        self.prepare(); calls = []
        def descendant(args, **kwargs):
            calls.append(args)
            output = "0017_future (head)\n" if args[-1] == "current" else "0016_instance_records -> 0017_future (head)\n"
            return SimpleNamespace(stdout=output)
        records.bind(self.policy, state_root=self.state, operator="test", run=descendant)
        self.assertTrue(any(call[-1] == "0016_instance_records:0017_future" for call in calls))


if __name__ == "__main__": unittest.main()
