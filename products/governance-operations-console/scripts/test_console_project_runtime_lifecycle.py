"""Focused owner contracts for exact builds, sandbox policy, and lifecycle."""

from copy import deepcopy
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import unittest
from unittest.mock import patch

import platform_operation_provider as platform
from platform_operation_provider import OperationStore
from agent_source_instance import digest
from console_project_runtime_artifacts import ProjectArtifactError, copy_verified_dependencies, qualify_build
from console_project_runtime_driver import K3sProjectClient, ProjectSandboxDriver, SandboxError
from console_project_runtime_operations import ProjectRuntimeError, ProjectRuntimeOperations
from console_project_runtime_provider import ProjectRuntimeProvider
from console_project_runtime_sandbox import ProjectSandbox, SandboxRecipe, WorkloadLimits
from console_project_runtime_setup import ProjectSetupStore, scope_key


IMAGE = "node@sha256:" + "1" * 64
ARTIFACT = "sha256:" + "2" * 64
BOUND = ("operation_id", "command_id", "scope_digest", "manifest_digest", "configuration_revision")


class Driver:
    """Exercise owner journaling independently of Kubernetes."""

    def __init__(self):
        self.submissions = []
        self.owner_reply = None
        self.fail_next = False

    def start(self, record):
        self.submissions.append(deepcopy(record))
        if self.fail_next:
            self.fail_next = False
            raise TimeoutError("reply lost")
        return self.owner_reply

    def read(self, _record):
        return self.owner_reply


class ProjectLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.operations = OperationStore(self.root / "owner")
        self.driver = Driver()
        self.lifecycle = ProjectRuntimeOperations(self.operations, driver=self.driver)
        self.scope = {"installation_id": "local", "project_custody_ref": "project:root",
                      "repository_id": 42, "app_root": ".", "dependency_paths": [], "environment_ref": "devint:proof"}
        self.create_setup(self.scope)

    def create_setup(self, scope, recipe="static", expected=None):
        class Source:
            commit = "1" * 40

            def require_file(self, name):
                assert name == "index.html"

        return ProjectSetupStore(self.operations).save(scope, requested_app_root=".", recipe_id=recipe,
                                                      expected_revision=expected, source=Source())

    def run_binding(self, sequence=1, scope=None):
        scope = scope or self.scope
        setup = ProjectSetupStore(self.operations).read(scope)["setup"]
        manifest = hashlib.sha256(str(sequence).encode()).hexdigest()
        return {"command_id": f"run:{sequence}", "operation_id": f"project-operation:{manifest}",
                "project_ref": scope["project_custody_ref"], "scope": scope, "scope_digest": f"sha256:{scope_key(scope)}",
                "scope_revision": sequence, "subject": {"kind": "delivery", "ref": "work-item-42"},
                "source": {"kind": "saved-draft", "base_commit": "1" * 40, "session_id": "source:session",
                           "revision": f"draft:{sequence}", "change_set_digest": "sha256:" + "3" * 64},
                "setup": setup, "snapshot": {"snapshot_id": f"project-source:{manifest}", "manifest_digest": f"sha256:{manifest}"}}

    def control(self, action, revision):
        operation = hashlib.sha256(f"{action}:{revision}".encode()).hexdigest()
        return {"command_id": f"control:{action}", "operation_id": f"project-operation:{operation}",
                "action": action, "scope": self.scope, "expected_revision": revision}

    def reply(self, acknowledgement, state, **extra):
        self.driver.owner_reply = {**{name: acknowledgement[name] for name in BOUND}, "state": state, **extra}

    def advance(self, accepted):
        return self.lifecycle.advance(self.scope, accepted["command_id"], accepted["operation_id"])

    def qualify(self, accepted, artifact=ARTIFACT):
        self.reply(accepted, "ready", artifact_digest=artifact, instance_ref="project:instance", owner_receipt_ref="owner:receipt")
        return self.advance(accepted)

    def test_retained_intent_and_lost_reply_reconcile_once(self):
        binding = self.run_binding()
        accepted = self.lifecycle.accept_run(binding)
        self.assertEqual(self.driver.submissions, [])
        self.driver.fail_next = True
        self.assertEqual(self.advance(accepted)["state"], "unknown")
        self.lifecycle = ProjectRuntimeOperations(OperationStore(self.operations.root), driver=self.driver)
        self.assertEqual(self.lifecycle.accept_run(binding)["state"], "unknown")
        self.assertEqual(self.qualify(accepted)["state"], "ready")
        self.assertEqual(len(self.driver.submissions), 1)
        with self.assertRaisesRegex(ProjectRuntimeError, "different project operation"):
            self.lifecycle.accept_run({**binding, "project_ref": "project:replaced"})

    def test_stop_resume_preserve_data_and_require_the_same_qualified_artifact(self):
        started = self.lifecycle.accept_run(self.run_binding())
        self.qualify(started)
        data = self.root / "project-data"
        data.write_bytes(b"existing data")
        stopped = self.lifecycle.accept_control(self.control("stop", started["revision"]))
        self.reply(stopped, "stopped", compute_released=True)
        self.assertEqual(self.advance(stopped)["state"], "stopped")

        original = (self.scope, started["command_id"], started["operation_id"])
        for read in (self.lifecycle.observe, self.lifecycle.read, self.lifecycle.advance):
            historical = read(*original)
            self.assertEqual(historical["state"], "stale")
            self.assertEqual(historical["manifest_digest"], started["manifest_digest"])
            self.assertNotIn("instance_ref", historical)
        self.assertEqual(self.lifecycle.accept_run(self.run_binding())["state"], "stale")
        self.assertEqual(self.lifecycle.inspect(self.scope)["operation"]["state"], "stopped")
        self.assertEqual(self.lifecycle.inspect(self.scope)["last_qualified"]["artifact_digest"], ARTIFACT)
        with self.assertRaisesRegex(ProjectRuntimeError, "latest state"):
            self.lifecycle.accept_control(self.control("resume", started["revision"]))
        with self.assertRaisesRegex(ProjectRuntimeError, "Stop or Resume"):
            self.lifecycle.accept_control(self.control("reset", stopped["revision"]))
        resumed = self.lifecycle.accept_control(self.control("resume", stopped["revision"]))
        self.assertEqual(self.qualify(resumed, "sha256:" + "7" * 64)["state"], "unknown")
        self.assertEqual(self.qualify(resumed)["state"], "ready")
        self.assertEqual(data.read_bytes(), b"existing data")
        self.assertEqual([row["action"] for row in self.driver.submissions], ["run", "stop", "resume"])

    def test_failed_update_keeps_prior_build_and_one_active_project(self):
        original = self.lifecycle.accept_run(self.run_binding())
        self.qualify(original)
        other = {**self.scope, "project_custody_ref": "project:other", "repository_id": 43}
        self.create_setup(other)
        with self.assertRaisesRegex(ProjectRuntimeError, "Stop the current project"):
            self.lifecycle.accept_run(self.run_binding(2, other))
        update = self.lifecycle.accept_run(self.run_binding(2))
        self.reply(update, "failed", compute_released=True)
        self.assertEqual(self.advance(update)["state"], "failed")
        project = self.lifecycle.inspect(self.scope)
        self.assertEqual(project["last_qualified"]["source_manifest_digest"], original["manifest_digest"])
        self.assertNotEqual(project["last_qualified"]["source_manifest_digest"], update["manifest_digest"])
        with self.assertRaisesRegex(ProjectRuntimeError, "older than"):
            older = self.run_binding()
            self.lifecycle.accept_run({**older, "command_id": "run:stale", "operation_id": "project-operation:" + "a" * 64})

    def test_setup_change_between_acceptance_and_dispatch_has_no_effect(self):
        binding = self.run_binding()
        accepted = self.lifecycle.accept_run(binding)
        self.create_setup(self.scope, recipe="no-runtime", expected=binding["setup"]["configuration_revision"])
        self.assertEqual(self.advance(accepted)["state"], "failed")
        self.assertEqual(self.driver.submissions, [])

    def test_authenticated_platform_route_retains_run_and_reads_original_state(self):
        binding = self.run_binding()
        self.assertIsNone(ProjectRuntimeProvider.from_policy({}, self.operations))
        service = SimpleNamespace(policy={"runtime_state_root": str(self.root)}, source_version="candidate",
            project_runtime=ProjectRuntimeProvider(self.lifecycle, admit=lambda _scope: {
                "project_ref": binding["project_ref"], "subject": binding["subject"],
            }))
        self.driver.owner_reply = {"operation_id": binding["operation_id"], "command_id": binding["command_id"],
            "scope_digest": binding["scope_digest"], "manifest_digest": binding["snapshot"]["manifest_digest"],
            "configuration_revision": binding["setup"]["configuration_revision"], "state": "ready",
            "artifact_digest": ARTIFACT, "instance_ref": "project:instance", "owner_receipt_ref": "owner:receipt"}
        credential = "a" * 32
        with patch.object(platform, "activation_is_current", return_value=True), \
             patch.object(platform.artifact_recovery, "blocked", return_value=None), \
             ThreadingHTTPServer(("127.0.0.1", 0), platform.handler_for(service, "broker", credential)) as server:
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            def request(action, value, secret=credential):
                route = f"http://127.0.0.1:{server.server_port}/v1/console-operations/project-runtime/{action}"
                enquiry = Request(route, json.dumps(value).encode(), headers={"Content-Type": "application/json",
                    "X-Platform-Caller-Id": "broker", "X-Platform-Caller-Secret": secret}, method="POST")
                with urlopen(enquiry, timeout=2) as response:
                    return response.status, json.load(response)

            try:
                with self.assertRaises(HTTPError) as rejected:
                    request("run", binding, secret="incorrect-credential")
                self.assertEqual(rejected.exception.code, 403)
                status, accepted = request("run", binding)
                self.assertEqual(status, 202)
                self.assertEqual(accepted["state"], "preparing")
                query = {key: binding[key] for key in ("scope", "command_id", "operation_id")}
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    status, observed = request("read", query)
                    if observed["state"] == "ready":
                        break
                    time.sleep(0.02)
                self.assertEqual(status, 200)
                self.assertEqual(observed["state"], "ready")
                self.assertEqual(observed["operation_id"], accepted["operation_id"])
                self.assertEqual(request("run", binding)[1]["state"], "ready")
                self.assertEqual(len(self.driver.submissions), 1)
            finally:
                server.shutdown()
                thread.join(timeout=2)


class ProjectSandboxTests(unittest.TestCase):
    def setUp(self):
        build = WorkloadLimits(1500, 768, 1024, 600)
        serve = WorkloadLimits(400, 256, 256, 3600)
        aggregate = WorkloadLimits(1900, 1024, 1280, 3600)
        self.recipe = SandboxRecipe(IMAGE, IMAGE, build, serve, aggregate, 6144, 512)
        self.sandbox = ProjectSandbox("sha256:" + "a" * 64, "project-operation:" + "b" * 64, self.recipe)

    def test_pods_have_no_host_access_and_network_policy_is_same_project_only(self):
        build = self.sandbox.build_pod("node-frontend", "apps/web")
        artifact = self.sandbox.volume_name("build")
        runtime = self.sandbox.runtime_pod("node-frontend", artifact_claim=artifact, data_claim=self.sandbox.volume_name("data"),
                                           api_address="10.40.0.5", api_port=3000)
        for pod in (self.sandbox.transfer_pod(), build, runtime):
            spec = pod["spec"]
            container = spec["containers"][0]
            self.assertFalse(spec["automountServiceAccountToken"])
            self.assertFalse(any(spec.get(name) for name in ("hostNetwork", "hostPID", "hostIPC")))
            self.assertTrue(spec["securityContext"]["runAsNonRoot"])
            self.assertEqual(spec["securityContext"]["seccompProfile"]["type"], "RuntimeDefault")
            self.assertFalse(container["securityContext"]["allowPrivilegeEscalation"])
            self.assertEqual(container["securityContext"]["capabilities"]["drop"], ["ALL"])
            self.assertNotIn("envFrom", container)
            self.assertTrue(all(not {"hostPath", "secret"}.intersection(volume) for volume in spec["volumes"]))
            self.assertIn("ephemeral-storage", container["resources"]["limits"])
        self.assertIn("--offline", build["spec"]["containers"][0]["command"][2])
        self.assertEqual([volume["name"] for volume in runtime["spec"]["volumes"]], ["build", "data", "temporary"])
        namespace, quota, policy = self.sandbox.policy()
        self.assertEqual(namespace["metadata"]["labels"]["pod-security.kubernetes.io/enforce"], "restricted")
        self.assertEqual(quota["spec"]["hard"]["limits.memory"], "1Gi")
        self.assertEqual(quota["spec"]["hard"]["requests.storage"], "6Gi")
        self.assertEqual(WorkloadLimits(1000, 1024, 2048, 60).quantities(),
                         {"cpu": "1", "memory": "1Gi", "ephemeral-storage": "2Gi"})
        self.assertEqual(policy["spec"]["ingress"], [])
        self.assertEqual(policy["spec"]["egress"], [])
        ingress, egress = self.sandbox.same_project_api_policy(3000)
        generation = {"platform.project/generation": self.sandbox.generation}
        frontend = {"matchLabels": {"platform.project/role": "frontend", **generation}}
        api = {"matchLabels": {"platform.project/role": "api", **generation}}
        self.assertEqual(ingress["spec"]["podSelector"], api)
        self.assertEqual(ingress["spec"]["ingress"][0]["from"], [{"podSelector": frontend}])
        self.assertEqual(egress["spec"]["podSelector"], frontend)
        self.assertEqual(egress["spec"]["egress"][0]["to"], [{"podSelector": api}])
        self.assertEqual(quota["spec"]["hard"]["pods"], "4")

    def test_paired_frontend_uses_the_approved_build_and_bound_api(self):
        artifact = self.sandbox.volume_name("build")
        with self.assertRaisesRegex(ValueError, "verified API endpoint"):
            self.sandbox.runtime_pod("node-frontend-api", artifact_claim=artifact)
        frontend = self.sandbox.runtime_pod("node-frontend-api", artifact_claim=artifact, api_address="10.40.0.5", api_port=3000)
        container = frontend["spec"]["containers"][0]
        self.assertEqual(container["command"], ["npm", "--prefix", "/project-build", "run", "start:frontend"])
        self.assertIn({"name": "PROJECT_API_ORIGIN", "value": "http://10.40.0.5:3000"}, container["env"])
        self.assertEqual(frontend["metadata"]["labels"]["platform.project/generation"], self.sandbox.generation)

    def test_update_clones_retained_data_read_only_into_the_new_owner_volume(self):
        prior = "data-" + "d" * 32
        document = self.sandbox.copy_retained_data(prior)
        mounts = document["spec"]["containers"][0]["volumeMounts"]
        volumes = {volume["name"]: volume for volume in document["spec"]["volumes"]}
        self.assertEqual(volumes["previous"]["persistentVolumeClaim"], {"readOnly": True, "claimName": prior})
        self.assertEqual(volumes["data"]["persistentVolumeClaim"], {"readOnly": False, "claimName": self.sandbox.volume_name("data")})
        self.assertTrue(next(mount for mount in mounts if mount["name"] == "previous")["readOnly"])
        self.assertIn("entries=(/previous-data/*)", document["spec"]["containers"][0]["command"][2])

    def test_build_wait_stops_at_the_native_failed_phase(self):
        client = K3sProjectClient()
        with patch.object(client, "get", return_value={"status": {"phase": "Failed"}}) as read:
            with self.assertRaisesRegex(SandboxError, "reported failure"):
                client.wait_build("project", "build", 120)
        read.assert_called_once_with("pod", "build", "project")

    def test_different_projects_get_disjoint_namespaces_and_generic_commands_are_denied(self):
        other = ProjectSandbox("sha256:" + "c" * 64, "project-operation:" + "b" * 64, self.recipe)
        self.assertNotEqual(self.sandbox.namespace, other.namespace)
        with self.assertRaises(ValueError):
            self.sandbox.build_pod("arbitrary", ".")
        with self.assertRaises(ValueError):
            self.sandbox.build_pod("node-api", "../secret")
        with self.assertRaises(ValueError):
            self.sandbox.runtime_pod("static", artifact_claim="arbitrary-pvc")

    def test_resume_accepts_native_empty_rule_projection_and_rejects_broadened_policy(self):
        class Kube:
            def get(self, _kind, _name, _namespace=None):
                return observed

        policy = self.sandbox.policy()[2]
        observed = deepcopy(policy)
        observed["spec"].pop("ingress")
        observed["spec"].pop("egress")
        driver = ProjectSandboxDriver(Path("."), kube=Kube(), snapshot_root=Path("."), cache_root=Path("."),
                                      authorize=None, dependency_approval=None)
        self.assertEqual(driver._project_object(self.sandbox, policy), observed)
        observed["spec"]["egress"] = [{}]
        with self.assertRaises(SandboxError):
            driver._project_object(self.sandbox, policy)


class ProjectArtifactTests(unittest.TestCase):
    def test_dependency_cache_reuse_rehashes_the_bytes_and_binds_the_lock_and_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            cache.mkdir()
            lock = "sha256:" + "a" * 64
            data = b"owner-qualified npm archive"
            content = hashlib.sha256(data).hexdigest()
            compatibility = digest({"recipe": "node-frontend", "image": IMAGE, "lock_digest": lock})
            approved = {"identity": compatibility, "digest": f"sha256:{content}", "bytes": len(data)}
            archive = cache / content
            archive.write_bytes(data)
            target = root / "candidate"
            def copy(path, lock_digest):
                return copy_verified_dependencies(cache, path, recipe="node-frontend", image=IMAGE,
                                                  lock_digest=lock_digest, approved=approved, max_bytes=2048)
            self.assertEqual(copy(target, lock), approved)
            self.assertEqual(target.read_bytes(), data)
            with self.assertRaisesRegex(ProjectArtifactError, "No compatible dependencies"):
                copy(root / "bad-lock", "sha256:" + "b" * 64)
            archive.write_bytes(b"b" * len(data))
            with self.assertRaisesRegex(ProjectArtifactError, "approved digest"):
                copy(root / "changed", lock)
            self.assertFalse((root / "changed").exists())
            self.assertEqual(target.read_bytes(), data)

    def test_a_prior_or_failed_build_cannot_be_relabelled_as_the_new_source(self):
        manifest = "sha256:" + "f" * 64
        binding = {"scope_digest": "sha256:" + "e" * 64, "operation_id": "project-operation:" + "a" * 64,
                   "snapshot": {"manifest_digest": manifest}, "setup": {"configuration_revision": "r2"}}
        claim = "build-" + "a" * 32
        observed = {"uid": "pod-uid", "phase": "Succeeded", "image": IMAGE, "output_claim": claim,
                    "scope_digest": binding["scope_digest"], "operation_id": binding["operation_id"],
                    "manifest_digest": manifest, "configuration_revision": "r2"}

        def qualify(value):
            return qualify_build(binding, expected_uid="pod-uid", image=IMAGE, output_claim=claim,
                                 observed=value, output_digest=ARTIFACT)

        self.assertEqual(qualify(observed)["artifact_digest"], ARTIFACT)
        for change in ({"phase": "Failed"}, {"uid": "older-pod"}, {"configuration_revision": "r1"},
                       {"manifest_digest": "sha256:" + "0" * 64}):
            with self.assertRaisesRegex(ProjectArtifactError, "exact operation"):
                qualify({**observed, **change})


if __name__ == "__main__":
    unittest.main()
