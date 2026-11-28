"""Platform ownership and recovery for one installation's project runtime."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
import re
import stat
from typing import Any

from agent_source_identity import write_json_atomic
from agent_source_instance import digest, invalid_constant, strict_object
from console_project_runtime_setup import ProjectSetupStore, scope_key
from console_project_runtime_snapshot import matches_digest, validate_binding


IDENTIFIER = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9:._-]{0,255}")
REFERENCE = re.compile(r"[a-zA-Z][a-zA-Z0-9:._/%-]{0,511}")
OPERATION = re.compile(r"project-operation:[a-f0-9]{64}")
RUN_FIELDS = {"command_id", "operation_id", "project_ref", "scope", "scope_digest", "scope_revision",
              "subject", "source", "setup", "snapshot"}
CONTROL_FIELDS = {"command_id", "operation_id", "action", "scope", "expected_revision"}
LIMIT = 8 * 1024 * 1024


class ProjectRuntimeError(ValueError):
    """Platform cannot safely apply this operation."""


def identifier(value: Any, pattern=IDENTIFIER) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class ProjectRuntimeOperations:
    """Use the existing OperationStore lock and private storage for project intent.

    The owner driver receives only a retained, currently admitted operation.
    Its `start` submits the first effect, while `read` observes the same
    operation and never creates or deletes a workload.
    """

    def __init__(self, operations, *, driver, clock=timestamp, browser_address=None):
        self.operations = operations
        self.setups = ProjectSetupStore(operations)
        self.directory = operations.root / "project-runtime"
        self.driver = driver
        self.clock = clock
        self.browser_address = browser_address

    def _path(self, scope):
        key = digest(scope["installation_id"])[7:]
        return self.directory / f"{key}.json"

    def _load(self, scope):
        try:
            fd = os.open(self._path(scope), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        except FileNotFoundError:
            return {"version": 1, "active_scope": None, "projects": {}, "commands": {}}
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > LIMIT:
                raise ProjectRuntimeError("The retained Platform runtime journal is unsafe or exceeds its limit.")
            value = stream.read(LIMIT + 1)
        if len(value) > LIMIT:
            raise ProjectRuntimeError("The retained Platform runtime journal exceeds its read limit.")
        try:
            state = json.loads(value, object_pairs_hook=strict_object, parse_constant=invalid_constant)
        except (ValueError, RecursionError):
            raise ProjectRuntimeError("The retained Platform runtime journal is unreadable.") from None
        if (not isinstance(state, dict) or state.get("version") != 1
                or not isinstance(state.get("projects"), dict) or not isinstance(state.get("commands"), dict)
                or (state.get("active_scope") is not None and state["active_scope"] not in state["projects"])):
            raise ProjectRuntimeError("The retained Platform runtime journal is invalid.")
        return state

    def _write(self, scope, state):
        if len(json.dumps(state, ensure_ascii=True, separators=(",", ":")).encode()) > LIMIT - 1:
            raise ProjectRuntimeError("The Platform runtime journal is full. Retain existing work during recovery.")
        write_json_atomic(self._path(scope), state)

    def _lock(self, scope):
        return self.operations.lock(f"project-runtime-installation:{self._path(scope).stem}")

    def _setup_current(self, binding):
        setup = self.setups.read(binding["scope"])
        if setup is None or setup["setup"] != binding["setup"]:
            raise ProjectRuntimeError("Project setup changed. Read current setup before requesting another build.")
        if setup["setup"]["recipe_id"] == "no-runtime":
            raise ProjectRuntimeError("This project setup does not run a workload.")

    def _new_project(self):
        return {"revision": 0, "source_revision": 0, "current_command": None,
                "qualified": None, "state": "stopped"}

    def _existing(self, state, command):
        record = state["commands"].get(command["command_id"])
        if record is not None and record["input_digest"] != digest(command):
            raise ProjectRuntimeError("This command ID already names a different project operation.")
        if record is None and any(row["operation_id"] == command["operation_id"] for row in state["commands"].values()):
            raise ProjectRuntimeError("This operation ID is already bound to another command.")
        return record

    def accept_run(self, binding):
        try:
            if not isinstance(binding, dict) or binding.keys() != RUN_FIELDS:
                raise ProjectRuntimeError("A complete broker run command is required.")
            validate_binding(binding)
        except (KeyError, TypeError, ValueError) as error:
            raise ProjectRuntimeError("A valid broker run command is required.") from error
        subject = binding["subject"]
        if (not identifier(binding["command_id"]) or not identifier(binding["project_ref"])
                or not identifier(binding["operation_id"], OPERATION)
                or type(binding["scope_revision"]) is not int or not 0 < binding["scope_revision"] <= 2**53 - 1
                or not isinstance(subject, dict) or subject.keys() != {"kind", "ref"}
                or subject["kind"] not in ("prototype", "delivery") or not identifier(subject["ref"])
                or binding["source"]["kind"] != "saved-draft"):
            raise ProjectRuntimeError("The broker run does not bind an admitted saved source and revision.")
        scope = binding["scope"]
        key = scope_key(scope)
        with self._lock(scope), self.operations.lock(f"project-runtime-scope:{key}"):
            state = self._load(scope)
            existing = self._existing(state, binding)
            if existing:
                return self._current_projection(existing, state["projects"][key])
            self._setup_current(binding)
            project = state["projects"].setdefault(key, self._new_project())
            self._check_capacity(state, key, project)
            if binding["scope_revision"] <= project["source_revision"]:
                raise ProjectRuntimeError("The saved-source command is older than the last admitted command.")
            project["source_revision"] = binding["scope_revision"]
            return self._retain(state, key, project, binding, "run", binding)

    def accept_control(self, command):
        if (not isinstance(command, dict) or command.keys() != CONTROL_FIELDS
                or not identifier(command["command_id"]) or not identifier(command["operation_id"], OPERATION)
                or command["action"] not in ("stop", "resume") or type(command["expected_revision"]) is not int):
            raise ProjectRuntimeError("Choose Stop or Resume for the current project revision.")
        scope = command["scope"]
        key = scope_key(scope)
        with self._lock(scope), self.operations.lock(f"project-runtime-scope:{key}"):
            state = self._load(scope)
            existing = self._existing(state, command)
            if existing:
                return self._current_projection(existing, state["projects"][key])
            project = state["projects"].get(key)
            if project is None or project["revision"] != command["expected_revision"]:
                raise ProjectRuntimeError("Project runtime state changed. Read the latest state before acting.")
            self._check_capacity(state, key, project)
            qualified = project["qualified"]
            if qualified is None or qualified["binding"]["scope"] != scope:
                raise ProjectRuntimeError("No preserved build exists for the admitted project scope.")
            action = command["action"]
            if (action == "resume" and project["state"] != "stopped") or (action == "stop" and project["state"] != "ready"):
                raise ProjectRuntimeError("The current project state cannot perform this action.")
            if action == "resume":
                self._setup_current(qualified["binding"])
            return self._retain(state, key, project, command, action, qualified["binding"])

    def _check_capacity(self, state, key, project):
        if state["active_scope"] not in (None, key):
            raise ProjectRuntimeError("Stop the current project before running another project on this installation.")
        current = state["commands"].get(project["current_command"])
        if current and current["state"] not in ("ready", "failed", "stopped"):
            raise ProjectRuntimeError("Read the original project operation before starting another action.")

    def _retain(self, state, key, project, command, action, binding):
        if project["qualified"] and project["qualified"]["binding"]["scope"] != binding["scope"]:
            raise ProjectRuntimeError("The existing runtime data belongs to a different admitted scope.")
        project["revision"] += 1
        project["current_command"] = command["command_id"]
        record = {
            "action": action, "operation_id": command["operation_id"], "command_id": command["command_id"],
            "input_digest": digest(command), "binding": binding, "state": "preparing", "dispatched": False,
            "observed_at": self.clock(), "revision": project["revision"], "observation": None,
            "previous": project["qualified"],
        }
        state["commands"][record["command_id"]] = record
        state["active_scope"] = key
        self._write(binding["scope"], state)
        return self._projection(record)

    def _projection(self, record):
        binding = record["binding"]
        return {"operation_id": record["operation_id"], "command_id": record["command_id"],
                "scope_digest": binding["scope_digest"], "manifest_digest": binding["snapshot"]["manifest_digest"],
                "configuration_revision": binding["setup"]["configuration_revision"],
                "state": record["state"], "observed_at": record["observed_at"], "revision": record["revision"],
                **{key: value for key, value in (record["observation"] or {}).items()
                   if key in {"instance_ref", "owner_receipt_ref", "endpoint_ref", "log_ref"}}}

    def _current_projection(self, record, project):
        if project["current_command"] != record["command_id"]:
            # Preserve the original binding without advertising a historical instance as running.
            return self._projection({**record, "state": "stale", "observation": None, "observed_at": self.clock()})
        return self._projection(record)

    def read(self, scope, command_id, operation_id):
        state = self._load(scope)
        record = self._record(state, scope, command_id, operation_id)
        return self._current_projection(record, state["projects"][scope_key(scope)])

    def observe(self, scope, command_id, operation_id):
        """Read actual owner state or retain uncertainty. This never submits an effect."""
        key = scope_key(scope)
        state = self._load(scope)
        row = self._record(state, scope, command_id, operation_id)
        project = state["projects"][key]
        if project["current_command"] != command_id or row["state"] in ("failed", "stopped"):
            return self._current_projection(row, project)
        observed = None
        try:
            if row["dispatched"]:
                observed = self.driver.read(row)
            observation = self._verify_observation(row, observed)
        except Exception:
            observation = {"state": "unknown"}
        if observation["state"] == "unknown":
            return self._projection({**row, "state": "unknown", "observation": None, "observed_at": self.clock()})
        preview_ready = observation["state"] == "ready" and self.browser_address is not None
        if row["state"] == observation["state"] and not preview_ready:
            return self._projection({**row, "observed_at": self.clock()})
        with self._lock(scope):
            current = self._load(scope)
            row = self._record(current, scope, command_id, operation_id)
            project = current["projects"][key]
            if project["current_command"] != command_id:
                return self._current_projection(row, project)
            if row["state"] not in ("ready", "failed", "stopped"):
                self._finish(current, key, project, row, observation)
            if preview_ready and row["state"] == "ready":
                address = self.browser_address(row, observed)
                current_observation = {key: value for key, value in observation.items() if key != "endpoint_ref"}
                if identifier(address, REFERENCE):
                    current_observation["endpoint_ref"] = address
                return self._projection({**row, "observation": current_observation, "observed_at": self.clock()})
            return self._current_projection(row, project)

    def inspect(self, scope):
        state = self._load(scope)
        project = state["projects"].get(scope_key(scope))
        if project is None:
            return None
        record = state["commands"][project["current_command"]]
        if record["binding"]["scope"] != scope:
            raise ProjectRuntimeError("The current project scope differs from the retained operation.")
        qualified = project["qualified"]
        return {"revision": project["revision"], "last_qualified": None if qualified is None else {
                    "source": qualified["binding"]["source"], "source_manifest_digest": qualified["binding"]["snapshot"]["manifest_digest"],
                    "configuration_revision": qualified["binding"]["setup"]["configuration_revision"],
                    "artifact_digest": qualified["artifact_digest"], "instance_ref": qualified["instance_ref"],
                }, "operation": self._projection(record)}

    def _record(self, state, scope, command_id, operation_id):
        row = state["commands"].get(command_id)
        if row is None or row["operation_id"] != operation_id or row["binding"]["scope"] != scope:
            raise ProjectRuntimeError("No original operation exists for this admitted project scope.")
        return row

    def advance(self, scope, command_id, operation_id):
        """Submit once, or reconcile from the owner's actual observation."""
        key = scope_key(scope)
        with self._lock(scope), self.operations.lock(f"project-runtime-scope:{key}"):
            state = self._load(scope)
            row = self._record(state, scope, command_id, operation_id)
            project = state["projects"][key]
            if project["current_command"] != command_id or row["state"] in ("ready", "failed", "stopped"):
                return self._current_projection(row, project)
            if not row["dispatched"] and row["action"] in ("run", "resume"):
                try:
                    self._setup_current(row["binding"])
                except (ValueError, OSError):
                    self._finish(state, key, project, row, {"state": "failed"})
                    return self._projection(row)
            dispatched = row["dispatched"]
            if not dispatched:
                row["dispatched"] = True
                row["observed_at"] = self.clock()
                self._write(scope, state)
            # Preserve another process's first-effect claim while the driver reads.
            # Holding this lock also prevents another setup write during initial dispatch.
            try:
                observation = self.driver.read(row) if dispatched else self.driver.start(row)
                verified = self._verify_observation(row, observation)
            except Exception:
                verified = {"state": "unknown"}
            self._finish(state, key, project, row, verified)
            return self._projection(row)

    def _verify_observation(self, row, observation):
        expected = self._projection(row)
        bind = {"operation_id", "command_id", "scope_digest", "manifest_digest", "configuration_revision"}
        if not isinstance(observation, dict) or any(observation.get(key) != expected[key] for key in bind):
            return {"state": "unknown"}
        phase = observation.get("state")
        allowed = {"preparing", "building", "starting", "ready", "failed", "unknown"}
        if row["action"] == "stop":
            allowed = {"preparing", "stopped", "failed", "unknown"}
        if not isinstance(phase, str) or phase not in allowed:
            return {"state": "unknown"}
        result = {"state": phase}
        for key in ("instance_ref", "owner_receipt_ref", "endpoint_ref", "log_ref"):
            if identifier(observation.get(key), REFERENCE):
                result[key] = observation[key]
        if phase == "ready":
            artifact = observation.get("artifact_digest")
            if not matches_digest(artifact) or not {"instance_ref", "owner_receipt_ref"}.issubset(result):
                return {"state": "unknown"}
            if row["action"] == "resume" and artifact != row["previous"]["artifact_digest"]:
                return {"state": "unknown"}
            result["artifact_digest"] = artifact
        if phase in ("failed", "stopped") and observation.get("compute_released") is not True:
            return {"state": "unknown"}
        return result

    def _finish(self, state, key, project, row, observation):
        phase = observation["state"]
        row["state"] = phase
        row["observed_at"] = self.clock()
        row["observation"] = observation
        if phase == "ready":
            project["state"] = "ready"
            project["qualified"] = {"binding": row["binding"], "artifact_digest": observation["artifact_digest"],
                                    "instance_ref": observation["instance_ref"], "operation_id": row["operation_id"]}
        if phase == "stopped" or (phase == "failed" and project["state"] != "ready"):
            state["active_scope"] = None
            project["state"] = "stopped"
        self._write(row["binding"]["scope"], state)
