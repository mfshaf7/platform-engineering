"""Bound the authenticated OOS handoff to a reviewed Platform installation."""

from __future__ import annotations

from contextlib import nullcontext
import json
from pathlib import Path
import threading

from agent_source_instance import digest, invalid_constant, strict_object
from console_project_runtime_driver import K3sProjectClient, ProjectSandboxDriver
from console_project_runtime_operations import ProjectRuntimeError, ProjectRuntimeOperations
from console_project_runtime_sandbox import SandboxRecipe, WorkloadLimits
from console_project_runtime_setup import scope_key
from console_project_runtime_snapshot import bounded_file, directory_fd, matches_digest
from console_artifact_recovery import RecoveryDeferred


ACTION_PATHS = {
    "/v1/console-operations/project-runtime/run": "submit",
    "/v1/console-operations/project-runtime/read": "read",
    "/v1/console-operations/project-runtime/setup/read": "read_setup",
    "/v1/console-operations/project-runtime/control": "control",
}
INPUT_BYTES = 32768


class ProjectRuntimeProvider:
    def __init__(self, lifecycle, *, admit, source_limits, owner_guard=nullcontext):
        self.lifecycle = lifecycle
        self.admit = admit
        if not isinstance(source_limits, dict) or any(
                type(source_limits.get(key)) is not int or not 0 < source_limits[key] <= 9007199254740991
                for key in ("max_files", "max_bytes")):
            raise ProjectRuntimeError("The reviewed project source limits are invalid.")
        self.capture_limits = {key: source_limits[key] for key in ("max_files", "max_bytes")}
        self.owner_guard = owner_guard
        self.workers = set()
        self.worker_lock = threading.Lock()

    @classmethod
    def from_policy(cls, policy, store, *, owner_guard=nullcontext):
        configured = policy.get("project_runtime")
        if not isinstance(configured, dict) or configured.get("enabled") is not True:
            return None
        security_digest = policy.get("security", {}).get("decision_digest")
        if not matches_digest(security_digest) or configured.get("security_decision_digest") != security_digest:
            raise ProjectRuntimeError("Project runtime requires its exact Platform Security approval.")
        private = Path(policy["runtime_state_root"]) / "project-runtime"
        snapshot_root = private / "snapshots"
        cache_root = private / "approved-dependencies"
        recipe_fields = configured.get("recipe")
        if not isinstance(recipe_fields, dict):
            raise ProjectRuntimeError("The reviewed project runtime recipe is unavailable.")
        try:
            recipe = SandboxRecipe(image=recipe_fields["image"], transfer_image=recipe_fields["transfer_image"],
                build=WorkloadLimits(**recipe_fields["build"]), serve=WorkloadLimits(**recipe_fields["serve"]),
                aggregate=WorkloadLimits(**recipe_fields["aggregate"]), storage_mib=recipe_fields["storage_mib"],
                output_mib=recipe_fields["output_mib"], run_port=recipe_fields["run_port"])
            limits = {key: configured[key] for key in ("source_limits", "input_mib", "cache_mib", "cache_bytes", "cache_expanded_bytes")}
        except (KeyError, TypeError, ValueError) as error:
            raise ProjectRuntimeError("The reviewed project runtime input limits are invalid.") from error

        def admitted(scope):
            identity = scope_key(scope)
            try:
                with directory_fd(private / "admitted-scopes") as directory:
                    with bounded_file(directory, f"{identity}.json", INPUT_BYTES) as (stream, size):
                        raw = stream.read(INPUT_BYTES + 1)
                if len(raw) != size:
                    raise ValueError("changed admission")
                record = json.loads(raw, object_pairs_hook=strict_object, parse_constant=invalid_constant)
            except (OSError, ValueError) as error:
                raise ProjectRuntimeError("The current Platform project admission is unavailable.") from error
            if (not isinstance(record, dict) or record.get("scope") != scope or record.get("security_decision_digest") != security_digest
                    or record.get("visibility") != "internal" or record.get("lane") != "local-dev-integration"
                    or not isinstance(record.get("project_ref"), str) or not isinstance(record.get("subject"), dict)
                    or type(record.get("data_mib")) is not int or not 0 <= record["data_mib"] <= recipe.storage_mib):
                raise ProjectRuntimeError("Project admission does not match this exact local Dev Integration scope.")
            return record

        def authorize(record):
            binding = record["binding"]
            admission = admitted(binding["scope"])
            if admission["project_ref"] != binding["project_ref"] or admission["subject"] != binding["subject"]:
                raise ProjectRuntimeError("Project runtime authority changed before dispatch.")
            return {"recipe": recipe, **limits, "data_mib": admission["data_mib"]}

        def approved_dependencies(binding, lock_digest, image):
            identity = digest({"recipe": binding["setup"]["recipe_id"], "image": image, "lock_digest": lock_digest})
            try:
                with directory_fd(private / "dependency-approvals") as directory:
                    with bounded_file(directory, f"{identity[7:]}.json", INPUT_BYTES) as (stream, size):
                        raw = stream.read(INPUT_BYTES + 1)
                record = json.loads(raw, object_pairs_hook=strict_object, parse_constant=invalid_constant)
            except (OSError, ValueError):
                return None
            if (len(raw) != size or not isinstance(record, dict) or record.get("security_decision_digest") != security_digest
                    or record.get("identity") != identity or not matches_digest(record.get("digest"))
                    or type(record.get("bytes")) is not int):
                return None
            return {key: record[key] for key in ("identity", "digest", "bytes")}

        driver = ProjectSandboxDriver(private / "operations", kube=K3sProjectClient(), snapshot_root=snapshot_root,
                                      cache_root=cache_root, authorize=authorize, dependency_approval=approved_dependencies)
        return cls(ProjectRuntimeOperations(store, driver=driver), admit=admitted,
                   source_limits=limits["source_limits"], owner_guard=owner_guard)

    def _start_retained(self, scope, result):
        if result["state"] == "preparing":
            # `advance` owns the once-only claim under the existing Platform lock.
            # The HTTP response reports the durable acknowledgement immediately.
            command, operation = result["command_id"], result["operation_id"]
            with self.worker_lock:
                if operation not in self.workers:
                    self.workers.add(operation)
                    worker = threading.Thread(target=self._run, args=(scope, command, operation), daemon=True)
                    try:
                        worker.start()
                    except RuntimeError:
                        self.workers.remove(operation)
                        raise
        return result

    def _run(self, scope, command, operation):
        try:
            with self.owner_guard():
                self.lifecycle.advance(scope, command, operation)
        except (OSError, ValueError, RecoveryDeferred):
            # Preserve the original reservation when the owner was unavailable
            # before dispatch. A read can report uncertainty without resubmitting.
            pass
        finally:
            with self.worker_lock:
                self.workers.discard(operation)

    def submit(self, binding):
        if not isinstance(binding, dict) or not isinstance(binding.get("scope"), dict):
            raise ProjectRuntimeError("A complete owner-bound project command is required.")
        admission = self.admit(binding["scope"])
        if admission["project_ref"] != binding.get("project_ref") or admission["subject"] != binding.get("subject"):
            raise ProjectRuntimeError("The broker project does not match the current Platform admission.")
        return self._start_retained(binding["scope"], self.lifecycle.accept_run(binding))

    def read_setup(self, value):
        if (not isinstance(value, dict) or value.keys() != {"scope", "project_ref", "subject"}
                or not isinstance(value["project_ref"], str) or not isinstance(value["subject"], dict)):
            raise ProjectRuntimeError("Read the setup for one exact admitted project subject.")
        scope = value["scope"]
        admission = self.admit(scope)
        if admission["project_ref"] != value["project_ref"] or admission["subject"] != value["subject"]:
            raise ProjectRuntimeError("The broker project does not match the current Platform admission.")
        record = self.lifecycle.setups.read(scope)
        if record is None:
            raise ProjectRuntimeError("No reviewed runtime setup is recorded for this project.")
        return {"project_ref": admission["project_ref"], "subject": admission["subject"],
                "scope": record["scope"], "setup": record["setup"], "limits": self.capture_limits}

    def read(self, value):
        if not isinstance(value, dict) or value.keys() != {"scope", "command_id", "operation_id"}:
            raise ProjectRuntimeError("Read the original owner command for this project.")
        self.admit(value["scope"])
        with self.worker_lock:
            if value["operation_id"] in self.workers:
                return self.lifecycle.read(value["scope"], value["command_id"], value["operation_id"])
        return self.lifecycle.observe(value["scope"], value["command_id"], value["operation_id"])

    def control(self, command):
        if not isinstance(command, dict) or not isinstance(command.get("scope"), dict):
            raise ProjectRuntimeError("Select the exact admitted project before Stop or Resume.")
        self.admit(command["scope"])
        return self._start_retained(command["scope"], self.lifecycle.accept_control(command))
