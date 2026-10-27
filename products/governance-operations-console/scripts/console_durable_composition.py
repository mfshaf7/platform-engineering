"""Compose the existing admitted OOS definition and read-only WGCF worker.

The exact Security decision selects a committed activation bundle. This module
publishes those original bytes and invokes the OOS role-aware validator; it
does not infer activation authority from source presence or worker readiness.
"""
from __future__ import annotations

from argparse import Namespace
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile

from console_profile_requests import private_directory, lifecycle
from dev_integration_compositions import _render_service_projection

BUNDLE_SOURCE_ROOT = "docs/reviews/components/console-capabilities-1332"
MOUNT = "/var/run/oos/orchestration-activation/manifest.json"
WORKER_IMAGE = re.compile(r"ghcr\.io/mfshaf7/workspace-governance-control-fabric-worker@sha256:[0-9a-f]{64}\Z")
GATES = (
    "contract-valid", "implementation-reviewed", "deterministic-replay-tested",
    "activity-idempotency-tested", "failure-and-control-tested",
    "dev-integration-profile-active", "platform-runtime-accepted",
    "security-review-accepted", "source-projection-verified", "rollback-and-suspension-proven",
)


def retirement_module(platform_repo):
    source = platform_repo / "dev-integration/profiles/temporal/scripts/generation_retirement.py"
    spec = importlib.util.spec_from_file_location("console_existing_generation_retirement", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class DurableCompositionError(RuntimeError):
    pass


def enabled(policy):
    return policy.get("durable_orchestration", {}).get("enabled") is True


def profile_root(workspace_root, operator):
    return workspace_root / ".dev-integration/accepted-idea-delivery" / operator


def bundle_root(workspace_root, operator):
    return profile_root(workspace_root, operator) / "orchestration-activation"


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def accepted_binding(policy):
    binding = policy.get("durable_orchestration", {}).get("activation_evidence")
    if (policy.get("security", {}).get("status") != "accepted" or not isinstance(binding, dict)
            or set(binding) != {"manifest_path", "manifest_digest", "wgcf_worker_image"}
            or binding["manifest_path"] != BUNDLE_SOURCE_ROOT + "/manifest.json"
            or not isinstance(binding["manifest_digest"], str)
            or len(binding["manifest_digest"]) != 71
            or not binding["manifest_digest"].startswith("sha256:")
            or not isinstance(binding["wgcf_worker_image"], str)
            or not WORKER_IMAGE.fullmatch(binding["wgcf_worker_image"])):
        raise DurableCompositionError("Durable composition requires the exact accepted Security bundle binding.")
    return binding


def environment(policy, *, operator):
    values = {"OOS_ORCHESTRATION_RUNTIME_ENABLED": "false", "OOS_ORCHESTRATION_WORKER_ENABLED": "false",
              "OOS_ORCHESTRATION_EXECUTION_AUTHORIZED": "false", "DEVINT_WGCF_TEMPORAL_WORKER_ENABLED": "false",
              "DEVINT_WGCF_TEMPORAL_ACTIVITY_EXECUTION_AUTHORIZED": "false"}
    if not enabled(policy):
        return values
    binding = accepted_binding(policy)
    address = _render_service_projection({"service_name": "temporal-frontend", "service_port": 7233,
        "address_format": "host-port"}, namespace=f"devint-temporal-{operator}")
    namespace = f"governance-{operator}"
    values.update({"OOS_ORCHESTRATION_RUNTIME_ENABLED": "true", "OOS_ORCHESTRATION_WORKER_ENABLED": "true",
        "OOS_ORCHESTRATION_EXECUTION_AUTHORIZED": "true",
        "OOS_ORCHESTRATION_ACTIVATION_EVIDENCE_PATH": MOUNT,
        "OOS_ORCHESTRATION_ACTIVATION_EVIDENCE_DIGEST": binding["manifest_digest"],
        "OOS_TEMPORAL_ADDRESS": address, "OOS_TEMPORAL_NAMESPACE": namespace,
        "DEVINT_WGCF_TEMPORAL_WORKER_ENABLED": "true",
        "DEVINT_WGCF_TEMPORAL_ACTIVITY_EXECUTION_AUTHORIZED": "true",
        "DEVINT_WGCF_TEMPORAL_WORKER_IMAGE": binding["wgcf_worker_image"],
        "DEVINT_WGCF_TEMPORAL_ACTIVATION_REVIEW_REF": policy["security"]["decision_uri"],
        "DEVINT_WGCF_TEMPORAL_ADDRESS": address, "DEVINT_WGCF_TEMPORAL_NAMESPACE": namespace})
    return values


def validate_owner_bundle(policy, root, *, operator, oos_repo, run):
    values = environment(policy, operator=operator)
    # Call the owner's existing pure resolver directly. This also permits the
    # accepted-base filesystem proof to use its locked OOS contract checkout;
    # it does not need a newer launcher or installed Temporal SDK to connect.
    script = """import {pathToFileURL} from 'node:url';import {join} from 'node:path';
const [owner,root]=process.argv.slice(1);
const c=await import(pathToFileURL(join(owner,'src/config.js')).href);
const a=await import(pathToFileURL(join(owner,'src/orchestration/activation-evidence.js')).href);
for(const role of [undefined,c.ORCHESTRATION_WORKER_PROCESS_ROLE]) {
 const config=c.loadConfig({...process.env,OOS_ORCHESTRATION_ACTIVATION_EVIDENCE_PATH:join(root,'manifest.json'),
  OOS_TEMPORAL_IDENTITY:role?c.ORCHESTRATION_WORKER_TEMPORAL_IDENTITY:c.ORCHESTRATION_API_TEMPORAL_IDENTITY},
  role?{orchestrationProcessRole:role}:{});
 if(!a.resolveActivationEvidence(config).valid)throw Error('The existing activation validator denied the exact API/worker bundle.');
}console.log('1');"""
    command = ["env", *(f"{key}={value}" for key, value in values.items()), "node",
               "--input-type=module", "--eval", script, str(oos_repo), str(root)]
    if run(command).stdout.strip() != "1":
        raise DurableCompositionError("The existing OOS validator did not admit both original process roles.")


def verify_prior_retirement(root, previous_digest, *, platform_repo):
    retirement = root.parent / "orchestration-retirement" / previous_digest.removeprefix("sha256:")
    manifest_path = retirement / "manifest.json"
    receipt_path = retirement / "receipt.json"
    public_key = retirement / "receipt-public-key.pem"
    for path in (manifest_path, receipt_path, public_key):
        if path.is_symlink() or not path.is_file() or path.stat().st_uid != os.geteuid():
            raise DurableCompositionError("Changed durable authority requires the existing original-generation retirement proof.")
    # Reuse the Platform retirement verifier, including its Ed25519 attestation,
    # exact registry seal, original generation/queue and source-target checks.
    module = retirement_module(platform_repo)
    raw = manifest_path.read_bytes()
    if json.loads(raw).get("activation_evidence_digest") != previous_digest:
        raise DurableCompositionError("Retirement proof names another activation generation.")
    try:
        module.verify_receipt(Namespace(retirement_manifest=manifest_path, retirement_digest=digest(raw),
            receipt=receipt_path, receipt_public_key=public_key))
    except (ValueError, OSError, RuntimeError) as error:
        raise DurableCompositionError("The original durable generation has no valid retirement receipt.") from error


def prepare(policy, *, workspace_root, operator, security_repo, platform_repo, oos_repo, run):
    if not enabled(policy):
        return
    binding = accepted_binding(policy)
    revision = policy["security"]["security_revision"]
    def source(path):
        raw = run(["git", "-C", str(security_repo), "show", f"{revision}:{path}"]).stdout.encode()
        if not raw or len(raw) > 65536:
            raise DurableCompositionError("A committed activation bundle artifact is absent or oversized.")
        return raw
    files = {"manifest.json": source(binding["manifest_path"])}
    if digest(files["manifest.json"]) != binding["manifest_digest"]:
        raise DurableCompositionError("Committed activation manifest differs from its accepted exact digest.")
    for gate in GATES:
        files[f"records/{gate}.json"] = source(f"{BUNDLE_SOURCE_ROOT}/records/{gate}.json")
    root = bundle_root(workspace_root, operator)
    # The parent belongs to the profile's shared session metadata. Preserve its
    # existing permissions; only our bundle/evidence children are private.
    root.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    if root.parent.is_symlink() or not root.parent.is_dir() or root.parent.stat().st_uid != os.geteuid():
        raise DurableCompositionError("The existing profile state root has unsafe custody.")
    if root.is_symlink():
        raise DurableCompositionError("Durable activation custody must not be a symlink.")
    # Validate all staged original bytes before changing any retained bundle or
    # invoking a runtime action. The actual OOS validator checks record hashes,
    # every owner, lifetime, target and both distinct process identities.
    temporary = Path(tempfile.mkdtemp(prefix=".orchestration-activation-", dir=root.parent))
    try:
        for name, raw in files.items():
            path = temporary / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            path.write_bytes(raw)
            path.chmod(0o600)
        validate_owner_bundle(policy, temporary, operator=operator, oos_repo=oos_repo, run=run)
        previous = root / "manifest.json"
        if previous.exists():
            if previous.is_symlink() or not previous.is_file():
                raise DurableCompositionError("Retained activation evidence has unsafe custody.")
            old_digest = digest(previous.read_bytes())
            if old_digest == binding["manifest_digest"]:
                retired = root.parent / "orchestration-retirement" / old_digest.removeprefix("sha256:") / "receipt.json"
                if retired.exists():
                    raise DurableCompositionError("A retired activation generation cannot be reused; obtain fresh accepted authority.")
                if any((root / name).is_symlink() or not (root / name).is_file()
                       or (root / name).read_bytes() != raw for name, raw in files.items()):
                    raise DurableCompositionError("Retained activation records differ from their original admitted bytes.")
                return  # Ordinary restart does not reissue or rotate authority.
            verify_prior_retirement(root, old_digest, platform_repo=platform_repo)
            archive = root.parent / "orchestration-retired" / old_digest.removeprefix("sha256:")
            private_directory(archive.parent)
            if archive.exists():
                raise DurableCompositionError("Retired activation archive already exists; reconcile original evidence.")
            root.rename(archive)
        elif root.exists():
            if not root.is_dir() or any(root.iterdir()):
                raise DurableCompositionError("Unproven activation state requires owner reconciliation.")
            root.rmdir()
        temporary.rename(root)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def status(policy, *, workspace_root, operator, oos_repo, run):
    if not enabled(policy):
        return {"enabled": False}
    validate_owner_bundle(policy, bundle_root(workspace_root, operator), operator=operator, oos_repo=oos_repo, run=run)
    for namespace, deployment in (
        (f"devint-accepted-idea-delivery-{operator}", "operator-orchestration-service-worker"),
        (f"devint-governance-control-fabric-{operator}", "workspace-governance-control-fabric-temporal-activity"),
    ):
        value = json.loads(run(["k3s", "kubectl", "-n", namespace, "get", "deployment", deployment, "-o", "json"]).stdout)
        if value.get("spec", {}).get("replicas") != 1 or value.get("status", {}).get("readyReplicas") != 1:
            raise DurableCompositionError("An admitted durable worker is unavailable.")
        if deployment == "workspace-governance-control-fabric-temporal-activity":
            containers = value.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
            if len(containers) != 1 or containers[0].get("image") != accepted_binding(policy)["wgcf_worker_image"]:
                raise DurableCompositionError("The activity worker does not use the exact Security-reviewed image digest.")
    worker = json.loads(run(["k3s", "kubectl", "-n", f"devint-accepted-idea-delivery-{operator}", "exec",
        "deployment/operator-orchestration-service-worker", "-c", "orchestration-worker", "--",
        "node", "src/orchestration-worker.js", "status"]).stdout)
    activity = json.loads(run(["k3s", "kubectl", "-n", f"devint-governance-control-fabric-{operator}", "exec",
        "deployment/workspace-governance-control-fabric-temporal-activity", "-c", "temporal-activity-worker", "--",
        "wgcf-worker", "status", "--json"]).stdout)
    source = run(["k3s", "kubectl", "-n", f"devint-governance-control-fabric-{operator}", "exec",
        "deployment/workspace-governance-control-fabric-temporal-activity", "-c", "temporal-activity-worker", "--",
        "cat", "/opt/wgcf/build/source-revision"]).stdout.strip()
    if (worker.get("run_allowed") is not True or worker.get("activation_evidence_digest") != accepted_binding(policy)["manifest_digest"]
            or activity.get("activation", {}).get("authorized") is not True
            or activity.get("temporal", {}).get("identity") != "wgcf-activity-worker"
            or activity.get("temporal", {}).get("task_queue") != "wgcf.validation-readiness.v1"
            or source != policy["security"]["reviewed_revisions"]["workspace-governance-control-fabric"]):
        raise DurableCompositionError("Live durable worker identity or original activation evidence is invalid.")
    return {"enabled": True, "definition_id": "validation-readiness-run", "definition_version": 1,
            "activation_evidence_digest": accepted_binding(policy)["manifest_digest"],
            "activity_worker_image": accepted_binding(policy)["wgcf_worker_image"],
            "activity_worker_source_revision": source,
            "original_generation_preserved": True, "workflow_and_activity_workers_ready": True}


def suspend(policy, *, workspace_root, operator, platform_repo, run):
    """Use the existing fenced OOS retirement operation before withdrawing work.

    This is bounded composition of the admitted owner command, not a second
    workflow implementation. Interrupted jobs and evidence remain recoverable.
    """
    if not enabled(policy):
        return
    root = bundle_root(workspace_root, operator)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        return  # No admitted generation was ever commissioned.
    previous_digest = digest(manifest_path.read_bytes())
    generation = previous_digest.removeprefix("sha256:")
    retirement = root.parent / "orchestration-retirement" / generation
    private_directory(retirement)
    receipt_path = retirement / "receipt.json"
    if receipt_path.exists():
        verify_prior_retirement(root, previous_digest, platform_repo=platform_repo)
        (retirement / "receipt-private-key.pem").unlink(missing_ok=True)
        run(["k3s", "kubectl", "-n", f"devint-accepted-idea-delivery-{operator}", "delete", "job",
             "oos-retire-" + generation[:24], "--ignore-not-found", "--wait=true"])
        restore_non_durable_api(run, operator=operator)
        return
    ns = f"devint-accepted-idea-delivery-{operator}"
    kubectl = ["k3s", "kubectl", "-n", ns]
    worker_name = "operator-orchestration-service-worker"
    worker = json.loads(run([*kubectl, "get", "deployment", worker_name, "-o", "json"]).stdout)
    # Drain both normal pollers and API start ingress. Zero ready pods alone
    # does not prove that their terminating processes have stopped.
    for name in ("operator-orchestration-service", worker_name):
        run([*kubectl, "scale", "deployment/" + name, "--replicas=0"])
        run([*kubectl, "wait", "--for=delete", "pods", "-l", f"app.kubernetes.io/name={name}", "--timeout=180s"])
        value = json.loads(run([*kubectl, "get", "deployment", name, "-o", "json"]).stdout)
        if value.get("spec", {}).get("replicas") != 0 or any(value.get("status", {}).get(key, 0)
                for key in ("replicas", "readyReplicas", "availableReplicas")):
            raise DurableCompositionError("Original durable start ingress or poller is still running.")
    now = datetime.now(timezone.utc)
    render = lambda value: value.isoformat().replace("+00:00", "Z")
    public = retirement / "receipt-public-key.pem"
    private = retirement / "receipt-private-key.pem"
    authorization = retirement / "manifest.json"
    key_id = "oos-generation-retirement-" + generation[:16]
    if not authorization.exists():
        if private.exists() or public.exists():
            raise DurableCompositionError("Interrupted retirement key setup requires original-state reconciliation.")
        run(["openssl", "genpkey", "-algorithm", "ED25519", "-out", str(private)])
        private.chmod(0o600)
        run(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)])
        public.chmod(0o600)
        authority_ref = "platform-engineering://console-capabilities-1332/retirement/" + generation
        module = retirement_module(platform_repo)
        module.issue_manifest(Namespace(activation_manifest=manifest_path, activation_digest=previous_digest,
            retirement_id=authority_ref, reason_ref="openproject://work_packages/1332",
            receipt_key_id=key_id, receipt_public_key=public, resume_seal_manifest=None, resume_seal_digest=None,
            issued_at=render(now), expires_at=render(now + timedelta(minutes=15)),
            start_ingress_active_replicas=0, in_flight_starts=0, start_ingress_observed_at=render(now),
            start_ingress_evidence_ref=authority_ref + "/start-ingress-stopped",
            workflow_poller_active_replicas=0, workflow_poller_observed_at=render(now),
            workflow_poller_evidence_ref=authority_ref + "/workflow-poller-stopped", output=authorization))
    result_root = retirement / "result"
    private_directory(result_root)
    template = json.loads(json.dumps(worker["spec"]["template"]))
    spec = template["spec"]
    container = spec["containers"][0]
    container["command"] = ["/bin/sh", "-ec", "node src/orchestration-worker.js retire > /var/lib/oos/retirement-result/receipt.json"]
    container.pop("args", None)
    values = {"OOS_ORCHESTRATION_RETIREMENT_EVIDENCE_PATH": "/var/run/oos/orchestration-retirement/manifest.json",
        "OOS_ORCHESTRATION_RETIREMENT_EVIDENCE_DIGEST": digest(authorization.read_bytes()),
        "OOS_ORCHESTRATION_RETIREMENT_RECEIPT_KEY_ID": key_id,
        "OOS_ORCHESTRATION_RETIREMENT_RECEIPT_PRIVATE_KEY_PATH": "/var/run/oos/orchestration-retirement/receipt-private-key.pem",
        "OOS_ORCHESTRATION_RETIREMENT_RECEIPT_PUBLIC_KEY_PATH": "/var/run/oos/orchestration-retirement/receipt-public-key.pem"}
    container["env"] = [entry for entry in container.get("env", []) if entry["name"] not in values]
    container["env"].extend({"name": key, "value": value} for key, value in values.items())
    container.setdefault("volumeMounts", []).extend([
        {"name": "retirement-evidence", "mountPath": "/var/run/oos/orchestration-retirement", "readOnly": True},
        {"name": "retirement-result", "mountPath": "/var/lib/oos/retirement-result"}])
    spec.setdefault("volumes", []).extend([
        {"name": "retirement-evidence", "hostPath": {"path": str(retirement), "type": "Directory"}},
        {"name": "retirement-result", "hostPath": {"path": str(result_root), "type": "Directory"}}])
    spec["restartPolicy"] = "Never"
    # Keep this bounded infrastructure job distinct from the stopped Deployment
    # selector while retaining the existing Temporal owner/network identity.
    template["metadata"]["labels"]["app.kubernetes.io/name"] = "oos-generation-retirement"
    job_name = "oos-retire-" + generation[:24]
    job = {"apiVersion": "batch/v1", "kind": "Job", "metadata": {"name": job_name, "namespace": ns},
           "spec": {"backoffLimit": 0, "activeDeadlineSeconds": 600, "template": template}}
    existing = run([*kubectl, "get", "job", job_name, "--ignore-not-found", "-o", "json"]).stdout.strip()
    if not existing:
        run([*kubectl, "create", "-f", "-"], input_value=json.dumps(job))
    run([*kubectl, "wait", "--for=condition=complete", "job/" + job_name, "--timeout=600s"])
    result = result_root / "receipt.json"
    if result.is_symlink() or not result.is_file() or result.stat().st_size > 65536:
        raise DurableCompositionError("Original OOS retirement job produced no bounded owner receipt.")
    # Verify before publishing the terminal marker or removing any job/key.
    module = retirement_module(platform_repo)
    module.verify_receipt(Namespace(retirement_manifest=authorization,
        retirement_digest=digest(authorization.read_bytes()), receipt=result, receipt_public_key=public))
    lifecycle.write_atomic(receipt_path, result.read_bytes())
    verify_prior_retirement(root, previous_digest, platform_repo=platform_repo)
    private.unlink(missing_ok=True)
    run([*kubectl, "delete", "job", job_name, "--ignore-not-found", "--wait=true"])
    restore_non_durable_api(run, operator=operator)


def restore_non_durable_api(run, *, operator):
    kubectl = ["k3s", "kubectl", "-n", f"devint-accepted-idea-delivery-{operator}"]
    run([*kubectl, "set", "env", "deployment/operator-orchestration-service", "OOS_ORCHESTRATION_EXECUTION_AUTHORIZED=false"])
    run([*kubectl, "scale", "deployment/operator-orchestration-service", "--replicas=1"])
    run([*kubectl, "rollout", "status", "deployment/operator-orchestration-service", "--timeout=180s"])
    run(["k3s", "kubectl", "-n", f"devint-governance-control-fabric-{operator}", "scale",
         "deployment/workspace-governance-control-fabric-temporal-activity", "--replicas=0"])
