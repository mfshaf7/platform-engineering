"""Private, revisioned operator configuration inside reviewed AI permissions.

Profiles remain the task/data policy. This store cannot add a provider endpoint,
task, caller or credential. The management service supplies verified catalogue
records; clients select those records rather than supplying capabilities.
"""
from __future__ import annotations

from contextlib import contextmanager
import copy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any


class ConfigurationError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode()).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, sort_keys=True, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def locked(path: Path, *, blocking: bool = True):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
        yield
    finally:
        os.close(fd)


def closed(value: Any, keys: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != keys:
        raise ConfigurationError("invalid-command", f"Invalid {label} fields.")


class ModelConfiguration:
    """One atomic state file: configuration, revision history and command receipts.

    Commands are compared before checking their original expected revision, so
    a lost response can be replayed after later edits without another mutation.
    State is local dev-integration custody, not a new shared storage service.
    """
    def __init__(self, root: Path, *, tasks: set[str], backends: dict[str, Any]):
        self.root = root
        self.tasks = set(tasks)
        self.backends = copy.deepcopy(backends)
        self.path = root / "model-configuration.json"

    @staticmethod
    def initial() -> dict[str, Any]:
        configuration = {"backends": {}, "models": {}, "default": None, "overrides": {}}
        return {"schema_version": 1, "revision": 0, "configuration": configuration,
                "history": {"0": configuration}, "commands": {}}

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self.initial()
        try:
            state = json.loads(self.path.read_text())
            if state["schema_version"] != 1 or not isinstance(state["revision"], int):
                raise ValueError()
            # Do not silently reset a damaged journal or discard replay identity.
            if str(state["revision"]) not in state["history"] or not isinstance(state["commands"], dict):
                raise ValueError()
            if digest(state["configuration"]) != digest(state["history"][str(state["revision"])]):
                raise ValueError()
            return state
        except (OSError, KeyError, TypeError, ValueError) as error:
            raise ConfigurationError("configuration-unavailable", "Retained model configuration is unavailable.") from error

    def snapshot(self, revision: int | None = None) -> dict[str, Any]:
        with locked(self.root / "configuration.lock"):
            state = self._read()
            selected = state["revision"] if revision is None else revision
            if type(selected) is not int or str(selected) not in state["history"]:
                raise ConfigurationError("revision-not-found", "Choose an existing configuration revision.")
            configuration = state["history"][str(selected)]
            return {"revision": selected, "current_revision": state["revision"], "digest": digest(configuration),
                    "configuration": copy.deepcopy(configuration), "history": [
                        {"revision": int(key), "digest": digest(state["history"][key])}
                        for key in sorted(state["history"], key=int)]}

    def command_result(self, command: dict[str, Any], *, actor: str):
        """Read an original receipt before any provider discovery/verification."""
        fingerprint = digest({"actor": actor, "command": command})
        with locked(self.root / "configuration.lock"):
            prior = self._read()["commands"].get(command.get("command_id"))
            if prior and prior["command_digest"] != fingerprint:
                raise ConfigurationError("command-conflict", "Command identity already belongs to different content or actor.")
            return copy.deepcopy(prior)

    def command(self, command: dict[str, Any], *, actor: str,
                verified_model: dict[str, Any] | None = None, account_binding=None) -> dict[str, Any]:
        closed(command, {"command_id", "expected_revision", "action", "input"}, "configuration command")
        if not isinstance(actor, str) or not actor or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}", str(command["command_id"])):
            raise ConfigurationError("invalid-command", "Command and actor identity are required.")
        if type(command["expected_revision"]) is not int or command["expected_revision"] < 0:
            raise ConfigurationError("invalid-command", "Expected revision must be a nonnegative integer.")
        fingerprint = digest({"actor": actor, "command": command})
        with locked(self.root / "configuration.lock"):
            state = self._read()
            previous = state["commands"].get(command["command_id"])
            if previous:
                if previous["command_digest"] != fingerprint:
                    raise ConfigurationError("command-conflict", "Command identity already belongs to different content or actor.")
                return copy.deepcopy(previous)
            if state["revision"] != command["expected_revision"]:
                raise ConfigurationError("revision-conflict", "Refresh the current configuration before saving.")
            config = copy.deepcopy(state["configuration"])
            action, payload = command["action"], command["input"]
            if action == "backend.register":
                closed(payload, {"backend_id"}, action)
                key = payload["backend_id"]
                if not isinstance(key, str) or key not in self.backends:
                    raise ConfigurationError("backend-not-admitted", "Backend must be admitted by the Platform owner.")
                config["backends"][key] = {"backend_id": key}
            elif action == "backend.remove":
                closed(payload, {"backend_id"}, action)
                key = payload["backend_id"]
                if not isinstance(key, str) or key not in config["backends"]:
                    raise ConfigurationError("backend-not-registered", "Backend registration does not exist.")
                if any(model["backend_id"] == key for model in config["models"].values()):
                    raise ConfigurationError("backend-in-use", "Remove that backend's model registrations first.")
                del config["backends"][key]
            elif action == "model.register":
                closed(payload, {"backend_id", "model"}, action)
                backend = payload["backend_id"]
                if not isinstance(backend, str) or backend not in self.backends or backend not in config["backends"]:
                    raise ConfigurationError("backend-not-registered", "Register the admitted backend first.")
                # Only the trusted owner service can supply discovered metadata.
                if not verified_model or verified_model.get("backend_id") != backend or verified_model.get("model") != payload["model"]:
                    raise ConfigurationError("model-verification-required", "Discover and verify the exact model through its admitted backend.")
                model_id = digest({"backend_id": backend, "model": payload["model"]})
                config["models"][model_id] = copy.deepcopy(verified_model)
            elif action == "model.remove":
                closed(payload, {"model_id"}, action)
                if not isinstance(payload["model_id"], str) or payload["model_id"] not in config["models"]:
                    raise ConfigurationError("model-not-registered", "Model registration does not exist.")
                del config["models"][payload["model_id"]]
            elif action == "routing.save":
                closed(payload, {"default", "overrides"}, action)
                config["default"], config["overrides"] = copy.deepcopy(payload["default"]), copy.deepcopy(payload["overrides"])
            elif action == "routing.rollback":
                closed(payload, {"revision"}, action)
                revision = payload["revision"]
                if type(revision) is not int or str(revision) not in state["history"]:
                    raise ConfigurationError("revision-not-found", "Choose an existing configuration revision.")
                config = copy.deepcopy(state["history"][str(revision)])
            else:
                raise ConfigurationError("action-not-allowed", "Configuration action is not admitted.")
            self.validate(config)
            revision = state["revision"] + 1
            receipt = {"command_id": command["command_id"], "command_digest": fingerprint,
                       "actor": actor, "action": action, "previous_revision": state["revision"],
                       "revision": revision, "configuration_digest": digest(config)}
            receipt["receipt_digest"] = digest(receipt)
            state["configuration"], state["revision"] = config, revision
            state["history"][str(revision)] = copy.deepcopy(config)
            state["commands"][command["command_id"]] = receipt
            if action == "model.register":
                self._outcome(state, model_id, verified_model, "verification", "suggestion-produced",
                              receipt["receipt_digest"], account_binding)
            atomic_json(self.path, state)
            return copy.deepcopy(receipt)

    def _outcome(self, state, model_id, model, kind, code, reference, account_binding):
        binding = digest({"model": model, "policy": self.backends.get(model["backend_id"]), "account": account_binding})
        now = datetime.now(timezone.utc).isoformat()
        outcomes = state.setdefault("provider_outcomes", {})
        previous = outcomes.get(model_id, {})
        success = previous.get("last_success") if previous.get("binding") == binding else None
        if code == "suggestion-produced":
            success = {"kind": kind, "at": now, "reference": reference}
        outcomes[model_id] = {"binding": binding, "at": now, "code": code, "last_success": success}
        # Removed registrations do not accumulate observation state.
        state["provider_outcomes"] = {key: value for key, value in outcomes.items() if key in state["configuration"]["models"]}

    def record_outcome(self, model, code, reference, account_binding=None):
        # Capacity admission rejected the call before a provider attempt.
        if code == "provider-busy":
            return
        model_id = digest({"backend_id": model["backend_id"], "model": model["model"]})
        with locked(self.root / "configuration.lock"):
            state = self._read()
            # A concurrent registration edit must not inherit an old request.
            if state["configuration"]["models"].get(model_id) != model:
                return
            self._outcome(state, model_id, model, "request", code, reference, account_binding)
            atomic_json(self.path, state)
            (self.root / "health.json").unlink(missing_ok=True)

    def cache_health(self, value, outcomes):
        with locked(self.root / "configuration.lock"):
            state = self._read()
            if (state["revision"] != value["configuration_revision"] or digest(state["configuration"]) != value["configuration_digest"]
                    or state.get("provider_outcomes", {}) != outcomes):
                return False
            atomic_json(self.root / "health.json", value)
            return True

    def outcomes(self):
        with locked(self.root / "configuration.lock"):
            return copy.deepcopy(self._read().get("provider_outcomes", {}))

    def outcome(self, model_id, model, account_binding=None, *, outcomes=None):
        value = (self.outcomes() if outcomes is None else outcomes).get(model_id)
        binding = digest({"model": model, "policy": self.backends.get(model["backend_id"]), "account": account_binding})
        return value if value and value.get("binding") == binding else None

    def validate(self, config: dict[str, Any]) -> None:
        closed(config, {"backends", "models", "default", "overrides"}, "configuration")
        if not all(isinstance(config[key], dict) for key in ("backends", "models", "overrides")):
            raise ConfigurationError("invalid-configuration", "Registration and override maps are required.")
        for key, backend in config["backends"].items():
            if backend != {"backend_id": key}:
                raise ConfigurationError("invalid-registration", "Backend records cannot change owner-selected connection or permission fields.")
        for model_id, model in config["models"].items():
            closed(model, {"backend_id", "model", "supported_efforts", "model_digest", "runtime_version", "verification_ref"}, "verified model")
            if model["backend_id"] not in config["backends"] or model_id != digest({"backend_id": model["backend_id"], "model": model["model"]}):
                raise ConfigurationError("invalid-registration", "Model registration does not bind its actual backend and model.")
            if not isinstance(model["model"], str) or not model["model"] or len(model["model"]) > 200:
                raise ConfigurationError("invalid-registration", "Model identity is invalid.")
            if model["runtime_version"] is not None and (not isinstance(model["runtime_version"], str) or not 0 < len(model["runtime_version"]) <= 2048):
                raise ConfigurationError("invalid-registration", "Runtime version must be observed metadata or explicitly unknown.")
            if model["model_digest"] is not None and (not isinstance(model["model_digest"], str) or not 0 < len(model["model_digest"]) <= 200):
                raise ConfigurationError("invalid-registration", "Model digest must be observed metadata or explicitly unknown.")
            efforts = model["supported_efforts"]
            if not isinstance(efforts, list) or not efforts or any(x is not None and type(x) not in {str, bool} for x in efforts) or len(set(efforts)) != len(efforts):
                raise ConfigurationError("invalid-registration", "Supported effort catalogue is invalid.")
            if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(model["verification_ref"])):
                raise ConfigurationError("invalid-registration", "An actual model verification reference is required.")
        if set(config["overrides"]) - self.tasks:
            raise ConfigurationError("task-not-admitted", "A task override is outside the existing profile contracts.")
        for task in self.tasks:
            route = config["overrides"].get(task, config["default"])
            if route is not None:
                self.validate_route(config, route, task)

    def validate_route(self, config: dict[str, Any], route: Any, task: str) -> None:
        closed(route, {"primary", "fallbacks", "on_exhausted"}, "task route")
        if route["on_exhausted"] != "fail-closed" or not isinstance(route["fallbacks"], list) or len(route["fallbacks"]) > 4:
            raise ConfigurationError("invalid-fallback", "Use at most four explicit fallbacks and fail closed when exhausted.")
        targets = [route["primary"], *route["fallbacks"]]
        seen = set()
        for target in targets:
            closed(target, {"model_id", "effort"}, "model selection")
            if not isinstance(target["model_id"], str) or (target["effort"] is not None and type(target["effort"]) not in {str, bool}):
                raise ConfigurationError("invalid-selection", "Model and effort identities are invalid.")
            model = config["models"].get(target["model_id"])
            if model is None:
                raise ConfigurationError("model-not-registered", "Every selected model must be registered and verified.")
            if target["effort"] not in model["supported_efforts"]:
                raise ConfigurationError("effort-not-supported", "The model does not support the selected effort.")
            if model["backend_id"] not in self.backends or task not in self.backends[model["backend_id"]]["allowed_tasks"]:
                raise ConfigurationError("task-not-admitted", "Backend is not admitted for this task and its data scope.")
            key = (target["model_id"], target["effort"])
            if key in seen:
                raise ConfigurationError("invalid-fallback", "Fallback order must not contain duplicate selections.")
            seen.add(key)

    def selection(self, snapshot: dict[str, Any], task: str) -> dict[str, Any] | None:
        if task not in self.tasks:
            raise ConfigurationError("task-not-admitted", "Task is outside the current profile contracts.")
        config = snapshot["configuration"]
        route = config["overrides"].get(task, config["default"])
        if route is None:
            return None  # Preserve the existing explicit source-selected binding.
        self.validate_route(config, route, task)
        return {"revision": snapshot["revision"], "configuration_digest": snapshot["digest"],
                "task": task, "route": copy.deepcopy(route), "models": {
                    x["model_id"]: copy.deepcopy(config["models"][x["model_id"]])
                    for x in [route["primary"], *route["fallbacks"]]}}


class InvocationJournal:
    """Freeze one selection/result per original caller invocation identity.

    A pending record after process loss means unknown completion. It must never
    automatically launch another provider or fall back on a repeated request.
    """
    def __init__(self, root: Path):
        self.root = root

    @contextmanager
    def invocation(self, identity: dict[str, Any], request_digest: str, selection: dict[str, Any]):
        key = digest(identity).removeprefix("sha256:")
        path = self.root / (key + ".json")
        try:
            with locked(self.root / (key + ".lock"), blocking=False):
                current = json.loads(path.read_text()) if path.exists() else None
                if current and current["request_digest"] != request_digest:
                    raise ConfigurationError("invocation-conflict", "Invocation identity is bound to another request.")
                if current is None:
                    current = {"identity": identity, "request_digest": request_digest,
                               "selection": copy.deepcopy(selection), "state": "pending", "result": None}
                    atomic_json(path, current)
                    fresh = True
                else:
                    fresh = False
                def finish(result: Any):
                    if not fresh or current["state"] != "pending":
                        raise ConfigurationError("invocation-conflict", "Only the original pending attempt can finish.")
                    current.update(state="finished", result=copy.deepcopy(result))
                    atomic_json(path, current)
                yield current, fresh, finish
        except BlockingIOError as error:
            raise ConfigurationError("invocation-in-progress", "The original invocation is still in progress.") from error
