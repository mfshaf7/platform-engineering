"""Platform model registration and configuration within fixed owner backends."""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.request

from codex_adapter import CodexAdapter, CodexProtocol
from model_configuration import ConfigurationError, ModelConfiguration, atomic_json, closed, digest, locked
from ollama_adapter import OllamaAdapter, OllamaAdapterError, ProviderBusy, ProviderIntegrityError, ProviderUnavailable
from provider_accounts import VaultCodexAccount
from model_login import ModelLogin
from api_provider_adapter import ApiBackend, PRESETS
from provider_connections import ProviderConnections, VaultApiCredentials


PROBE_SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean", "const": True}},
                "required": ["ok"], "additionalProperties": False}


class OllamaBackend:
    def __init__(self, base_url: str, *, opener=urllib.request.urlopen):
        self.base_url = base_url.rstrip("/")
        self.opener = opener

    def _read(self, path, payload=None):
        try:
            request = urllib.request.Request(self.base_url + path, data=None if payload is None else json.dumps(payload).encode(),
                                             headers={"Content-Type": "application/json"})
            with self.opener(request, timeout=3) as response:
                raw = response.read(1_000_001)
                if len(raw) > 1_000_000:
                    raise ValueError()
                return json.loads(raw)
        except (OSError, ValueError, urllib.error.URLError):
            raise ProviderUnavailable("The admitted local backend catalogue is unavailable.") from None

    def discover(self):
        version, tags = self._read("/api/version"), self._read("/api/tags")
        if (not isinstance(version.get("version"), str) or not 0 < len(version["version"]) <= 2048
                or not isinstance(tags.get("models"), list) or len(tags["models"]) > 256
                or any(not isinstance(item, dict) or not all(isinstance(item.get(key), str) and 0 < len(item[key]) <= 200
                    for key in ("name", "digest")) for item in tags["models"])):
            raise ProviderIntegrityError("The local provider metadata is invalid.")
        return [{"model": model["name"], "supported_efforts": None,
                 "model_digest": model["digest"], "runtime_version": version["version"]}
                for model in tags["models"]]

    def metadata(self, name):
        model = next((item for item in self.discover() if item["model"] == name), None)
        if model is None:
            raise ConfigurationError("model-not-advertised", "The local backend does not advertise this model.")
        shown = self._read("/api/show", {"model": name})
        thinking = shown.get("thinking")
        values = thinking.get("values") if isinstance(thinking, dict) else [None]
        if not isinstance(values, list) or not 0 < len(values) <= 32 or any(type(x) not in {str, bool} and x is not None or isinstance(x, str) and len(x) > 200 for x in values):
            raise ProviderIntegrityError("The model's native thinking metadata is invalid.")
        return {**model, "supported_efforts": values}

    def adapter(self, model, effort, limits):
        backend = self
        class SelectedAdapter:
            def invoke(self, **kwargs):
                current = backend.metadata(model["model"])
                if effort not in current["supported_efforts"] or current["model_digest"] != model["model_digest"] or current["runtime_version"] != model["runtime_version"]:
                    raise ProviderIntegrityError("The selected local model identity or native effort changed.")
                adapter = OllamaAdapter(base_url=backend.base_url, model=model["model"],
                             expected_digest=model["model_digest"], expected_runtime_version=model["runtime_version"],
                             timeout_seconds=limits["timeout_seconds"], retry_count=0,
                             max_concurrency=1, max_output_tokens=limits["max_output_tokens"],
                             conservative_completion=True,
                             max_response_bytes=limits.get("max_output_bytes", 65536),
                             reasoning_effort=effort, shared_provider_limit=True, keep_alive=0, opener=backend.opener)
                return adapter.invoke(**kwargs)
        return SelectedAdapter()


class CodexBackend:
    def __init__(self, *, executable: Path, executable_digest: str, account):
        self.executable, self.executable_digest, self.account = executable, executable_digest, account

    def check_connection(self):
        if not CodexAdapter._slots.acquire(blocking=False):
            raise ProviderBusy("The dedicated Codex process slot is busy.")
        try:
            with self.account.project(allow_missing=True) as (home, persist):
                binding = getattr(persist, "account_binding", None)
                if not (home / "auth.json").is_file():
                    return None, binding
                protocol = CodexProtocol(executable=self.executable, executable_digest=self.executable_digest,
                                         home=home, timeout_seconds=10)
                try:
                    deadline = time.monotonic() + 10
                    protocol.initialize(deadline)
                    protocol.connection(deadline)
                    models = protocol.models(deadline)
                    if protocol.account_path.is_file():
                        persist(protocol.account_path.read_bytes())
                    return models, binding
                except OllamaAdapterError as error:
                    error.account_binding = binding
                    raise
                finally:
                    protocol.close()
        finally:
            CodexAdapter._slots.release()

    def discover(self):
        if not CodexAdapter._slots.acquire(blocking=False):
            raise ProviderBusy("The dedicated Codex process slot is busy.")
        try:
            with self.account.project() as (home, persist):
                protocol = CodexProtocol(executable=self.executable, executable_digest=self.executable_digest,
                                         home=home, timeout_seconds=10)
                try:
                    deadline = time.monotonic() + 10
                    protocol.initialize(deadline)
                    models = protocol.models(deadline)
                    if protocol.account_path.is_file():
                        persist(protocol.account_path.read_bytes())
                    return models
                finally:
                    protocol.close()
        finally:
            CodexAdapter._slots.release()

    def adapter(self, model, effort, limits):
        owner = self
        class ProjectedAdapter:
            def invoke(self, **kwargs):
                with ExitStack() as projection:
                    try:
                        home, persist = projection.enter_context(owner.account.project())
                    except BlockingIOError:
                        # Only account admission precedes provider submission.
                        # Do not catch dispatch, persistence or context-exit
                        # failures here: those cannot permit another provider.
                        raise ProviderBusy("The dedicated Codex account is in use before inference.") from None
                    adapter = CodexAdapter(executable=owner.executable, executable_digest=owner.executable_digest,
                                           home=home, model=model["model"], effort=effort,
                                           timeout_seconds=limits["timeout_seconds"], account_sink=persist,
                                           max_output_bytes=limits.get("max_output_bytes", 65536))
                    try:
                        return replace(adapter.invoke(**kwargs), account_binding=getattr(persist, "account_binding", None))
                    except OllamaAdapterError as error:
                        error.account_binding = getattr(persist, "account_binding", None)
                        raise
        return ProjectedAdapter()


class ModelManagement:
    def __init__(self, *, configuration: ModelConfiguration, backends: dict[str, Any], authority=None, connections=None):
        self.configuration, self.backends = configuration, backends
        self.authority = authority or {}
        self.logins = ModelLogin(configuration.root / "logins", backends)
        self.connections = connections
        self._fixed_backends = dict(backends)
        self._fixed_policies = dict(configuration.backends)
        self.sync_connections()

    def sync_connections(self):
        if self.connections is None:
            return
        try:
            policies = self.connections.policies()
        except BlockingIOError:
            raise ProviderBusy("Provider connections are changing; refresh shortly.") from None
        for key in set(self.backends) - set(self._fixed_backends) - set(policies):
            del self.backends[key]
        for key, policy in policies.items():
            if key not in self.backends:
                self.backends[key] = ApiBackend(policy["provider"], lambda key=key: self.connections.credential(key),
                    verification_current=lambda model, binding, key=key: self.configuration.outcome(
                        digest({"backend_id": key, "model": model["model"]}), model, binding) is not None)
        self.configuration.backends = {**self._fixed_policies, **policies}

    def connection_command(self, command, *, actor):
        if self.connections is None:
            raise ConfigurationError("connections-not-commissioned", "API connections are not commissioned in this installation.")
        result = self.connections.command(command, actor=actor)
        self.sync_connections()
        return result

    @classmethod
    def from_environment(cls, selections, root: Path):
        path = os.environ.get("GOVERNED_AI_MODEL_MANAGEMENT_POLICY_PATH")
        if not path:
            return None
        policy = json.loads(Path(path).read_text())
        closed(policy, {"schema_version", "caller_id", "operator_id", "token_file", "backends"} |
               ({"api_connections"} if "api_connections" in policy else set()), "owner management policy")
        if policy["schema_version"] != 1 or not all(isinstance(policy[k], str) and policy[k] for k in ("caller_id", "operator_id", "token_file")):
            raise ConfigurationError("invalid-policy", "Owner identity and authentication policy are required.")
        tasks = {profile_id + "/" + kind for profile_id, profile in selections["profiles"].items()
                 for kind in profile["task_contracts"]}
        backends = {}
        for backend_id, backend in policy["backends"].items():
            if not isinstance(backend.get("allowed_tasks"), list) or set(backend["allowed_tasks"]) - tasks:
                raise ConfigurationError("invalid-policy", "Backend permissions must name existing profile tasks.")
            if backend.get("provider") == "ollama":
                closed(backend, {"provider", "endpoint_origin", "allowed_tasks"}, "local backend policy")
                backends[backend_id] = OllamaBackend(backend["endpoint_origin"])
            elif backend.get("provider") == "codex-app-server":
                closed(backend, {"provider", "executable", "executable_digest", "vault", "allowed_tasks"}, "Codex backend policy")
                vault = backend["vault"]
                closed(vault, {"address", "mount", "path", "token_file"}, "dedicated account custody")
                account = VaultCodexAccount(address=vault["address"], mount=vault["mount"], path=vault["path"],
                                            token_file=Path(vault["token_file"]), runtime_root=root / "accounts" / backend_id)
                backends[backend_id] = CodexBackend(executable=Path(backend["executable"]),
                                                   executable_digest=backend["executable_digest"], account=account)
            else:
                raise ConfigurationError("backend-not-admitted", "This runtime does not implement the requested provider protocol.")
        configuration = ModelConfiguration(root, tasks=tasks, backends=policy["backends"])
        connections = None
        if "api_connections" in policy:
            admitted = policy["api_connections"]
            closed(admitted, {"providers", "vault", "allowed_tasks"}, "API connection policy")
            if admitted["providers"] != list(PRESETS) or not isinstance(admitted["allowed_tasks"], list) or set(admitted["allowed_tasks"]) - tasks:
                raise ConfigurationError("invalid-policy", "API presets and task permissions require the reviewed owner policy.")
            vault = admitted["vault"]
            closed(vault, {"address", "mount", "prefix", "token_file"}, "API credential custody")
            credentials = VaultApiCredentials(**vault)
            connections = ProviderConnections(root, vault=credentials, configuration=configuration, allowed_tasks=admitted["allowed_tasks"])
        return cls(configuration=configuration, backends=backends,
                   connections=connections,
                   authority={key: policy[key] for key in ("caller_id", "operator_id", "token_file")})

    def catalogue(self, backend_id: str, model=None):
        self.sync_connections()
        if backend_id not in self.configuration.backends or backend_id not in self.backends:
            raise ConfigurationError("backend-not-admitted", "Backend is not part of the accepted owner configuration.")
        # Catalogue availability is distinct from registration or verification.
        backend = self.backends[backend_id]
        if model is not None and hasattr(backend, "metadata"):
            models = [backend.metadata(model)]
        else:
            models = backend.discover()
            if model is not None:
                models = [item for item in models if item["model"] == model]
        return {"backend_id": backend_id, "models": models}

    def refresh_health(self, *, now=None):
        """Native metadata/account reads after core startup; never inference."""
        now = now or datetime.now(timezone.utc)
        self.sync_connections()
        connections = {x["connection_id"]: x for x in self.connections.snapshot()["connections"]} if self.connections else {}
        snapshot = self.configuration.snapshot()
        config = snapshot["configuration"]
        outcomes = self.configuration.outcomes()
        previous = self.health(snapshot)
        if previous and 0 <= (now - datetime.fromisoformat(previous["checked_at"])).total_seconds() < 60:
            return previous
        result = {"configuration_revision": snapshot["revision"], "configuration_digest": snapshot["digest"],
                  "checked_at": now.isoformat(), "expires_at": (now + timedelta(seconds=120)).isoformat(),
                  "backends": [], "models": []}
        if self.connections:
            result["_connections_digest"] = digest(connections)
        deadline = time.monotonic() + 20
        # One owner process, one bounded collector; UI reads never probe providers.
        with locked(self.configuration.root / "health.lock", blocking=False):
            for key in sorted(config["backends"])[:32]:
                backend = self.backends.get(key)
                state, code = "unknown", "connection-not-probed"
                advertised = None
                account_binding = None
                try:
                    if time.monotonic() >= deadline:
                        code = "check-budget-exhausted"
                    elif isinstance(backend, OllamaBackend):
                        advertised = {item["model"]: item for item in backend.discover()}
                        state, code = "available", "metadata-available"
                    elif isinstance(backend, CodexBackend):
                        models, account_binding = backend.check_connection()
                        if models is None:
                            state, code = "unavailable", "account-sign-in-required"
                        else:
                            advertised = {item["model"]: item for item in models}
                            state, code = "available", "connection-verified"
                    elif isinstance(backend, ApiBackend):
                        connection = connections[key]
                        account_binding = connection["credential_generation"]
                        if connection["state"] != "active":
                            state, code = "unavailable", "connection-disconnected"
                        elif connection["pending_operation"]:
                            state, code = "verification-needed", "credential-reconcile-required"
                        elif not account_binding:
                            state, code = "unavailable", "api-key-required"
                except ProviderIntegrityError as error:
                    account_binding = getattr(error, "account_binding", None)
                    state, code = "verification-needed", "provider-metadata-invalid"
                except ProviderUnavailable as error:
                    account_binding = getattr(error, "account_binding", None)
                    state, code = "unavailable", "provider-unavailable"
                except (BlockingIOError, ProviderBusy) as error:
                    account_binding = getattr(error, "account_binding", None)
                    state, code = "unknown", "provider-busy"
                except (KeyError, TypeError, ValueError, OSError):
                    state, code = "unknown", "provider-metadata-invalid"
                result["backends"].append({"backend_id": key, "state": state, "code": code})
                for model_id, model in sorted(config["models"].items()):
                    if model["backend_id"] != key or len(result["models"]) >= 256:
                        continue
                    item = {"model_id": model_id, "state": state, "code": code,
                            "observed_runtime_version": None, "observed_model_digest": None, "last_success": None}
                    if advertised is not None:
                        observed = advertised.get(model["model"])
                        if observed is None:
                            item.update(state="unavailable", code="model-not-advertised")
                        elif time.monotonic() >= deadline:
                            item.update(state="unknown", code="check-budget-exhausted")
                        else:
                            try:
                                if isinstance(backend, OllamaBackend):
                                    observed = backend.metadata(model["model"])
                                item.update(observed_runtime_version=observed["runtime_version"], observed_model_digest=observed["model_digest"])
                                changed = any(observed[field] != model[field] for field in ("model_digest", "runtime_version", "supported_efforts"))
                                item.update(state="verification-needed" if changed else "available",
                                            code="registration-changed" if changed else "metadata-matched")
                            except (ConfigurationError, OllamaAdapterError, OSError, ValueError, KeyError, TypeError):
                                item.update(state="unknown", code="provider-metadata-invalid")
                    outcome = self.configuration.outcome(model_id, model, account_binding, outcomes=outcomes)
                    if outcome:
                        success = outcome.get("last_success")
                        if success and datetime.fromisoformat(success["at"]) <= now:
                            item["last_success"] = success
                        # Native metadata never clears a newer failed turn.
                        if item["state"] == "available" and outcome["code"] != "suggestion-produced":
                            item.update(state="verification-needed", code="last-request-failed")
                    if isinstance(backend, CodexBackend) and item["state"] == "available":
                        success = item["last_success"]
                        recent = success and 0 <= (now - datetime.fromisoformat(success["at"])).total_seconds() <= 900
                        item.update(state="available" if recent else "verification-needed",
                                    code="recent-model-success" if recent else "model-verification-required")
                    if isinstance(backend, ApiBackend) and state == "unknown":
                        success = item["last_success"]
                        recent = success and 0 <= (now - datetime.fromisoformat(success["at"])).total_seconds() <= 900
                        okay = recent and outcome and outcome["code"] == "suggestion-produced"
                        item.update(state="available" if okay else "verification-needed",
                                    code="recent-model-success" if okay else "model-verification-required")
                    result["models"].append(item)
            # A turn finishing during this collector must not be overwritten
            # by an earlier success/failure observation from the same revision.
            self.configuration.cache_health(result, outcomes)
        return {key: value for key, value in result.items() if not key.startswith("_")}

    def health(self, snapshot):
        try:
            path = self.configuration.root / "health.json"
            if path.is_symlink() or path.stat().st_size > 1_048_576:
                return None
            value = json.loads(path.read_text())
            if self.connections and value.pop("_connections_digest", None) != digest({
                    x["connection_id"]: x for x in self.connections.snapshot()["connections"]}):
                return None
            now = datetime.now(timezone.utc)
            if (value["configuration_revision"] != snapshot["revision"] or value["configuration_digest"] != snapshot["digest"]
                    or not datetime.fromisoformat(value["checked_at"]) <= now < datetime.fromisoformat(value["expires_at"])):
                return None
            return value
        except (OSError, ValueError, KeyError, TypeError):
            return None

    def describe_backends(self):
        self.sync_connections()
        snapshot = self.configuration.snapshot()
        registered = snapshot["configuration"]["backends"]
        return {"health": self.health(snapshot), "tasks": sorted(self.configuration.tasks), "backends": [
            {"backend_id": key, "provider": value.get("provider"), "allowed_tasks": value["allowed_tasks"],
             "registered": key in registered, "account_login_supported": isinstance(self.backends.get(key), CodexBackend),
             "availability": "not-probed", **({"experimental": True, "qualification": "real-account-verification-pending",
                "catalogue_supported": value["provider"] != "glm-api", "verification_max_tokens": 4096}
                if value.get("provider") in PRESETS else {})}
            for key, value in sorted(self.configuration.backends.items())]}

    def command(self, command: dict[str, Any], *, actor: str):
        self.sync_connections()
        closed(command, {"command_id", "expected_revision", "action", "input"}, "management command")
        if not isinstance(command["command_id"], str) or not command["command_id"] or len(command["command_id"]) > 200:
            raise ConfigurationError("invalid-command", "A stable bounded command identity is required.")
        if type(command["expected_revision"]) is not int or command["expected_revision"] < 0:
            raise ConfigurationError("invalid-command", "Expected revision must be a nonnegative integer.")
        name = digest(command["command_id"])[7:]
        path = self.configuration.root / "requests" / (name + ".json")
        fingerprint = digest({"actor": actor, "command": command})
        with locked(path.with_suffix(".lock")):
            if path.exists():
                retained = json.loads(path.read_text())
                if retained["request_digest"] != fingerprint:
                    raise ConfigurationError("command-conflict", "Command identity belongs to another request or actor.")
                if retained["state"] == "finished":
                    return retained["result"]
                if retained["state"] == "failed":
                    if retained["provider_error"]:
                        error = OllamaAdapterError("The original provider operation failed.")
                        error.code = retained["error"]
                        raise error
                    raise ConfigurationError(retained["error"], "The original configuration command was rejected.")
                completed = self.configuration.command_result(command, actor=actor)
                if completed:
                    retained.update(state="finished", result=completed)
                    atomic_json(path, retained)
                    return completed
                if command["action"] not in {"account.login.start", "account.login.cancel"}:
                    raise ConfigurationError("command-completion-unknown", "Reconcile the original command; verification must not be duplicated.")
                # Native login start/cancel have their own persistent identity
                # and are safe to reconcile, including after a host restart.
            else:
                retained = {"request_digest": fingerprint, "state": "pending"}
                atomic_json(path, retained)
            try:
                result = self._command(command, actor=actor)
            except (ConfigurationError, OllamaAdapterError) as error:
                retained.update(state="failed", error=error.code, provider_error=isinstance(error, OllamaAdapterError))
                atomic_json(path, retained)
                raise
            retained.update(state="finished", result=result)
            atomic_json(path, retained)
            return result

    def _command(self, command: dict[str, Any], *, actor: str):
        closed(command, {"command_id", "expected_revision", "action", "input"}, "management command")
        if not isinstance(command["command_id"], str):
            raise ConfigurationError("invalid-command", "A stable command identity is required.")
        if command["action"] in {"account.login.start", "account.login.cancel"}:
            payload = command["input"]
            if command["action"] == "account.login.start":
                closed(payload, {"backend_id"}, "account sign-in")
                if not isinstance(payload["backend_id"], str) or payload["backend_id"] not in self.configuration.snapshot()["configuration"]["backends"]:
                    raise ConfigurationError("backend-not-registered", "Register the admitted backend before signing in.")
                return self.logins.start(command_id=command["command_id"], backend_id=payload["backend_id"], actor=actor)
            closed(payload, {"login_command_id"}, "account sign-in cancellation")
            return self.logins.cancel(command_id=payload["login_command_id"], actor=actor)
        path = self.configuration.root / "commands" / (digest(command["command_id"])[7:] + ".lock")
        with locked(path):
            previous = self.configuration.command_result(command, actor=actor)
            if previous:
                return previous
            verified = None
            if command["action"] == "model.register":
                closed(command["input"], {"backend_id", "model"}, "model registration")
                backend_id, name = command["input"]["backend_id"], command["input"]["model"]
                if not isinstance(backend_id, str) or not isinstance(name, str):
                    raise ConfigurationError("invalid-command", "Backend and model identities must be strings.")
                snapshot = self.configuration.snapshot()
                if snapshot["revision"] != command["expected_revision"]:
                    raise ConfigurationError("revision-conflict", "Refresh configuration before model verification.")
                if backend_id not in snapshot["configuration"]["backends"]:
                    raise ConfigurationError("backend-not-registered", "Register the admitted backend first.")
                existing = snapshot["configuration"]["models"].get(digest({"backend_id": backend_id, "model": name}))
                try:
                    metadata = next(iter(self.catalogue(backend_id, name)["models"]), None)
                    if metadata is None:
                        raise ConfigurationError("model-not-advertised", "The backend does not advertise this model.")
                    backend = self.backends[backend_id]
                    result = backend.adapter(metadata, metadata["supported_efforts"][0], {
                        "timeout_seconds": 60, "max_output_tokens": 4096 if isinstance(backend, ApiBackend) else 64,
                        "max_output_bytes": 65536 if isinstance(backend, ApiBackend) else 4096, "verification": True,
                    }).invoke(input_payload={"ok": True}, output_schema=PROBE_SCHEMA,
                              prompt_version="model-registration-probe-v1",
                              system_prompt='Return the JSON object {"ok":true}. Use no tools.')
                    if result.output != {"ok": True}:
                        raise ProviderIntegrityError("The advertised model did not complete its bounded verification.")
                    verified = {**metadata, "backend_id": backend_id, "verification_ref": digest({
                        "command_id": command["command_id"], "model": metadata, "result": result.output,
                        "latency_ms": result.latency_ms, "prompt_version": result.prompt_version})}
                except (ConfigurationError, OllamaAdapterError) as error:
                    if existing:
                        self.configuration.record_outcome(existing, error.code, digest(command), getattr(error, "account_binding", None))
                    raise
            return self.configuration.command(command, actor=actor, verified_model=verified,
                                              account_binding=getattr(result, "account_binding", None) if verified else None)

    def adapter(self, model, effort, limits):
        self.sync_connections()
        backend_id = model["backend_id"]
        if backend_id not in self.configuration.backends or backend_id not in self.backends:
            raise ProviderIntegrityError("The selected backend is no longer admitted.")
        return self.backends[backend_id].adapter(model, effort, limits)
