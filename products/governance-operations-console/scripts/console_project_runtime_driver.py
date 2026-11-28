"""Run an exact, admitted project operation through the existing local K3s owner."""

from __future__ import annotations

import hashlib
import ipaddress
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import time

from agent_source_identity import write_json_atomic
from console_project_runtime_artifacts import copy_verified_dependencies, qualify_build
from console_project_runtime_sandbox import ProjectSandbox
from console_project_runtime_setup import NODE_SCRIPTS, PAIRED_NODE_RECIPE, source_path
from console_project_runtime_snapshot import stage_project_snapshot


class SandboxError(RuntimeError):
    """The project operation could not be observed safely."""


class K3sProjectClient:
    """Use the current Platform operator's k3s client with fixed verbs and no shell."""

    def _call(self, *args, data=None, stream=None, output=None, timeout=30):
        try:
            result = subprocess.run(["k3s", "kubectl", *args], input=data, stdin=stream,
                                    stdout=output if output is not None else subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, timeout=timeout, check=True)
        except (OSError, subprocess.SubprocessError):
            raise SandboxError("The isolated K3s owner action did not complete.") from None
        return result.stdout

    def get(self, kind, name, namespace=None):
        location = ["-n", namespace] if namespace else []
        content = self._call(*location, "get", kind, name, "-o", "json", "--ignore-not-found")
        return json.loads(content) if content else None

    def create(self, document):
        return json.loads(self._call("create", "-o", "json", "-f", "-", data=json.dumps(document).encode()))

    def list(self, kind, namespace):
        return json.loads(self._call("-n", namespace, "get", kind, "-o", "json"))["items"]

    def wait_ready(self, namespace, name, seconds):
        self._call("-n", namespace, "wait", "--for=condition=Ready", f"pod/{name}",
                   f"--timeout={seconds}s", timeout=seconds + 10)

    def wait_build(self, namespace, name, seconds):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            observed = self.get("pod", name, namespace)
            if observed is None:
                raise SandboxError("The isolated build or data copy disappeared before completion.")
            phase = observed.get("status", {}).get("phase")
            if phase == "Succeeded":
                return
            if phase == "Failed":
                raise SandboxError("The isolated build or data copy reported failure.")
            delay = min(2, deadline - time.monotonic())
            if delay > 0:
                time.sleep(delay)
        raise SandboxError("The isolated build or data copy did not complete within its reviewed time limit.")

    def remove(self, kind, name, namespace):
        self._call("-n", namespace, "delete", kind, name, "--ignore-not-found", "--wait=true", "--timeout=45s", timeout=55)

    def transfer(self, namespace, pod, archive, target):
        self._call("-n", namespace, "exec", "-i", pod, "--", "tar", "-x", "-C", target,
                   "--no-same-owner", "--no-same-permissions", stream=archive, timeout=120)

    def output(self, namespace, pod, destination, byte_limit):
        # The trusted reader only receives a read-only qualified output volume.
        # Keep a growing project archive from consuming unbounded host storage.
        script = 'set -o pipefail; tar -c --sort=name -C /project-build . | head -c "$1"'
        self._call("-n", namespace, "exec", pod, "--", "/bin/bash", "-ec", script, "read-build", str(byte_limit + 1),
                   output=destination, timeout=120)


class ProjectSandboxDriver:
    """Produce owner observations from real pods and preserve the prior good build."""

    def __init__(self, root, *, kube, snapshot_root, cache_root, authorize, dependency_approval, preview=None):
        self.root = Path(root)
        self.kube = kube
        self.snapshot_root = Path(snapshot_root)
        self.cache_root = Path(cache_root)
        self.authorize = authorize
        self.dependency_approval = dependency_approval
        self.preview = preview

    def _receipt(self, operation):
        return self.root / "sandbox-receipts" / f"{operation.split(':', 1)[1]}.json"

    def _sandbox(self, record):
        policy = self.authorize(record)
        if not policy:
            raise SandboxError("The exact reviewed project sandbox is not admitted.")
        return ProjectSandbox(record["binding"]["scope_digest"], record["operation_id"], policy["recipe"]), policy

    def _project_object(self, sandbox, document):
        metadata = document["metadata"]
        namespace = metadata.get("namespace")
        previous = self.kube.get(document["kind"].lower(), metadata["name"], namespace)
        if previous is None:
            return self.kube.create(document)
        existing = previous.get("metadata", {})
        if (existing.get("annotations", {}).get("platform.project/scope") != sandbox.scope
                or existing.get("labels", {}).get("app.kubernetes.io/managed-by") != "platform-project-runtime"):
            raise SandboxError("The selected Kubernetes object is outside this Platform project scope.")
        if document["kind"] == "Namespace":
            labels = metadata["labels"]
            if any(existing.get("labels", {}).get(name) != value for name, value in labels.items()):
                raise SandboxError("The project namespace's Pod Security labels changed.")
        else:
            wanted = document["spec"]
            actual = previous.get("spec", {})
            kind = document["kind"]
            if kind == "NetworkPolicy":
                # The API omits empty rule arrays from persisted deny policies.
                # Their omission and an explicit empty list deny the same traffic.
                actual = {"ingress": [], "egress": [], **actual}
            if (kind not in ("NetworkPolicy", "ResourceQuota", "PersistentVolumeClaim")
                    or any(expected != actual.get(name) for name, expected in wanted.items()
                           if kind != "PersistentVolumeClaim" or name != "resources")
                    or (kind == "PersistentVolumeClaim" and wanted["resources"]["requests"] != actual.get("resources", {}).get("requests"))
                    or any(existing.get("annotations", {}).get(key) != value for key, value in metadata["annotations"].items())):
                raise SandboxError("The retained project policy or volume no longer matches the reviewed configuration.")
        return previous

    def _remove_owned(self, sandbox, kind, name, operation):
        observed = self.kube.get(kind, name, sandbox.namespace)
        if observed is None:
            return
        annotations = observed.get("metadata", {}).get("annotations", {})
        if annotations.get("platform.project/scope") != sandbox.scope or annotations.get("platform.project/operation") != operation:
            raise SandboxError("The selected compute is no longer owned by this project operation.")
        self.kube.remove(kind, name, sandbox.namespace)
        if self.kube.get(kind, name, sandbox.namespace) is not None:
            raise SandboxError("The isolated owner could not confirm compute was released.")

    def _observation(self, record, phase, **evidence):
        binding = record["binding"]
        return {"operation_id": record["operation_id"], "command_id": record["command_id"],
                "scope_digest": binding["scope_digest"], "manifest_digest": binding["snapshot"]["manifest_digest"],
                "configuration_revision": binding["setup"]["configuration_revision"], "state": phase, **evidence}

    def _retain(self, record, observation):
        write_json_atomic(self._receipt(record["operation_id"]), observation)
        return observation

    @staticmethod
    def _checked_dependency_archive(archive, max_bytes):
        total = 0
        for entry in archive:
            name = entry.name.removeprefix("./")
            if entry.isdir() and name in ("", "."):
                continue
            source_path(name)
            allowed = name == "_cacache" or name.startswith("_cacache/")
            if not allowed or not (entry.isdir() or entry.isfile()):
                raise SandboxError("The approved dependency archive contains unsupported entries.")
            total += entry.size
            if total > max_bytes:
                raise SandboxError("The expanded dependency cache exceeds its reviewed limit.")

    def _stage(self, sandbox, policy, record, transfer):
        binding = record["binding"]
        staged = stage_project_snapshot(self.snapshot_root, self.root, binding, **policy["source_limits"])
        try:
            with tempfile.TemporaryFile(dir=self.root) as archive:
                with tarfile.open(fileobj=archive, mode="w") as content:
                    for entry in sorted(staged.iterdir()):
                        content.add(entry, arcname=entry.name)
                archive.seek(0)
                self.kube.transfer(sandbox.namespace, transfer, archive, "/project-input")
            recipe = binding["setup"]["recipe_id"]
            if recipe not in NODE_SCRIPTS:
                return
            lock = staged / binding["scope"]["app_root"] / "package-lock.json"
            if not lock.is_file():
                raise SandboxError("The exact saved source does not contain its approved package-lock.json.")
            with lock.open("rb") as stream:
                lock_digest = f"sha256:{hashlib.file_digest(stream, 'sha256').hexdigest()}"
            approved = self.dependency_approval(binding, lock_digest, sandbox.recipe.image)
            if approved is None:
                raise SandboxError("The exact package lock has no approved offline dependency archive.")
            cache = staged / ".owner-offline-cache.tar"
            copy_verified_dependencies(self.cache_root, cache, recipe=recipe, image=sandbox.recipe.image,
                                       lock_digest=lock_digest, approved=approved, max_bytes=policy["cache_bytes"])
            with tarfile.open(cache, mode="r:") as archive:
                self._checked_dependency_archive(archive, policy["cache_expanded_bytes"])
            with cache.open("rb") as archive:
                self.kube.transfer(sandbox.namespace, transfer, archive, "/approved-cache")
        finally:
            shutil.rmtree(staged)

    def _build(self, sandbox, policy, record):
        for role, size in (("input", policy["input_mib"]), ("dependencies", policy["cache_mib"]),
                           ("build", sandbox.recipe.output_mib)):
            self._project_object(sandbox, sandbox.volume(role, size))
        transfer = sandbox.transfer_pod()
        transfer_name = transfer["metadata"]["name"]
        self._project_object(sandbox, transfer)
        self.kube.wait_ready(sandbox.namespace, transfer_name, sandbox.recipe.build.deadline_seconds)
        self._stage(sandbox, policy, record, transfer_name)
        self._remove_owned(sandbox, "pod", transfer_name, sandbox.operation)

        binding = record["binding"]
        build = sandbox.build_pod(binding["setup"]["recipe_id"], binding["scope"]["app_root"])
        build["metadata"]["annotations"].update({"platform.project/manifest": binding["snapshot"]["manifest_digest"],
                                                   "platform.project/setup": binding["setup"]["configuration_revision"]})
        build_name = build["metadata"]["name"]
        created = self._project_object(sandbox, build)
        self.kube.wait_build(sandbox.namespace, build_name, sandbox.recipe.build.deadline_seconds)
        observed = self.kube.get("pod", build_name, sandbox.namespace)
        if observed is None:
            raise SandboxError("The expected isolated build disappeared before verification.")
        metadata = observed["metadata"]
        annotations = metadata.get("annotations", {})
        container = observed["spec"]["containers"][0]
        volume = next(volume for volume in observed["spec"]["volumes"] if volume["name"] == "build")
        reader = sandbox.artifact_reader()
        reader_name = reader["metadata"]["name"]
        self._project_object(sandbox, reader)
        self.kube.wait_ready(sandbox.namespace, reader_name, sandbox.recipe.build.deadline_seconds)
        with tempfile.TemporaryFile(dir=self.root) as output:
            self.kube.output(sandbox.namespace, reader_name, output, sandbox.recipe.output_mib * 1024 * 1024)
            size = output.tell()
            if not 0 < size <= sandbox.recipe.output_mib * 1024 * 1024:
                raise SandboxError("The build output exceeds its owner-reviewed artifact budget.")
            output.seek(0)
            content_digest = f"sha256:{hashlib.file_digest(output, 'sha256').hexdigest()}"
        artifact = qualify_build(binding, expected_uid=created["metadata"]["uid"], image=sandbox.recipe.image,
                                 output_claim=sandbox.volume_name("build"), output_digest=content_digest,
                                 observed={"uid": metadata["uid"], "phase": observed.get("status", {}).get("phase"),
                                           "image": container["image"], "output_claim": volume["persistentVolumeClaim"]["claimName"],
                                           "scope_digest": annotations.get("platform.project/scope"),
                                           "operation_id": annotations.get("platform.project/operation"),
                                           "manifest_digest": annotations.get("platform.project/manifest"),
                                           "configuration_revision": annotations.get("platform.project/setup")})
        self._remove_owned(sandbox, "pod", reader_name, sandbox.operation)
        self._remove_owned(sandbox, "pod", build_name, sandbox.operation)
        for role in ("input", "dependencies"):
            self._remove_owned(sandbox, "persistentvolumeclaim", sandbox.volume_name(role), sandbox.operation)
        return {**artifact, "build_operation": sandbox.operation}

    def _previous_receipt(self, record):
        previous = record["previous"]
        if previous is None:
            raise SandboxError("No qualified runtime exists for the requested operation.")
        receipt = json.loads(self._receipt(previous["operation_id"]).read_text(encoding="utf-8"))
        if receipt.get("artifact_digest") != previous["artifact_digest"] or receipt.get("state") != "ready":
            raise SandboxError("The prior build receipt does not match the retained runtime.")
        return receipt

    def _check_claim(self, sandbox, name, operation):
        claim = self.kube.get("persistentvolumeclaim", name, sandbox.namespace)
        actual = (claim or {}).get("metadata", {}).get("annotations", {})
        if (actual.get("platform.project/scope") != sandbox.scope
                or actual.get("platform.project/operation") != operation):
            raise SandboxError("The retained volume ownership no longer matches its qualified receipt.")

    def _data(self, sandbox, policy, record, previous):
        size = policy.get("data_mib", 0)
        previous_claim = previous.get("data_claim") if previous else None
        if previous_claim is not None:
            self._check_claim(sandbox, previous_claim, previous["data_operation"])
        if record["action"] == "resume":
            if bool(previous_claim) != bool(size):
                raise SandboxError("The retained project data policy changed. Review its current setup before Resume.")
            return previous_claim, previous["data_operation"]
        if not size:
            if previous_claim is not None:
                raise SandboxError("The reviewed update cannot drop existing declared project data.")
            return None, None
        claim = sandbox.volume_name("data")
        self._project_object(sandbox, sandbox.volume("data", size))
        if previous_claim is not None:
            copy = sandbox.copy_retained_data(previous_claim)
            name = copy["metadata"]["name"]
            self._project_object(sandbox, copy)
            self.kube.wait_build(sandbox.namespace, name, sandbox.recipe.build.deadline_seconds)
            self._remove_owned(sandbox, "pod", name, sandbox.operation)
        return claim, sandbox.operation

    def _pair_policies(self, sandbox, runtime):
        if not runtime.get("api_pod_name"):
            return []
        generation = ProjectSandbox(sandbox.scope, runtime["operation_id"], sandbox.recipe)
        return generation.same_project_api_policy(runtime["api_port"])

    def _validate_network(self, sandbox, allowed):
        policies = self.kube.list("networkpolicy", sandbox.namespace)
        if {document["metadata"]["name"] for document in policies} != {document["metadata"]["name"] for document in allowed}:
            raise SandboxError("The project namespace contains a network policy outside the admitted workload configuration.")
        for document in allowed:
            self._project_object(sandbox, document)

    def _remove_policies(self, sandbox, port):
        for document in sandbox.same_project_api_policy(port):
            self._remove_owned(sandbox, "networkpolicy", document["metadata"]["name"], sandbox.operation)

    def _release(self, sandbox, runtime):
        if self.preview is not None:
            self.preview.withdraw(runtime["operation_id"])
        for name in (runtime["pod_name"], runtime.get("api_pod_name")):
            if name:
                self._remove_owned(sandbox, "pod", name, runtime["operation_id"])
        if runtime.get("api_pod_name"):
            previous = ProjectSandbox(sandbox.scope, runtime["operation_id"], sandbox.recipe)
            self._remove_policies(previous, runtime["api_port"])

    def _compute_present(self, sandbox, runtime):
        return any(self.kube.get("pod", name, sandbox.namespace) is not None
                   for name in (runtime["pod_name"], runtime.get("api_pod_name")) if name)

    def _serve(self, sandbox, recipe_id, **values):
        document = sandbox.runtime_pod(recipe_id, **values)
        name = document["metadata"]["name"]
        uid = self._project_object(sandbox, document)["metadata"]["uid"]
        self.kube.wait_ready(sandbox.namespace, name, sandbox.recipe.serve.deadline_seconds)
        actual = self.kube.get("pod", name, sandbox.namespace)
        if not self._ready(actual, uid):
            raise SandboxError("The actual isolated runtime did not report ready.")
        return name, uid, actual

    def _start(self, sandbox, policy, record):
        baseline = sandbox.policy()
        for document in baseline:
            self._project_object(sandbox, document)
        previous = self._previous_receipt(record) if record["previous"] else None
        previous_active = previous is not None and self._compute_present(sandbox, previous)
        allowed = [baseline[-1], *(self._pair_policies(sandbox, previous) if previous_active else [])]
        self._validate_network(sandbox, allowed)
        if record["action"] == "run" and previous_active and previous.get("data_claim"):
            raise SandboxError("Stop the current instance before updating an application with shared project data.")
        if record["action"] == "resume":
            artifact = previous
            self._check_claim(sandbox, artifact["output_claim"], artifact["build_operation"])
        else:
            artifact = self._build(sandbox, policy, record)
        data_claim, data_operation = self._data(sandbox, policy, record, previous)
        recipe_id = record["binding"]["setup"]["recipe_id"]
        serving = {"artifact_claim": artifact["output_claim"], "data_claim": data_claim}
        pair = {}
        if recipe_id == PAIRED_NODE_RECIPE:
            # Apply narrowly scoped policies before either process starts. Only
            # the API receives the reviewed data volume in the paired recipe.
            port = sandbox.recipe.run_port
            for document in sandbox.same_project_api_policy(port):
                self._project_object(sandbox, document)
                allowed.append(document)
            self._validate_network(sandbox, allowed)
            api_name, api_uid, api = self._serve(sandbox, "node-api", **serving)
            api_ip = str(ipaddress.ip_address(api.get("status", {}).get("podIP", "")))
            pair = {"api_pod_name": api_name, "api_pod_uid": api_uid, "api_address": api_ip, "api_port": port}
            serving.update({"api_address": api_ip, "api_port": port, "data_claim": None})
        name, uid, _ = self._serve(sandbox, recipe_id, **serving)
        if pair and not self._api_ready(sandbox, pair):
            raise SandboxError("The bound project API changed before frontend readiness.")
        if record["action"] == "run" and previous:
            try:
                self._release(sandbox, previous)
            except SandboxError:
                # The original transition must be inspected if retirement has
                # applied but cannot be confirmed.
                return self._observation(record, "unknown")
        return self._retain(record, self._observation(record, "ready", artifact_digest=artifact["artifact_digest"],
                            output_claim=artifact["output_claim"], build_operation=artifact["build_operation"],
                            pod_name=name, pod_uid=uid, data_claim=data_claim, data_operation=data_operation,
                            instance_ref=f"project-runtime:{sandbox.namespace}/{name}",
                            owner_receipt_ref=f"platform-project-receipt:{sandbox.generation}", **pair))

    def _api_ready(self, sandbox, runtime):
        if not runtime.get("api_pod_name"):
            return True
        api = self.kube.get("pod", runtime["api_pod_name"], sandbox.namespace)
        return (self._ready(api, runtime["api_pod_uid"])
                and api.get("status", {}).get("podIP") == runtime["api_address"])

    def browser_address(self, record, receipt):
        if self.preview is None:
            return None

        def target():
            try:
                sandbox, _ = self._sandbox(record)
                actual = self.kube.get("pod", receipt["pod_name"], sandbox.namespace)
                if self._ready(actual, receipt["pod_uid"]) and self._api_ready(sandbox, receipt):
                    address = ipaddress.ip_address(actual["status"]["podIP"])
                    if address.is_private and not (address.is_loopback or address.is_link_local or address.is_unspecified):
                        return str(address), sandbox.recipe.run_port
            except (OSError, ValueError, SandboxError, KeyError):
                pass
            return None

        if target() is None:
            self.preview.withdraw(record["operation_id"])
            return None
        try:
            return self.preview.expose(record["binding"]["scope_digest"], record["operation_id"], target)
        except OSError:
            return None

    @staticmethod
    def _ready(pod, uid):
        return (isinstance(pod, dict) and pod.get("metadata", {}).get("uid") == uid
                and pod.get("status", {}).get("phase") == "Running"
                and any(item.get("type") == "Ready" and item.get("status") == "True"
                        for item in pod.get("status", {}).get("conditions", [])))

    def start(self, record):
        sandbox, policy = self._sandbox(record)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if record["action"] == "stop":
            prior = self._previous_receipt(record)
            self._release(sandbox, prior)
            return self._retain(record, self._observation(record, "stopped", compute_released=True))
        try:
            return self._start(sandbox, policy, record)
        except (OSError, ValueError, SandboxError, tarfile.TarError) as error:
            for role in ("frontend", "api", "data-copy", "artifact-reader", "build", "transfer"):
                self._remove_owned(sandbox, "pod", f"{role}-{sandbox.generation}", sandbox.operation)
            if record["binding"]["setup"]["recipe_id"] == PAIRED_NODE_RECIPE:
                self._remove_policies(sandbox, sandbox.recipe.run_port)
            if record["action"] == "run":
                for role in ("input", "dependencies", "build", "data"):
                    self._remove_owned(sandbox, "persistentvolumeclaim", sandbox.volume_name(role), sandbox.operation)
            return self._retain(record, self._observation(record, "failed", compute_released=True,
                                failure_kind=type(error).__name__,
                                failure_detail=str(error) if isinstance(error, SandboxError) else None))

    def read(self, record):
        sandbox, _ = self._sandbox(record)
        try:
            result = json.loads(self._receipt(record["operation_id"]).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            if record["action"] == "stop":
                prior = self._previous_receipt(record)
                if not self._compute_present(sandbox, prior) and not any(
                        self.kube.get("networkpolicy", item["metadata"]["name"], sandbox.namespace)
                        for item in self._pair_policies(sandbox, prior)):
                    return self._observation(record, "stopped", compute_released=True)
            return self._observation(record, "unknown")
        if result.get("state") == "ready" and (
                not self._ready(self.kube.get("pod", result["pod_name"], sandbox.namespace), result["pod_uid"])
                or not self._api_ready(sandbox, result)):
            return self._observation(record, "unknown")
        return result
