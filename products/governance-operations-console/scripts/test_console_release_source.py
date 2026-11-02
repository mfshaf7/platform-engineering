"""Repeat-use owner-data proof. All GitHub state is synthetic and isolated."""
import base64
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, unquote
import yaml

import console_release_source as source
import console_release_dispatch as release
import console_release_identity as identity
import platform_operation_provider as provider
from test_console_release_dispatch import GitHub, CREDS, PE, WG, DECISION, command


def blob(raw):
    raw = raw.encode()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


class OwnerGitHub(GitHub):
    def __init__(self):
        super().__init__()
        paths = source.READ_PATHS | source.MUTABLE_RECORDS
        documents = {path: (release.ROOT / path).read_text() for path in paths}
        lifecycle = yaml.safe_load(documents["environments/prod/openclaw-lifecycle.yaml"])
        lifecycle.update(state="suspended",reason="isolated source fixture",changedBy="mfshaf7",incidentRef=None)
        documents["environments/prod/openclaw-lifecycle.yaml"] = yaml.safe_dump(lifecycle)
        documents["environments/prod/argocd/kustomization.yaml"] = yaml.safe_dump({"resources":release.expected_prod_resources("suspended")})
        documents["environments/prod/argocd/openclaw-prod-lifecycle-configmap.yaml"] = yaml.safe_dump(release.lifecycle_configmap_payload(lifecycle))
        documents["scripts/reviewed-owner-code.py"] = "# accepted owner workflow code\n"
        self.versions = {PE: documents}
        self.runs, self.pulls = {}, {}
        self.offline, self.bad_blob, self.truncated, self.bad_lineage = False, False, False, False

    def entries(self, ref):
        return {path: ("100644", "blob", blob(raw)) for path, raw in self.versions[ref].items()}

    def local_reader(self, workspace, owner, path):
        if owner == "workspace-governance":
            return {"products":{"openclaw":{"posture":"active","maturity":"fully-governed","platform_owner":"platform-engineering","security_owner":"security-architecture","highest_real_endpoint":"governed-prod","stage_supported":True,"governed_prod_promotion":True}}}, WG
        return yaml.safe_load(self.versions[PE][path]), PE

    def call(self, method, path, *, bearer, body=None):
        request_path = path
        if self.offline:
            raise identity.IdentityError("Synthetic offline transport")
        route = path.removeprefix(release.PREFIX)
        result = None
        handled = True
        if route.startswith("/git/commits/"):
            ref = route.split("/")[-1]
            result = {"sha": ref, "tree": {"sha": ref}}
        elif route.startswith("/git/trees/"):
            ref = route.split("/")[-1].split("?")[0]
            result = {"sha": ref, "truncated": self.truncated, "tree": [{"path": path, "mode": mode, "type": kind, "sha": sha} for path, (mode, kind, sha) in self.entries(ref).items()]}
        elif route.startswith("/contents/"):
            path = route.split("?", 1)[0].removeprefix("/contents/")
            ref = parse_qs(route.split("?", 1)[1])["ref"][0]
            raw = self.versions[self.main if ref == "main" else ref][path]
            result = {"type": "file", "encoding": "base64", "content": base64.b64encode((raw + ("corrupt" if self.bad_blob else "")).encode()).decode()}
        elif route.startswith("/compare/"):
            pair = route.removeprefix("/compare/").split("?")[0]
            base, head = pair.split("...")
            result = {"merge_base_commit": {"sha": "f" * 40 if self.bad_lineage else base}, "status": "identical" if base == (self.main if head == "main" else head) else "ahead"}
        elif route.startswith("/actions/runs/"):
            result = self.runs[int(route.split("/")[-1])]
        elif route.startswith("/pulls?"):
            head = parse_qs(route.split("?", 1)[1])["head"][0].split(":", 1)[1]
            result = [self.pulls[head]] if head in self.pulls else []
        elif "/runs?" in route:
            result = {"workflow_runs": list(self.runs.values())}
        else:
            handled = False
        if handled:
            self.calls.append((method, request_path, copy.deepcopy(body)))
            return result
        result = super().call(method, path, bearer=bearer, body=body)
        if method == "POST" and route.endswith("/dispatches"):
            number = 42 + len(self.runs)
            intent = json.loads(body["inputs"]["console_intent"])
            self.run.update(id=number, head_sha=intent["platform_revision"])
            self.runs[number] = self.run
            return {"workflow_run_id": number}
        return result

    def advance(self, edits):
        documents = dict(self.versions[self.main])
        documents.update(edits)
        ref = hashlib.sha1(json.dumps(documents, sort_keys=True).encode()).hexdigest()
        self.versions[ref] = documents
        self.main = ref
        return ref

    def merge(self, record):
        rel = record["release"]
        values, number = rel["values"], rel["run_id"]
        lifecycle = yaml.safe_load(self.versions[self.main]["environments/prod/openclaw-lifecycle.yaml"])
        lifecycle.update(state=values["state"], reason=values["reason"], changedBy="mfshaf7", incidentRef=values["incident_ref"] or None)
        if values["operation_note"]:
            lifecycle["note"] = values["operation_note"]
        verification = yaml.safe_load(self.versions[self.main]["environments/prod/verification.yaml"])
        verification.update(status=release.prod_verification_status_for_state(values["state"]), verifiedAt=None, verifiedBy=None, evidenceRef=None)
        edits = {"environments/prod/openclaw-lifecycle.yaml": yaml.safe_dump(lifecycle),
                 "environments/prod/argocd/kustomization.yaml": yaml.safe_dump({"resources": release.expected_prod_resources(values["state"])}),
                 "environments/prod/argocd/openclaw-prod-lifecycle-configmap.yaml": yaml.safe_dump(release.lifecycle_configmap_payload(lifecycle)),
                 "environments/prod/verification.yaml": yaml.safe_dump(verification)}
        ref = self.advance(edits)
        self.runs[number].update(status="completed", conclusion="success")
        branch = "prod/openclaw-" + values["state"] + "-" + str(number)
        self.pulls[branch] = {"number": number + 100, "state": "closed", "merged_at": "2026-11-02T04:00:00Z", "merge_commit_sha": ref,
                              "head": {"ref": branch, "sha": "d" * 40, "repo": {"id": release.REPOSITORY_ID}}, "base": {"ref": "main", "repo": {"id": release.REPOSITORY_ID}}}


class OwnerSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.policy = {"workspace_root": self.temp.name, "runtime_state_root": self.temp.name,
                       "security": {"platform_revision": PE, "decision_digest": DECISION},
                       "platform_operation_provider": {"operator_id": "operator:mfshaf7"},
                       "governed_release": {"permitted": True, "security_accepted": True, "security_review_ref": "docs/reviews/components/2026-11-02-console-native-governed-release.md", "security_decision_digest": DECISION}}
        self.github = OwnerGitHub()
        self.clock = 100
        self.source = self.fresh_source()
        self.identity = patch.object(identity, "credential", return_value=CREDS)
        self.identity.start(); self.addCleanup(self.identity.stop)

    def fresh_source(self):
        return source.ReleaseSource(self.policy, lambda method, route: self.github.call(method, release.PREFIX + route, bearer=CREDS["token"]),
                                    local_reader=self.github.local_reader, base_loader=lambda: self.github.entries(PE), monotonic=lambda: self.clock)

    def test_two_consecutive_native_changes_follow_owner_data_without_repinning_runtime(self):
        store = provider.OperationStore(Path(self.temp.name) / "operations")
        dispatcher = release.ReleaseDispatcher(self.policy, store, reader=self.github.local_reader, client=self.github, credential_reader=lambda _: CREDS, owner_source=self.source)
        for index, target in enumerate(["traffic-stopped", "live"]):
            with self.subTest(target=target):
                view = self.source.view(force=True, require_current=True)
                projection = __import__("console_governed_products").read_products(self.policy, reader=view.reader)
                owner = next(product for product in projection["products"] if product["product_id"] == "openclaw")
                self.assertEqual(owner["runtime"]["state"], "suspended" if index == 0 else "traffic-stopped")
                cmd = command()
                cmd.update(command_id=f"console-command:repeat-{index}", idempotency_key=f"idempotency:repeat-{index}", correlation_id=f"correlation:repeat-{index}")
                cmd["subject"]["expected_source_version"] = projection["source_version"]
                cmd["input"]["values"]["state"] = target
                cmd["intent_digest"] = release.digest({key: value for key, value in cmd.items() if key not in {"approval", "intent_digest"}})
                cmd["approval"].update(intent_digest=cmd["intent_digest"], decision_ref=f"approval:repeat-{index}")
                record = provider.new_record(cmd, projection["source_version"])
                record["release"] = dispatcher.prepare(cmd)
                dispatcher.dispatch(record, provider.event, provider.terminal_receipt)
                self.github.merge(record)
                dispatcher.reconcile(record, provider.event, provider.terminal_receipt)
                self.assertEqual(record["state"], "succeeded")
                self.assertEqual(self.policy["security"]["platform_revision"], PE)
        self.assertEqual(len([call for call in self.github.calls if call[0] == "POST" and call[1].endswith("/dispatches")]), 2)
        self.assertEqual(self.source.view(force=True).reader(None, "platform-engineering", "environments/prod/openclaw-lifecycle.yaml")[0]["state"], "live")

    def test_code_change_is_not_admitted_as_record_data(self):
        self.source.view(require_current=True)
        self.github.advance({"scripts/reviewed-owner-code.py": "# unreviewed code\n"})
        retained = self.source.view(force=True)
        self.assertEqual(retained.posture, "retained-owner-main")
        self.assertIn("code changed", retained.reason)
        self.clock += 4
        with self.assertRaises(source.SourceChanged):
            self.source.view(force=True, require_current=True)

    def test_cold_offline_reader_retains_exact_last_snapshot_without_offering_current_authority(self):
        observed = self.source.view(require_current=True)
        self.github.offline = True
        cold = self.fresh_source()
        retained = cold.view()
        self.assertEqual(retained.posture, "retained-owner-main")
        self.assertEqual(retained.reader(None, "platform-engineering", "environments/prod/openclaw-lifecycle.yaml"), observed.reader(None, "platform-engineering", "environments/prod/openclaw-lifecycle.yaml"))
        with self.assertRaises(source.ProfileReadError): cold.view(require_current=True)

    def test_incomplete_tree_foreign_lineage_and_blob_mismatch_never_claim_current_source(self):
        for flag in ["truncated", "bad_blob"]:
            with self.subTest(flag=flag):
                setattr(self.github, flag, True)
                with self.assertRaises(source.ProfileReadError): self.fresh_source().view(require_current=True)
                setattr(self.github, flag, False)
        self.github.advance({"environments/prod/verification.yaml": "status: pending\n"}); self.github.bad_lineage = True
        with self.assertRaises(source.SourceChanged): self.fresh_source().view(require_current=True)

    def test_corrupt_derived_cache_does_not_become_source_authority(self):
        self.source.view(require_current=True)
        value = json.loads(self.source.cache_path.read_text());value["source_revision"] = "f" * 40
        self.source.cache_path.write_text(json.dumps(value));self.github.offline=True
        self.assertEqual(self.fresh_source().view().posture,"accepted-snapshot")

    def test_warm_reads_share_head_and_document_proof_without_per_product_commands(self):
        self.source.view(require_current=True); count=len(self.github.calls)
        self.source.view(require_current=True)
        self.assertEqual(len(self.github.calls),count)

    def test_data_advance_fetches_only_changed_blobs_and_reuses_immutable_documents(self):
        self.source.view(require_current=True);count=len(self.github.calls)
        record=yaml.safe_load(self.github.versions[self.github.main]["environments/prod/openclaw-lifecycle.yaml"]);record["reason"]="New owner record"
        self.github.advance({"environments/prod/openclaw-lifecycle.yaml":yaml.safe_dump(record)})
        self.source.view(force=True,require_current=True)
        fetches=[path for method,path,_ in self.github.calls[count:]if "/contents/"in path]
        self.assertEqual(len(fetches),1)

    def test_base_tree_reader_uses_real_accepted_git_objects_without_checkout(self):
        policy=copy.deepcopy(self.policy)
        policy["security"]["platform_revision"]=subprocess.check_output(["git","-C",str(release.ROOT),"rev-parse","HEAD"],text=True).strip()
        actual=source.ReleaseSource(policy,lambda *_:self.fail("No network needed for base code proof"))
        entries=actual._git_entries()
        self.assertIn("Makefile",entries)
        self.assertIn("scripts/repository_provider_identity.py",entries)

    def test_slow_refresh_keeps_immutable_progress_instead_of_restarting_forever(self):
        def slow(method,route):
            result=self.github.call(method,release.PREFIX+route,bearer=CREDS["token"])
            self.clock+=2.5
            return result
        self.source.fetch=slow
        for attempt in range(12):
            view=self.source.view(force=True)
            if view.posture=="owner-main":break
            self.clock+=4
        self.assertEqual(view.posture,"owner-main")
        trees=[path for _,path,_ in self.github.calls if "/git/trees/"in path]
        self.assertEqual(len(trees),1)

    def test_inactive_readiness_inputs_do_not_remove_runtime_capability(self):
        raw=yaml.safe_load(self.github.versions[self.github.main]["environments/stage/release-candidate.yaml"])
        raw["candidate"]["requiredChecks"]=[]
        self.github.advance({"environments/stage/release-candidate.yaml":yaml.safe_dump(raw)})
        view=self.source.view(require_current=True)
        subjects=release.catalog_subjects(self.policy,reader=view.reader)
        capabilities={item["capability_id"]:item for subject in subjects for item in subject["capabilities"]}
        self.assertFalse(capabilities["release.openclaw.readiness"]["available"])
        self.assertTrue(capabilities["release.openclaw.runtime"]["available"])


if __name__ == "__main__":
    unittest.main()
