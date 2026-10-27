"""Filesystem composition witnesses, not live fulfillment or activation proof."""
import base64
import copy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import console_profile_requests as profiles


class ProfileRequestsCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="profile-composition-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.policy = {"purpose_profiles": {"enabled": True}, "security": {"status": "accepted"}}
        self.calls = []
        self.auth = {"CALLER_ALLOWED_IDS": profiles.CALLER + ",existing-owner",
                     "CALLER_AUTH_SHARED_SECRET": "synthetic-shared-credential",
                     "CALLER_AUTH_SECRETS_JSON": json.dumps({profiles.CALLER: "synthetic-console-credential",
                                                            "existing-owner": "synthetic-other-credential"})}
        self.settings = {}
        self.pod_settings = {}
        self.pod_auth = copy.deepcopy(self.auth)
        self.base_auth = copy.deepcopy(self.auth)
        self.secret_version = 1
        self.template_annotations = {}
        self.template_signature = None
        self.rollouts = 0
        self.registry = {"schema_version": 1, "artifact_type": "platform-model-profile-source-projection",
                         "owner_repo": "platform-engineering", "source": {"source_version": "a" * 40},
                         "profiles": [{"profile_id": "synthetic-reviewed-profile"}]}
        self.registry["digest"] = profiles.lifecycle.digest_value(self.registry)

    def owner_run(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if "project" in command:
            output = Path(command[command.index("--output") + 1])
            profiles.lifecycle.write_atomic(output, json.dumps(self.registry).encode())
        if "get" in command and "secret" in command:
            data = {key: base64.b64encode(value.encode()).decode() for key, value in self.auth.items()}
            return SimpleNamespace(stdout=json.dumps({"data": data,
                "metadata": {"resourceVersion": str(self.secret_version)}}), returncode=0)
        if "get" in command and "deployment" in command:
            return SimpleNamespace(stdout='{"metadata":{"name":"operator-orchestration-service"}}', returncode=0)
        if "patch" in command:
            value = json.loads(kwargs["input_value"])
            if "secret" in command:
                if any(self.auth.get(key) != item for key, item in value["stringData"].items()):
                    self.secret_version += 1
                self.auth.update(value["stringData"])
                return SimpleNamespace(stdout=json.dumps({"metadata": {
                    "resourceVersion": str(self.secret_version)}}), returncode=0)
            else:
                self.template_annotations.update(value["spec"]["template"].get("metadata", {}).get("annotations", {}))
                self.settings.update({entry["name"]: entry["value"]
                    for entry in value["spec"]["template"]["spec"]["containers"][0]["env"]})
                signature = json.dumps({"annotations": self.template_annotations,
                                        "settings": self.settings}, sort_keys=True)
                if signature != self.template_signature:
                    self.template_signature = signature
                    self.pod_settings = copy.deepcopy(self.settings)
                    self.pod_auth = copy.deepcopy(self.auth)
                    self.rollouts += 1
        if "node" in command:
            value = {"enabled": self.pod_settings.get("OOS_MODEL_PROFILE_REQUEST_ENABLED") == "true",
                     "bindings": json.loads(self.pod_settings.get("OOS_MODEL_PROFILE_REQUEST_CALLER_OPERATOR_BINDINGS_JSON", "{}")),
                     "fulfillers": self.pod_settings.get("OOS_MODEL_PROFILE_FULFILLMENT_CALLER_IDS", "").split(","),
                     "authenticated": profiles.FULFILLER in self.pod_auth["CALLER_ALLOWED_IDS"].split(",") and
                         profiles.FULFILLER in json.loads(self.pod_auth["CALLER_AUTH_SECRETS_JSON"]),
                     "state_root": self.pod_settings.get("OOS_MODEL_PROFILE_REQUEST_STATE_ROOT")}
            return SimpleNamespace(stdout=json.dumps(value), returncode=0)
        return SimpleNamespace(stdout="{}", returncode=0)

    def prepare(self):
        profiles.prepare(self.policy, repo_root=self.root, state_root=self.root, run=self.owner_run)

    def bind(self):
        profiles.bind_oos(self.policy, state_root=self.root, namespace="synthetic-namespace",
                          operator_id="operator:synthetic", run=self.owner_run)

    def test_first_use_publishes_current_registry_without_any_transaction(self):
        self.prepare()
        root, projection, history, credential = profiles.paths(self.root)
        self.assertEqual(self.registry, json.loads(projection.read_text()))
        self.assertEqual([], list(history.iterdir()))
        self.assertEqual(0o700, root.stat().st_mode & 0o777)
        self.assertEqual(0o700, history.stat().st_mode & 0o777)
        self.assertEqual(0o600, credential.stat().st_mode & 0o777)
        self.assertEqual(0o600, projection.stat().st_mode & 0o777)
        self.assertEqual({"GOVERNANCE_CONSOLE_MODEL_PROFILE_SOURCE_PROJECTION_PATH",
                          "GOVERNANCE_CONSOLE_MODEL_PROFILE_REQUEST_HISTORY_ROOT"},
                         set(profiles.activation_environment(self.root)))

    def test_existing_callers_survive_and_fulfiller_never_becomes_operator(self):
        self.prepare()
        old = json.loads(self.auth["CALLER_AUTH_SECRETS_JSON"])
        self.bind()
        secrets = json.loads(self.auth["CALLER_AUTH_SECRETS_JSON"])
        for key, value in old.items():
            self.assertEqual(value, secrets[key])
        self.assertNotIn(secrets[profiles.FULFILLER], old.values())
        self.assertEqual({profiles.CALLER: "operator:synthetic"},
                         json.loads(self.settings["OOS_MODEL_PROFILE_REQUEST_CALLER_OPERATOR_BINDINGS_JSON"]))
        self.assertEqual(profiles.FULFILLER, self.settings["OOS_MODEL_PROFILE_FULFILLMENT_CALLER_IDS"])
        self.bind()
        self.assertEqual(1, self.auth["CALLER_ALLOWED_IDS"].split(",").count(profiles.FULFILLER))
        value = profiles.status(self.policy, state_root=self.root, namespace="synthetic-namespace",
                                operator_id="operator:synthetic", run=self.owner_run)
        self.assertFalse(value["transaction_required_for_registry"])
        self.assertTrue(value["distinct_fulfiller_bound"])

    def test_pending_acceptance_and_unsafe_credentials_have_no_owner_effect(self):
        self.policy["security"]["status"] = "pending"
        with self.assertRaises(profiles.ProfileCompositionError):
            self.prepare()
        self.assertEqual([], self.calls)
        self.assertFalse((self.root / "private").exists())
        self.policy["security"]["status"] = "accepted"
        self.prepare()
        credential = profiles.paths(self.root)[3]
        credential.chmod(0o644)
        self.calls.clear()
        with self.assertRaises(profiles.ProfileCompositionError):
            self.bind()
        self.assertEqual([], self.calls)

    def test_resumed_base_composition_reloads_the_restored_secret(self):
        self.prepare()
        self.bind()
        first_template = self.template_signature
        # A later base up replaces the shared Secret and starts a process from
        # it, while kubectl apply retains the custom binding annotation/env.
        self.auth = copy.deepcopy(self.base_auth)
        self.secret_version += 1
        self.pod_auth = copy.deepcopy(self.base_auth)
        self.bind()
        value = profiles.status(self.policy, state_root=self.root,
            namespace="synthetic-namespace", operator_id="operator:synthetic", run=self.owner_run)
        self.assertTrue(value["distinct_fulfiller_bound"])
        self.assertNotEqual(first_template, self.template_signature)
        self.assertEqual(2, self.rollouts)

    def test_unchanged_binding_keeps_the_already_consuming_process(self):
        self.prepare()
        self.bind()
        first_template = self.template_signature
        self.bind()
        self.assertEqual(first_template, self.template_signature)
        self.assertEqual(1, self.rollouts)
        value = profiles.status(self.policy, state_root=self.root,
            namespace="synthetic-namespace", operator_id="operator:synthetic", run=self.owner_run)
        self.assertTrue(value["distinct_fulfiller_bound"])

    def test_unconfirmed_publication_cannot_attest_a_consumer_rollout(self):
        self.prepare()
        def unconfirmed_run(command, **kwargs):
            result = self.owner_run(command, **kwargs)
            if "patch" in command and "secret" in command:
                return SimpleNamespace(stdout='{"metadata": {}}', returncode=0)
            return result
        with self.assertRaisesRegex(profiles.ProfileCompositionError, "credential version is unavailable"):
            profiles.bind_oos(self.policy, state_root=self.root,
                namespace="synthetic-namespace", operator_id="operator:synthetic", run=unconfirmed_run)
        self.assertEqual(0, self.rollouts)
        self.assertNotIn(profiles.FULFILLER, self.pod_auth["CALLER_ALLOWED_IDS"].split(","))

    def test_missing_authenticated_console_cannot_grant_fulfillment(self):
        self.prepare()
        self.auth["CALLER_ALLOWED_IDS"] = "existing-owner"
        with self.assertRaises(profiles.ProfileCompositionError):
            self.bind()
        self.assertFalse(any("patch" in command for command, _ in self.calls))

    def test_unrelated_existing_auth_aliases_do_not_invent_an_additional_separation_rule(self):
        self.prepare()
        callers = json.loads(self.auth["CALLER_AUTH_SECRETS_JSON"])
        callers["existing-alias"] = callers["existing-owner"]
        self.auth["CALLER_AUTH_SECRETS_JSON"] = json.dumps(callers)
        self.auth["CALLER_ALLOWED_IDS"] += ",existing-alias"
        self.bind()
        actual = json.loads(self.auth["CALLER_AUTH_SECRETS_JSON"])
        self.assertEqual(actual["existing-owner"], actual["existing-alias"])
        self.assertNotEqual(actual[profiles.CALLER], actual[profiles.FULFILLER])
        self.assertNotIn(actual[profiles.FULFILLER], callers.values())

    def test_rollback_withdraws_only_new_runtime_grants_and_preserves_history(self):
        self.prepare()
        self.bind()
        history = profiles.paths(self.root)[2] / "retained-owner-evidence.json"
        history.write_text("retained evidence")
        profiles.disable(self.policy, namespace="synthetic-namespace", run=self.owner_run)
        self.assertEqual("false", self.settings["OOS_MODEL_PROFILE_REQUEST_ENABLED"])
        self.assertNotIn(profiles.FULFILLER, json.loads(self.auth["CALLER_AUTH_SECRETS_JSON"]))
        self.assertIn(profiles.CALLER, self.auth["CALLER_ALLOWED_IDS"])
        self.assertEqual("retained evidence", history.read_text())


if __name__ == "__main__":
    unittest.main()
