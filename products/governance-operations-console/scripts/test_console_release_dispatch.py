"""Exercise original-request recovery at the GitHub transport boundary; no live writes."""
from contextlib import contextmanager
import copy
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import yaml

import console_release_dispatch as release
import console_release_identity as identity
import platform_operation_provider as provider

sys.path.insert(0, str(release.ROOT / "products/openclaw/scripts"))
import console_release_workflow as workflow

PE = "a" * 40
WG = "b" * 40
DECISION = "sha256:" + "c" * 64
CREDS = {"token": "dedicated-test-only-token", "bot_id": 9001}


def reader(workspace, owner, path):
    if owner == "workspace-governance":
        return {"products": {"openclaw": {"posture": "active", "stage_supported": True, "governed_prod_promotion": True}}}, WG
    return yaml.safe_load((release.ROOT / path).read_text()), PE


def command(kind="runtime"):
    values = {"state": "traffic-stopped", "reason": "Operator test", "incident_ref": "", "operation_note": ""}
    if kind == "promotion":
        values = {"promotion_note": "Test", "suspend_stage_environment": "true"}
    if kind == "readiness":
        values = {"verification_evidence_ref": "evidence:test", "verification_note": "", "approval_note": ""}
        required = reader(None, "platform-engineering", "environments/stage/release-candidate.yaml")[0]["candidate"]["requiredChecks"]
        values.update({"check:" + name: "passed" for name in required})
    result = {"schema_version": 1, "command_id": "console-command:test", "idempotency_key": "console-idempotency:test", "correlation_id": "console-correlation:test", "causation_id": None,
              "actor_ref": "operator:mfshaf7", "subject": {"kind": "product-runtime-lifecycle" if kind == "runtime" else "product-release", "ref": "product:openclaw", "expected_source_version": f"products:{WG}:{PE}"},
              "capability_id": "release.openclaw." + kind, "action": release.SPECS[kind]["action"], "input": {"workflow_id": kind, "values": values}, "requested_at": "2026-11-02T00:00:00Z"}
    result["intent_digest"] = release.digest(result)
    result["approval"] = {"decision": "approved", "operator_id": result["actor_ref"], "decision_ref": "console-approval:test", "decided_at": result["requested_at"], "intent_digest": result["intent_digest"]}
    return result


class GitHub:
    def __init__(self):
        self.calls = []
        self.run = None
        self.pull = None
        self.lost_ack = False
        self.branch = False
        self.main = PE
        self.environment = {"protection_rules": [{"type": "required_reviewers", "reviewers": [{"reviewer": {"id": 244414185}}]}], "deployment_branch_policy": {"protected_branches": True}}
        self.documents = {}

    def call(self, method, path, *, bearer, body=None):
        self.calls.append((method, path, copy.deepcopy(body)))
        assert bearer == CREDS["token"]
        route = path.removeprefix(release.PREFIX)
        if method == "POST" and route.endswith("/dispatches"):
            intent = json.loads(body["inputs"]["console_intent"])
            self.run = {"id": 42, "run_attempt": 1, "event": "workflow_dispatch", "head_sha": PE, "repository": {"id": release.REPOSITORY_ID}, "actor": {"id": CREDS["bot_id"]}, "path": ".github/workflows/" + release.SPECS[intent["workflow_id"]]["filename"], "display_title": "Console release " + body["inputs"]["console_request_id"], "status": "waiting", "conclusion": None}
            if self.lost_ack:
                raise release.IdentityError("transport lost after accepted write")
            return {"workflow_run_id": 42}
        if method == "POST" and route.endswith("/cancel"):
            self.run.update(status="completed", conclusion="cancelled")
            return {}
        if route == "":
            return {"id": release.REPOSITORY_ID, "full_name": release.REPOSITORY}
        if route.startswith("/environments/"):
            return self.environment
        if route == "/git/ref/heads/main":
            return {"object": {"sha": self.main}}
        if route.startswith("/git/ref/heads/"):
            if self.branch:
                return {"object": {"sha": "d" * 40}}
            raise release.ProviderHttpError(404)
        if route == "/actions/runs/42":
            return self.run
        if "/runs?" in route:
            return {"workflow_runs": [self.run] if self.run else []}
        if route.startswith("/pulls?"):
            return [self.pull] if self.pull else []
        if route.startswith("/compare/"):
            return {"merge_base_commit": {"sha": "e" * 40}}
        if route.startswith("/contents/"):
            import base64
            path = route.split("?", 1)[0].removeprefix("/contents/")
            doc = self.documents.get(path, reader(None, "platform-engineering", path)[0])
            return {"encoding": "base64", "content": base64.b64encode(yaml.safe_dump(doc).encode()).decode()}
        raise AssertionError((method, route))


class NativeDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.policy = {"workspace_root": str(release.ROOT.parent), "runtime_state_root": self.temp.name, "platform_operation_provider": {"operator_id": "operator:mfshaf7"}, "security": {"decision_digest": DECISION},
                       "governed_release": {"permitted": True, "security_accepted": True, "security_review_ref": "docs/reviews/components/2026-11-02-console-native-governed-release.md", "security_decision_digest": DECISION}}
        self.store = provider.OperationStore(Path(self.temp.name) / "provider")
        self.github = GitHub()
        self.dispatcher = release.ReleaseDispatcher(self.policy, self.store, reader=reader, client=self.github, credential_reader=lambda _: CREDS)
        self.identity_patch = patch.object(identity, "credential", return_value=CREDS)
        self.identity_patch.start()
        self.addCleanup(self.identity_patch.stop)

    def record(self, kind="runtime"):
        cmd = command(kind)
        record = provider.new_record(cmd, cmd["subject"]["expected_source_version"])
        record["release"] = self.dispatcher.prepare(cmd)
        self.store.write(record)
        return record

    def dispatch(self, record):
        return self.dispatcher.dispatch(record, provider.event, provider.terminal_receipt)

    def refresh(self, record):
        return self.dispatcher.reconcile(record, provider.event, provider.terminal_receipt)

    def test_native_fields_derive_from_owner_catalog_without_passing_defaults(self):
        fields = release.action_definition(self.policy, "readiness", reader=reader)["fields"]
        checks = [field for field in fields if field["id"].startswith("check:")]
        self.assertTrue(checks)
        self.assertTrue(all(field["default_value"] == "" for field in checks))

    def test_acknowledged_dispatch_waits_for_existing_human_gate(self):
        record = self.dispatch(self.record())
        self.assertEqual((record["state"], record["release"]["phase"], record["receipt"]), ("queued", "awaiting-approval", None))
        self.assertFalse(record["retryable"])
        count = len(record["events"])
        self.refresh(record)
        self.assertEqual(len(record["events"]), count)

    def test_lost_ack_is_recovered_from_original_run_without_second_post(self):
        self.github.lost_ack = True
        record = self.dispatch(self.record())
        cold = self.store.read(record["command"]["command_id"])
        self.refresh(cold)
        self.assertEqual(cold["release"]["run_id"], 42)
        self.assertEqual(len([call for call in self.github.calls if call[0] == "POST"]), 1)

    def test_missing_original_run_is_explicit_uncertainty_and_never_redispatched(self):
        record = self.record()
        record["release"].update(phase="dispatching", dispatch_started_at=release.now())
        self.refresh(record)
        self.refresh(self.store.read(record["command"]["command_id"]))
        self.assertEqual(record["state"], "blocked")
        self.assertFalse(any(method == "POST" for method, _, _ in self.github.calls))

    def service(self):
        with patch.object(provider, "require_security_activation"):
            service = provider.ProviderService(self.policy, Path(self.temp.name) / "policy.yaml", self.store, "platform:test")
        service.release_dispatcher = self.dispatcher
        return service

    def test_provider_replay_and_cold_get_do_not_rely_on_current_catalog(self):
        service = self.service()
        with patch.object(provider, "activation_is_current", return_value=True):
            status, result = service.submit({"command": command()})
        self.assertEqual(status, 202)
        self.policy["governed_release"]["permitted"] = False
        self.assertEqual(self.service().read(command()["command_id"])["release_workflow"]["run_id"], 42)
        status, replay = service.submit({"command": command()})
        self.assertEqual(status, 200)
        self.assertEqual(replay["operation_id"], result["operation_id"])
        self.assertEqual(len([c for c in self.github.calls if c[0] == "POST"]), 1)

    def test_credential_outage_after_catalog_retains_prepared_request_for_recovery(self):
        service = self.service()
        with patch.object(provider, "activation_is_current", return_value=True), patch.object(identity, "credential", side_effect=identity.IdentityError("expired")):
            _, result = service.submit({"command": command()})
        self.assertEqual(result["state"], "blocked")
        self.assertEqual(result["release_workflow"]["phase"], "prepared")
        self.assertFalse(any(c[0] == "POST" for c in self.github.calls))
        with patch.object(provider, "activation_is_current", return_value=True):
            recovered = self.service().read(command()["command_id"])
        self.assertEqual(recovered["release_workflow"]["run_id"], 42)

    def test_stale_admission_is_durably_rejected_with_no_effect_receipt(self):
        service = self.service()
        with patch.object(provider, "activation_is_current", return_value=False):
            _, result = service.submit({"command": command()})
        self.assertEqual(result["state"], "failed")
        self.assertEqual(result["receipt"]["effect"], "none")
        self.assertEqual(self.service().read(command()["command_id"]), result)
        self.assertEqual(self.github.calls, [])

    def test_dispatch_method_cannot_send_an_already_marked_record_again(self):
        record = self.dispatch(self.record())
        self.dispatch(record)
        self.assertEqual(len([c for c in self.github.calls if c[0] == "POST"]), 1)

    def test_retained_write_ahead_marker_prevents_dispatch_even_if_phase_is_reset(self):
        record=self.dispatch(self.record());record["release"]["phase"]="prepared"
        self.dispatch(record)
        self.assertEqual(len([c for c in self.github.calls if c[0] == "POST"]),1)

    def test_definitive_dispatch_denial_has_no_effect_receipt(self):
        original=self.github.call
        def denied(method,path,**kwargs):
            if method=="POST"and path.endswith("/dispatches"):raise release.ProviderHttpError(403)
            return original(method,path,**kwargs)
        with patch.object(self.github,"call",side_effect=denied):result=self.dispatch(self.record())
        self.assertEqual(result["state"],"failed");self.assertEqual(result["receipt"]["effect"],"none")

    def test_corrupt_prepared_command_cannot_dispatch_after_process_restart(self):
        record=self.record();record["command"]["input"]["values"]["reason"]="Corrupted"
        with self.assertRaises(release.ReleaseError):self.dispatch(record)
        self.assertEqual(self.github.calls,[])

    def test_stale_main_or_missing_human_approval_prevents_dispatch(self):
        self.github.main = "f" * 40
        with self.assertRaises(release.ReleaseError):
            self.dispatch(self.record())
        self.github.main = PE
        self.github.environment["protection_rules"] = []
        with self.assertRaises(release.ReleaseError):
            self.dispatch(self.record())
        self.assertFalse(any(method == "POST" for method, _, _ in self.github.calls))

    def test_wrong_run_identity_cannot_be_claimed_as_original_progress(self):
        record = self.dispatch(self.record())
        self.github.run["actor"] = {"id": 777}
        with self.assertRaises(release.ReleaseError):
            self.refresh(record)

    def test_workflow_success_and_open_pr_are_not_terminal_release_success(self):
        record = self.dispatch(self.record())
        self.github.run.update(status="completed", conclusion="success")
        self.github.pull = {"number": 55, "state": "open", "merged_at": None, "head": {"ref": "prod/openclaw-traffic-stopped-42", "sha": "d" * 40, "repo": {"id": release.REPOSITORY_ID}}, "base": {"ref": "main", "repo": {"id": release.REPOSITORY_ID}}}
        self.refresh(record)
        self.assertEqual((record["state"], record["release"]["phase"], record["receipt"]), ("running", "awaiting-review", None))
        # Squash merge is verified by merge commit ancestry, not head ancestry.
        self.github.pull.update(merged_at="2026-11-02T01:00:00Z", merge_commit_sha="e" * 40)
        self.github.documents["environments/prod/openclaw-lifecycle.yaml"] = {"state": "traffic-stopped", "reason": "Operator test", "incidentRef": None, "changedBy": "mfshaf7"}
        lifecycle=self.github.documents["environments/prod/openclaw-lifecycle.yaml"]
        self.github.documents["environments/prod/argocd/kustomization.yaml"]={"resources":release.expected_prod_resources("traffic-stopped")}
        self.github.documents["environments/prod/argocd/openclaw-prod-lifecycle-configmap.yaml"]=release.lifecycle_configmap_payload(lifecycle)
        self.github.documents["environments/prod/verification.yaml"]={"status":release.prod_verification_status_for_state("traffic-stopped")}
        self.refresh(record)
        self.assertEqual(record["state"], "succeeded")
        self.assertTrue(record["receipt"]["release_workflow"]["desired_state_verified"])
        previous = copy.deepcopy(record)
        self.github.run = None
        self.refresh(record)
        self.assertEqual(record, previous)  # Terminal receipt is immutable.

    def test_failed_after_push_keeps_original_branch_recoverable(self):
        record = self.dispatch(self.record())
        self.github.run.update(status="completed", conclusion="failure")
        self.github.branch = True
        self.refresh(record)
        self.assertEqual(record["state"], "blocked")
        self.assertEqual(record["release"]["phase"], "awaiting-review")
        self.assertIsNone(record["receipt"])

    def test_readiness_readback_uses_complete_owner_candidate_and_verification_refs(self):
        record=self.record("readiness"); candidate_doc=reader(None,"platform-engineering","environments/stage/release-candidate.yaml")[0]
        values=record["release"]["values"]
        verification={"status":"verified","verifiedAt":"2026-11-02T03:00:00Z","verifiedBy":"mfshaf7","candidateRef":release.candidate_ref_for(candidate_doc),"evidenceRef":values["verification_evidence_ref"],"checks":[{"id":key[6:],"status":value}for key,value in values.items()if key.startswith("check:")]}
        readiness={"status":"approved","approvedBy":"mfshaf7","approvedCandidate":candidate_doc["candidate"],"candidateRef":release.candidate_ref_for(candidate_doc),"verificationRef":release.verification_ref_for(verification)}
        self.github.documents.update({"environments/stage/verification.yaml":verification,"environments/stage/promotion-readiness.yaml":readiness})
        self.assertTrue(self.dispatcher._desired(record,"e"*40))
        verification["candidateRef"]["imageDigest"]="sha256:"+"f"*64
        self.assertFalse(self.dispatcher._desired(record,"e"*40))

    def test_promotion_readback_respects_requested_stage_posture(self):
        record=self.record("promotion")
        self.github.documents["environments/prod/versions.yaml"]=reader(None,"platform-engineering","environments/stage/versions.yaml")[0]
        self.github.documents["environments/stage/argocd/kustomization.yaml"]={"resources":["suspend-sentinel-configmap.yaml"]}
        self.assertTrue(self.dispatcher._desired(record,"e"*40))
        record["release"]["values"]["suspend_stage_environment"]="false"
        self.assertFalse(self.dispatcher._desired(record,"e"*40))
        self.github.documents["environments/stage/argocd/kustomization.yaml"]={"resources":["openclaw-gateway-app.yaml"]}
        self.github.documents["environments/stage/verification.yaml"]={"status":"pending"}
        self.github.documents["environments/stage/promotion-readiness.yaml"]={"status":"pending"}
        self.assertTrue(self.dispatcher._desired(record,"e"*40))

    def test_changed_journal_values_are_rejected_before_any_provider_read(self):
        record = self.record()
        record["release"]["values"]["reason"] = "Tampered"
        with self.assertRaises(release.ReleaseError):
            self.refresh(record)
        self.assertEqual(self.github.calls, [])

    def test_cancel_targets_only_original_in_flight_run_and_retains_effect_uncertainty(self):
        record = self.dispatch(self.record())
        control = {"idempotency_key": "control:test"}
        self.dispatcher.cancel(record, control, provider.event, provider.terminal_receipt)
        self.assertEqual(record["state"], "cancelled")
        self.assertEqual(record["receipt"]["effect"], "partial")

    def test_guard_binds_app_source_workflow_and_all_inputs_as_data(self):
        record = self.dispatch(self.record())
        body = next(body for method, path, body in self.github.calls if method == "POST" and path.endswith("/dispatches"))
        env = {"CONSOLE_REQUEST_ID": body["inputs"]["console_request_id"], "CONSOLE_INTENT": body["inputs"]["console_intent"], "GITHUB_REPOSITORY": release.REPOSITORY, "GITHUB_REPOSITORY_ID": str(release.REPOSITORY_ID), "GITHUB_ACTOR": "mfshaf7-governed-releases[bot]", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/main", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_WORKFLOW_REF": release.REPOSITORY + "/.github/workflows/manage-prod-environment.yaml@refs/heads/main", "GITHUB_SHA": PE}
        env.update({"RELEASE_" + key.upper(): value for key, value in body["inputs"].items() if key not in {"console_request_id", "console_intent"}})
        self.assertEqual(workflow.guard("runtime", env)["command_id"], record["command"]["command_id"])
        for key, value in [("GITHUB_ACTOR", "mfshaf7"), ("GITHUB_SHA", "f" * 40), ("GITHUB_RUN_ATTEMPT", "2"), ("RELEASE_REASON", "$(touch /tmp/untrusted)")]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                workflow.guard("runtime", {**env, key: value})
        self.assertIsNone(workflow.guard("runtime", {"GITHUB_ACTOR": "mfshaf7"}))
        with self.assertRaises(ValueError):
            workflow.guard("runtime", {"GITHUB_ACTOR": "mfshaf7-governed-releases[bot]"})

    def test_all_workflows_keep_protection_and_avoid_input_shell_interpolation(self):
        for kind, spec in release.SPECS.items():
            doc = yaml.safe_load((release.ROOT / ".github/workflows" / spec["filename"]).read_text())
            job = next(iter(doc["jobs"].values()))
            self.assertIn(job["environment"], [spec["environment"], "${{ inputs.target_environment }}"])
            self.assertTrue(any(" guard " + kind in step.get("run", "") for step in job["steps"]))
            for step in job["steps"]:
                self.assertNotIn("${{ inputs.", step.get("run", ""))
                self.assertNotIn("--force", step.get("run", ""))


class NativeIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.policy = {"runtime_state_root": self.temp.name, "security": {"decision_digest": DECISION}, "governed_release": {"permitted": True, "security_accepted": True, "security_decision_digest": DECISION, "security_review_ref":"docs/reviews/components/2026-11-02-console-native-governed-release.md"}}
        self.revoked = []
        test = self

        class App:
            permissions = copy.deepcopy(identity.PERMISSIONS)
            repository_id = release.REPOSITORY_ID
            issued = 0
            def authenticated_app(self, jwt):
                return {"id": 12, "slug": "mfshaf7-governed-releases", "owner": {"id": 244414185, "login": "mfshaf7"}}
            def installation(self, installation_id, jwt):
                return {"id": 34, "app_id": 12, "account": {"id":244414185,"login":"mfshaf7"}, "suspended_at": None, "repository_selection": "selected", "permissions": self.permissions, "events": []}
            def issue_token(self, installation_id, jwt, repositories, permissions):
                from repository_provider_identity import IssuedToken
                self.issued += 1
                return IssuedToken("synthetic-private-installation-token-" + str(self.issued), (datetime.now(timezone.utc) + timedelta(minutes=59)).isoformat(), (), permissions)
            def accessible_repositories(self, token):
                return ({"full_name":release.REPOSITORY,"id":self.repository_id},)
            def call(self, method, route, *, bearer):
                return {"id": 9001, "login": "mfshaf7-governed-releases[bot]"}
            def revoke_token(self, token):
                test.revoked.append(token)
        self.client = App()
        self.jwt = patch.object(identity, "create_app_jwt", return_value="synthetic-jwt")
        self.jwt.start(); self.addCleanup(self.jwt.stop)

    @contextmanager
    def key(self, contract):
        yield Path(self.temp.name) / "unused-synthetic-key"

    def commission(self):
        return identity.commission(self.policy, 12, 34, client=self.client, key_context=self.key)

    def test_commission_proves_private_scope_and_never_returns_token(self):
        receipt = self.commission()
        self.assertNotIn("token", receipt)
        bundle = identity.credential(self.policy)
        self.assertEqual(bundle["permissions"], identity.PERMISSIONS)
        self.assertEqual(identity.bundle_path(self.policy).stat().st_mode & 0o777, 0o600)
        self.assertNotIn("synthetic-private", json.dumps(receipt))

    def test_broader_permissions_or_other_numeric_repository_are_rejected(self):
        self.client.permissions = {**identity.PERMISSIONS, "administration":"write"}
        with self.assertRaises(identity.IdentityError): self.commission()
        self.client.permissions = copy.deepcopy(identity.PERMISSIONS)
        self.client.repository_id = 77
        with self.assertRaises(identity.IdentityError): self.commission()
        self.assertFalse(identity.bundle_path(self.policy).exists())
        self.assertEqual(len(self.revoked), 1)  # Rejected issued token is retired.

    def test_rotation_retires_previous_token_before_replacement(self):
        self.commission(); previous = identity.credential(self.policy)["token"]
        self.commission()
        self.assertEqual(self.revoked[-1], previous)
        self.assertEqual(self.revoked.count(previous), 1)
        self.assertNotEqual(identity.credential(self.policy)["token"], previous)

    def test_uncertain_revocation_cannot_issue_overlapping_replacement(self):
        self.commission(); previous = identity.credential(self.policy)["token"]
        revoke=self.client.revoke_token
        def uncertain(token):
            if token==previous:raise identity.IdentityError("network unavailable")
            revoke(token)
        with patch.object(self.client, "revoke_token", side_effect=uncertain):
            with self.assertRaises(identity.IdentityError): self.commission()
        self.assertEqual(identity.credential(self.policy)["token"], previous)

    def test_expiry_permission_and_security_changes_withhold_credential(self):
        self.commission()
        value = identity.private_json(identity.bundle_path(self.policy))
        for edit in [lambda v:v.update(expires_at=(datetime.now(timezone.utc)-timedelta(seconds=1)).isoformat()), lambda v:v.update(permissions={"actions":"write"}), lambda v:v.update(security_digest="sha256:"+"d"*64)]:
            changed = copy.deepcopy(value); edit(changed); identity.atomic_json(identity.bundle_path(self.policy), changed)
            with self.assertRaises(identity.IdentityError): identity.credential(self.policy)
        identity.atomic_json(identity.bundle_path(self.policy), value)
        identity.bundle_path(self.policy).chmod(0o644)
        with self.assertRaises(identity.IdentityError): identity.credential(self.policy)

    def test_unselected_connection_is_not_a_core_startup_dependency(self):
        self.policy["governed_release"]["permitted"] = False
        self.assertEqual(identity.maintain(self.policy), {"state":"not-selected"})
        self.assertFalse(identity.bundle_path(self.policy).exists())

    def test_native_authority_derives_from_existing_exact_composition_without_digest_pin(self):
        policy={"governed_release":{"permitted":True,"security_review_ref":"docs/reviews/components/2026-11-02-console-native-governed-release.md"}}
        decision={"status":"accepted","gate_id":"gate:existing-core","reviewed_revisions":{"platform-engineering":PE,"operator-orchestration-service":WG},"reviewed_trees":{"platform-engineering":"d"*40}}
        header={"native_release_activation":{"status":"accepted","gate_id":decision["gate_id"],"reviewed_revisions":decision["reviewed_revisions"],"reviewed_platform_tree":"d"*40}}
        text=lambda value:"---\n"+yaml.safe_dump(value)+"---\nSource review\n"
        resolved=identity.resolve_selection(policy,decision,text(header))
        self.assertTrue(resolved["security_accepted"])
        self.assertEqual(resolved["security_decision_digest"],identity.digest(decision))
        self.assertNotIn("security_decision_digest",policy["governed_release"])
        for change in [lambda h:h["native_release_activation"].update(status="pending"),lambda h:h["native_release_activation"].update(reviewed_platform_tree="e"*40),lambda h:h["native_release_activation"]["reviewed_revisions"].update({"platform-engineering":"f"*40})]:
            altered=copy.deepcopy(header);change(altered);self.assertFalse(identity.resolve_selection(policy,decision,text(altered))["security_accepted"])
        self.assertFalse(identity.resolve_selection(policy,decision,"review missing") ["security_accepted"])


if __name__ == "__main__":
    unittest.main()
