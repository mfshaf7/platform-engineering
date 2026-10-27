"""Real committed bundle bytes checked by the existing OOS role validator."""
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace

import console_durable_composition as durable


class DurableCompositionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="durable-composition-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.security = self.root / "security"
        self.security.mkdir()
        self.platform = Path(durable.__file__).resolve().parents[3]
        candidates = [ancestor / "operator-orchestration-service" for ancestor in self.platform.parents]
        self.oos = Path(os.environ["OOS_REPO_ROOT"]) if os.environ.get("OOS_REPO_ROOT") else next(
            path for path in candidates if (path / ".git").exists())
        self.calls = []
        for command in (["git", "init", "-b", "main"], ["git", "config", "user.name", "Synthetic Test Fixture"],
                        ["git", "config", "user.email", "synthetic-fixture@example.invalid"]):
            subprocess.run(command, cwd=self.security, capture_output=True, check=True)
        self.bundle = self.security / durable.BUNDLE_SOURCE_ROOT
        (self.bundle / "records").mkdir(parents=True)
        owners = ["workspace-governance", "operator-orchestration-service", "operator-orchestration-service",
                  "workspace-governance-control-fabric", "operator-orchestration-service", "platform-engineering",
                  "platform-engineering", "security-architecture", "workspace-governance-control-fabric", "platform-engineering"]
        evidence = {}
        for gate, owner in zip(durable.GATES, owners):
            raw = json.dumps({"schema_version": 1, "gate_id": gate, "owner": owner,
                "source_version": "synthetic-source:v1", "record_ref": "synthetic-test://evidence/" + gate,
                "outcome": "accepted"}, sort_keys=True).encode() + b"\n"
            (self.bundle / "records" / (gate + ".json")).write_bytes(raw)
            evidence[gate] = {"artifact_path": f"records/{gate}.json", "artifact_digest": durable.digest(raw)}
        now = datetime.now(timezone.utc)
        render = lambda value: value.isoformat().replace("+00:00", "Z")
        self.manifest = {"schema_version": 1, "manifest_id": "synthetic-test://activation/original",
            "definition_id": "validation-readiness-run", "definition_version": 1,
            "environment": "dev-integration", "profile_id": "temporal", "profile_lifecycle": "active",
            "issued_at": render(now - timedelta(minutes=5)), "expires_at": render(now + timedelta(hours=1)),
            "issued_by": "platform-engineering", "decision": "accepted", "decision_ref": "synthetic-test://decision/original",
            "temporal_target": {"address": "temporal-frontend.devint-temporal-mfshaf7.svc:7233",
                "namespace": "governance-mfshaf7", "identities": {"api": "operator-orchestration-service-api",
                    "workflow_worker": "oos-workflow-worker"}}, "evidence": evidence}
        self.commit_bundle()

    def commit_bundle(self):
        raw = json.dumps(self.manifest, sort_keys=True).encode() + b"\n"
        (self.bundle / "manifest.json").write_bytes(raw)
        subprocess.run(["git", "add", "."], cwd=self.security, check=True, capture_output=True)
        subprocess.run(["git", "commit", "--allow-empty", "-m", "Synthetic activation fixture"],
                       cwd=self.security, check=True, capture_output=True)
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.security, text=True).strip()
        self.policy = {"durable_orchestration": {"enabled": True, "activation_evidence": {
            "manifest_path": durable.BUNDLE_SOURCE_ROOT + "/manifest.json", "manifest_digest": durable.digest(raw)}},
            "security": {"status": "accepted", "security_revision": revision,
                         "decision_uri": "synthetic-test://security/accepted"}}

    def owner_run(self, command, **kwargs):
        self.calls.append(command)
        result = subprocess.run(command, capture_output=True, text=True,
                                input=kwargs.get("input_value"), check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        return result

    def prepare(self):
        durable.prepare(self.policy, workspace_root=self.root, operator="mfshaf7", security_repo=self.security,
            platform_repo=self.platform, oos_repo=self.oos, run=self.owner_run)

    def test_exact_committed_bundle_admits_both_roles_and_restart_preserves_bytes_and_generation(self):
        parent = durable.profile_root(self.root, "mfshaf7")
        parent.mkdir(parents=True, mode=0o755)
        self.prepare()
        root = durable.bundle_root(self.root, "mfshaf7")
        before = {str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in root.rglob("*") if path.is_file()}
        self.prepare()
        after = {str(path.relative_to(root)): (path.read_bytes(), path.stat().st_mtime_ns)
                 for path in root.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(11, len(before))
        self.assertEqual(0o700, root.stat().st_mode & 0o777)
        self.assertEqual(0o755, parent.stat().st_mode & 0o777)
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in root.rglob("*") if path.is_file()))
        self.assertTrue(any("resolveActivationEvidence" in value for command in self.calls for value in command))
        self.assertFalse(any("kubectl" in command for command in self.calls))
        env = durable.environment(self.policy, operator="mfshaf7")
        self.assertEqual("true", env["DEVINT_WGCF_TEMPORAL_WORKER_ENABLED"])
        self.assertEqual(durable.MOUNT, env["OOS_ORCHESTRATION_ACTIVATION_EVIDENCE_PATH"])
        self.assertEqual("oos-workflow-worker", self.manifest["temporal_target"]["identities"]["workflow_worker"])

    def test_missing_acceptance_and_missing_digest_have_no_effect(self):
        for security, binding in (("pending", self.policy["durable_orchestration"]["activation_evidence"]),
                                  ("accepted", {})):
            self.policy["security"]["status"] = security
            self.policy["durable_orchestration"]["activation_evidence"] = binding
            with self.assertRaises(durable.DurableCompositionError):
                self.prepare()
        self.assertEqual([], self.calls)
        self.assertFalse((self.root / ".dev-integration").exists())
        disabled = durable.environment({}, operator="mfshaf7")
        self.assertTrue(all(value == "false" for value in disabled.values()))

    def test_native_validator_rejects_expiry_shared_identity_wrong_target_and_record_hash(self):
        original = json.loads(json.dumps(self.manifest))
        for change in ("expired", "shared-identity", "wrong-target", "record-hash"):
            with self.subTest(change=change):
                self.manifest = json.loads(json.dumps(original))
                if change == "expired":
                    self.manifest["expires_at"] = self.manifest["issued_at"]
                elif change == "shared-identity":
                    self.manifest["temporal_target"]["identities"]["workflow_worker"] = "operator-orchestration-service-api"
                elif change == "wrong-target":
                    self.manifest["temporal_target"]["namespace"] = "governance-other"
                else:
                    self.manifest["evidence"]["security-review-accepted"]["artifact_digest"] = "sha256:" + "0" * 64
                self.commit_bundle()
                with self.assertRaisesRegex(RuntimeError, "existing activation validator denied"):
                    self.prepare()
                self.assertFalse(durable.bundle_root(self.root, "mfshaf7").exists())

    def test_current_bundle_is_not_overwritten_by_unretired_reactivation_or_corrupt_record(self):
        self.prepare()
        root = durable.bundle_root(self.root, "mfshaf7")
        original = (root / "manifest.json").read_bytes()
        self.manifest["manifest_id"] = "synthetic-test://activation/replacement"
        self.commit_bundle()
        with self.assertRaisesRegex(durable.DurableCompositionError, "retirement proof"):
            self.prepare()
        self.assertEqual(original, (root / "manifest.json").read_bytes())
        self.manifest["manifest_id"] = "synthetic-test://activation/original"
        self.commit_bundle()
        (root / "records/contract-valid.json").write_text("corrupt original")
        with self.assertRaisesRegex(durable.DurableCompositionError, "original admitted bytes"):
            self.prepare()
        self.assertEqual("corrupt original", (root / "records/contract-valid.json").read_text())

    def test_retired_generation_cannot_be_reused_by_restart(self):
        self.prepare()
        root = durable.bundle_root(self.root, "mfshaf7")
        old = durable.digest((root / "manifest.json").read_bytes())
        retired = root.parent / "orchestration-retirement" / old.removeprefix("sha256:")
        retired.mkdir(parents=True)
        (retired / "receipt.json").write_text("unverified marker only denies reuse")
        with self.assertRaisesRegex(durable.DurableCompositionError, "retired activation generation"):
            self.prepare()

    def test_interrupted_suspension_reconciles_one_job_and_real_owner_signature(self):
        # Kubernetes/Temporal are seams in this filesystem witness. The
        # committed activation, Platform issue/verify and OOS receipt signing
        # are real owner implementations. An empty synthetic registry does not
        # establish live run reconciliation or native operating acceptance.
        self.prepare()
        root = durable.bundle_root(self.root, "mfshaf7")
        generation = self.policy["durable_orchestration"]["activation_evidence"]["manifest_digest"][7:]
        retirement = root.parent / "orchestration-retirement" / generation
        replicas = {"operator-orchestration-service": 1, "operator-orchestration-service-worker": 1}
        jobs = []
        attempts = []
        template = {"metadata": {"labels": {"app.kubernetes.io/name": "operator-orchestration-service-worker",
                    "orchestration.workspace/identity": "oos-workflow-worker"}},
                    "spec": {"containers": [{"name": "orchestration-worker", "env": []}], "volumes": []}}
        def kubernetes(command, **kwargs):
            if command[:2] != ["k3s", "kubectl"]:
                return self.owner_run(command, **kwargs)
            self.calls.append(command)
            if "get" in command and "deployment" in command:
                name = command[command.index("deployment") + 1]
                return SimpleNamespace(stdout=json.dumps({"spec": {"replicas": replicas[name], "template": template}, "status": {}}))
            if "scale" in command:
                name = next(value.split("/", 1)[1] for value in command if value.startswith("deployment/"))
                replicas[name] = int(command[-1].split("=")[1])
            if "get" in command and "job" in command:
                return SimpleNamespace(stdout=json.dumps(jobs[0]) if jobs else "")
            if "create" in command:
                job = json.loads(kwargs["input_value"])
                container = job["spec"]["template"]["spec"]["containers"][0]
                self.assertNotIn("envFrom", container)
                self.assertEqual("oos-workflow-worker", job["spec"]["template"]["metadata"]["labels"]["orchestration.workspace/identity"])
                self.assertEqual(600, job["spec"]["activeDeadlineSeconds"])
                self.assertTrue(any(item.get("readOnly") for item in container["volumeMounts"]
                                    if item["name"] == "retirement-evidence"))
                jobs.append(job)
            if "wait" in command and "--for=condition=complete" in command:
                attempts.append(1)
                if len(attempts) > 1:
                    return SimpleNamespace(stdout="", returncode=0)  # Re-read the original completed job's file.
                script = """import {pathToFileURL} from 'node:url';import {join} from 'node:path';import {readFileSync} from 'node:fs';import {createHash} from 'node:crypto';
const [owner,activation,dir,activationDigest]=process.argv.slice(1);
const c=await import(pathToFileURL(join(owner,'src/config.js')).href);
const r=await import(pathToFileURL(join(owner,'src/orchestration/generation-retirement.js')).href);
const s=await import(pathToFileURL(join(owner,'src/orchestration/generation-start-registry.js')).href);
const constants=await import(pathToFileURL(join(owner,'src/orchestration/constants.js')).href);
const bytes=readFileSync(join(dir,'manifest.json'));const manifest=JSON.parse(bytes);
const hash=v=>'sha256:'+createHash('sha256').update(v).digest('hex');
const config=c.loadConfig({OOS_ORCHESTRATION_ACTIVATION_EVIDENCE_PATH:join(activation,'manifest.json'),
 OOS_ORCHESTRATION_ACTIVATION_EVIDENCE_DIGEST:activationDigest,
 OOS_TEMPORAL_ADDRESS:'temporal-frontend.devint-temporal-mfshaf7.svc:7233',OOS_TEMPORAL_NAMESPACE:'governance-mfshaf7',
 OOS_TEMPORAL_IDENTITY:'oos-workflow-worker',OOS_ORCHESTRATION_RETIREMENT_EVIDENCE_PATH:join(dir,'manifest.json'),
 OOS_ORCHESTRATION_RETIREMENT_EVIDENCE_DIGEST:hash(bytes),OOS_ORCHESTRATION_RETIREMENT_RECEIPT_KEY_ID:manifest.receipt_verification.key_id,
 OOS_ORCHESTRATION_RETIREMENT_RECEIPT_PRIVATE_KEY_PATH:join(dir,'receipt-private-key.pem'),
 OOS_ORCHESTRATION_RETIREMENT_RECEIPT_PUBLIC_KEY_PATH:join(dir,'receipt-public-key.pem')},
 {orchestrationProcessRole:c.ORCHESTRATION_WORKER_PROCESS_ROLE});
const retirement=r.resolveGenerationRetirement(config);if(!retirement.valid)throw Error(JSON.stringify(retirement));
const now=new Date().toISOString();const registry={...s.generationStartRegistryInputFor(activationDigest),
 registry_workflow_type:constants.GENERATION_START_REGISTRY_WORKFLOW_TYPE,invalid_registration_count:0,registered_workflow_ids:[],
 seal_ref:manifest.retirement_id,seal_authorization_digest:hash(bytes),sealed_at:now};
const receipt=r.createGenerationRetirementReceipt(config,retirement,{cancelSignalTargetCount:0,matchedExecutionCount:0,
 recordedAt:now,registryResult:registry,registryResultDigest:hash(JSON.stringify(registry)),retirementStartedAt:now,
 terminalProjectionCount:0,uncommittedRegistrationCount:0});console.log(JSON.stringify(receipt));"""
                result = self.owner_run(["node", "--input-type=module", "--eval", script,
                    str(self.oos), str(root), str(retirement), "sha256:" + generation])
                (retirement / "result/receipt.json").write_text(result.stdout)
                if len(attempts) == 1:
                    raise RuntimeError("synthetic acknowledgement lost after owner result")
            return SimpleNamespace(stdout="", returncode=0)
        with self.assertRaisesRegex(RuntimeError, "acknowledgement lost"):
            durable.suspend(self.policy, workspace_root=self.root, operator="mfshaf7", platform_repo=self.platform, run=kubernetes)
        self.assertFalse((retirement / "receipt.json").exists())
        self.assertTrue((retirement / "receipt-private-key.pem").is_file())
        durable.suspend(self.policy, workspace_root=self.root, operator="mfshaf7", platform_repo=self.platform, run=kubernetes)
        self.assertEqual(1, len(jobs))
        self.assertFalse((retirement / "receipt-private-key.pem").exists())
        durable.verify_prior_retirement(root, "sha256:" + generation, platform_repo=self.platform)
        self.assertEqual(1, replicas["operator-orchestration-service"])
        self.assertEqual(0, replicas["operator-orchestration-service-worker"])
        self.assertEqual(0, replicas["workspace-governance-control-fabric-temporal-activity"])


if __name__ == "__main__":
    unittest.main()
