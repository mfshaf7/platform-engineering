"""Named API connections and opaque operation custody, separate from model history.

Only the explicit credential method accepts a key. Safe intent is retained
before a Vault CAS write; neither this file nor the generic command journal
ever contains the key. Reconciliation reads the original owner effect.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import copy
import hmac
import json
from pathlib import Path
import re
import urllib.error
import urllib.request

from api_provider_adapter import PRESETS, presets
from model_configuration import ConfigurationError, atomic_json, closed, digest, locked
from ollama_adapter import ProviderIntegrityError, ProviderUnavailable
from provider_accounts import NoCredentialRedirect


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def identifier(value, label="operation"):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,199}", value):
        raise ConfigurationError("invalid-command", "A bounded stable " + label + " identity is required.")
    return value


class VaultApiCredentials:
    def __init__(self, *, address, mount, prefix, token_file, opener=None):
        if not address.startswith(("https://", "http://127.0.0.1:", "http://vault.")):
            raise ProviderIntegrityError("Use the accepted Platform Vault endpoint.")
        if any(x in {"", ".", ".."} for x in (mount + "/" + prefix).split("/")):
            raise ProviderIntegrityError("The API credential custody prefix is invalid.")
        self.base = address.rstrip("/") + "/v1/" + mount + "/data/" + prefix.rstrip("/") + "/"
        self.token_file = Path(token_file)
        self.opener = opener or urllib.request.build_opener(NoCredentialRedirect()).open

    def _request(self, connection_id, payload=None, version=None):
        if not re.fullmatch(r"api-[a-f0-9]{32}", connection_id):
            raise ConfigurationError("invalid-connection", "Select an existing API connection.")
        if version is not None and (type(version) is not int or version < 1):
            raise ConfigurationError("invalid-credential-version", "The retained credential reference is invalid.")
        try:
            if self.token_file.is_symlink() or self.token_file.stat().st_mode & 0o077:
                raise ValueError()
            token = self.token_file.read_text().strip()
            if not token:
                raise ValueError()
            url = self.base + connection_id + ("?version=" + str(version) if version is not None else "")
            request = urllib.request.Request(url, data=None if payload is None else json.dumps(payload).encode(),
                headers={"X-Vault-Token": token, "Content-Type": "application/json"})
            with self.opener(request, timeout=8) as response:
                raw = response.read(65537)
                if len(raw) > 65536:
                    raise ValueError()
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ValueError()
                return value
        except urllib.error.HTTPError as error:
            if error.code == 404 and payload is None:
                return None
            raise ProviderUnavailable("API credential custody has not confirmed this operation.") from None
        except (OSError, ValueError, urllib.error.URLError):
            raise ProviderUnavailable("API credential custody is unavailable; reconcile the original operation.") from None

    def read(self, connection_id, version=None):
        value = self._request(connection_id, version=version)
        if value is None:
            return {"version": 0, "data": {}}
        try:
            number = value["data"]["metadata"]["version"]
            data = value["data"]["data"]
            if type(number) is not int or number < 1 or not isinstance(data, dict):
                raise ValueError()
            return {"version": number, "data": data}
        except (KeyError, TypeError, ValueError):
            raise ProviderUnavailable("API credential custody returned incomplete evidence.") from None

    def write(self, connection_id, *, previous_version, data):
        value = self._request(connection_id, {"options": {"cas": previous_version}, "data": data})
        if value.get("data", {}).get("version") != previous_version + 1:
            raise ProviderUnavailable("Reconcile the original API credential write before continuing.")


class ProviderConnections:
    def __init__(self, root, *, vault, configuration, allowed_tasks):
        self.root, self.vault, self.configuration = Path(root), vault, configuration
        self.allowed_tasks = sorted(allowed_tasks)
        self.path = self.root / "provider-connections.json"
        self.lock = self.root / "provider-connections.lock"

    def _read(self):
        if not self.path.exists():
            return {"schema_version": 1, "revision": 0, "connections": {}, "operations": {}}
        try:
            if self.path.is_symlink():
                raise ValueError()
            value = json.loads(self.path.read_text())
            if value["schema_version"] != 1 or type(value["revision"]) is not int or any(
                    not isinstance(value[k], dict) for k in ("connections", "operations")):
                raise ValueError()
            return value
        except (OSError, ValueError, KeyError, TypeError):
            raise ConfigurationError("connections-unavailable", "Retained provider connections are unavailable; no empty replacement was created.") from None

    @staticmethod
    def _public(state):
        return {"revision": state["revision"], "presets": presets(), "connections": [
            {key: copy.deepcopy(item[key]) for key in ("connection_id", "provider", "name", "state", "credential_generation", "pending_operation", "updated_at")}
            | {"experimental": True, "qualification": "real-account-verification-pending",
               "credential_present": item["credential_generation"] is not None}
            for item in state["connections"].values() if item["state"] != "removed"]}

    def snapshot(self):
        with locked(self.lock, blocking=False):
            return self._public(self._read())

    def policies(self):
        return {x["connection_id"]: {"provider": x["provider"], "endpoint_origin": PRESETS[x["provider"]]["origin"],
                "allowed_tasks": self.allowed_tasks} for x in self.snapshot()["connections"]}

    @staticmethod
    def _connection(state, connection_id):
        item = state["connections"].get(connection_id) if isinstance(connection_id, str) else None
        if item is None:
            raise ConfigurationError("connection-not-found", "Select an existing provider connection.")
        return item

    def _admit(self, state, command, actor):
        closed(command, {"command_id", "expected_revision", "action", "input"}, "connection command")
        identifier(command["command_id"])
        identifier(actor, "operator")
        fingerprint = digest({"actor": actor, "command": command})
        old = state["operations"].get(command["command_id"])
        if old:
            if old["command_digest"] != fingerprint:
                raise ConfigurationError("command-conflict", "This identity belongs to another connection operation or operator.")
            return old
        if type(command["expected_revision"]) is not int or command["expected_revision"] != state["revision"]:
            raise ConfigurationError("revision-conflict", "Refresh provider connections before changing them.")
        operation = {"command_id": command["command_id"], "command_digest": fingerprint, "actor": actor,
                     "action": command["action"], "connection_id": None, "state": "pending", "receipt": None}
        state["operations"][command["command_id"]] = operation
        return operation

    def _finish(self, state, operation, item):
        item["pending_operation"] = None
        item["updated_at"] = timestamp()
        before = state["revision"]
        state["revision"] += 1
        receipt = {"command_id": operation["command_id"], "command_digest": operation["command_digest"], "actor": operation["actor"], "action": operation["action"],
                   "connection_id": item["connection_id"], "previous_revision": before, "revision": state["revision"],
                   "state_digest": digest(self._public(state))}
        receipt["receipt_digest"] = digest(receipt)
        operation.update(state="finished", receipt=receipt)
        atomic_json(self.path, state)
        return copy.deepcopy(receipt)

    def command(self, command, *, actor):
        with ExitStack() as locks:
            if isinstance(command, dict) and isinstance(command.get("input"), dict) and command["input"].get("connection_id"):
                locks.enter_context(locked(self.root / (digest(command["input"]["connection_id"])[7:] + ".connection.lock"), blocking=False))
            locks.enter_context(locked(self.lock, blocking=False))
            state = self._read()
            operation = self._admit(state, command, actor)
            if operation["state"] == "finished":
                return copy.deepcopy(operation["receipt"])
            action, payload = command["action"], command["input"]
            if action == "connection.create":
                closed(payload, {"provider", "name"}, action)
                if payload["provider"] not in PRESETS or not isinstance(payload["name"], str) or not 0 < len(payload["name"].strip()) <= 100:
                    raise ConfigurationError("invalid-connection", "Choose a supported provider and a short connection name.")
                if len([x for x in state["connections"].values() if x["state"] != "removed"]) >= 16:
                    raise ConfigurationError("connection-limit", "This installation supports sixteen named API connections.")
                connection_id = "api-" + digest({"actor": actor, "command": command["command_id"]})[7:39]
                item = {"connection_id": connection_id, "provider": payload["provider"], "name": payload["name"].strip(),
                        "state": "active", "credential_generation": None, "pending_operation": None, "updated_at": timestamp()}
                state["connections"][connection_id] = item
                operation["connection_id"] = connection_id
            elif action in {"connection.disconnect", "connection.reconnect", "connection.remove"}:
                closed(payload, {"connection_id"}, action)
                item = self._connection(state, payload["connection_id"])
                if item["state"] == "removed":
                    raise ConfigurationError("connection-removed", "This connection was removed; its identity cannot be rebound.")
                pending = item["pending_operation"]
                if pending not in {None, operation["command_id"]}:
                    prior = state["operations"].get(pending)
                    if action == "connection.reconnect" or not prior or prior["action"] != "connection.credentials":
                        raise ConfigurationError("credential-reconcile-required", "Reconcile the original connection operation first.")
                    # Explicit disconnect/removal fences uncertain secret writes.
                    # A stale credential reconciliation cannot reactivate them.
                    prior.update(state="cancelled", receipt=None)
                operation["connection_id"] = item["connection_id"]
                if action == "connection.remove":
                    config = self.configuration.snapshot()
                    if any(m["backend_id"] == item["connection_id"] for m in config["configuration"]["models"].values()):
                        raise ConfigurationError("connection-in-use", "Reassign routes and remove this connection's registered models before removing it.")
                    item.update(state="removing", pending_operation=operation["command_id"])
                    atomic_json(self.path, state)
                    if item["connection_id"] in config["configuration"]["backends"]:
                        self.configuration.command({"command_id": "remove-connection:" + digest(operation["command_id"])[7:],
                            "expected_revision": config["revision"], "action": "backend.remove", "input": {"backend_id": item["connection_id"]}}, actor=actor)
                    self._fence(item, operation)
                    item.update(state="removed", credential_generation=None)
                elif action == "connection.disconnect":
                    item.update(state="disconnected", pending_operation=operation["command_id"])
                    atomic_json(self.path, state)
                    self._fence(item, operation)
                    item["credential_generation"] = None
                else:
                    item["state"] = "active"
            else:
                raise ConfigurationError("action-not-allowed", "This connection action is not admitted.")
            return self._finish(state, operation, item)

    def _fence(self, item, operation):
        # A CAS tombstone advances the Vault version. A late prior CAS write
        # therefore cannot resurrect a key after removal. No DELETE/undelete.
        retained = self.vault.read(item["connection_id"])
        if retained["data"].get("operation_id") == operation["command_id"] and retained["data"].get("api_key") is None:
            return
        self.vault.write(item["connection_id"], previous_version=retained["version"], data={
            "operation_id": operation["command_id"], "actor": operation["actor"], "api_key": None})

    def credentials(self, *, command_id, expected_revision, connection_id, api_key, actor):
        identifier(command_id)
        if not isinstance(api_key, str) or not 8 <= len(api_key) <= 8192 or any(not 33 <= ord(c) <= 126 for c in api_key):
            raise ConfigurationError("invalid-api-key", "Enter a bounded API key without spaces or line breaks.")
        # The admitted durable command deliberately excludes the raw key.
        command = {"command_id": command_id, "expected_revision": expected_revision,
                   "action": "connection.credentials", "input": {"connection_id": connection_id}}
        with locked(self.root / (digest(connection_id)[7:] + ".connection.lock"), blocking=False), locked(self.lock, blocking=False):
            state = self._read()
            operation = self._admit(state, command, actor)
            item = self._connection(state, connection_id)
            if operation["state"] == "cancelled":
                raise ConfigurationError("operation-cancelled", "This credential operation was fenced by disconnect or removal.")
            if operation["state"] == "finished":
                retained = self.vault.read(connection_id, operation["vault_version"])
                old_key = retained["data"].get("api_key")
                if not isinstance(old_key, str) or not hmac.compare_digest(old_key, api_key):
                    raise ConfigurationError("command-conflict", "This credential operation already belongs to different material.")
                return copy.deepcopy(operation["receipt"])
            if item["state"] != "active" or item["pending_operation"] not in {None, command_id}:
                raise ConfigurationError("connection-not-active", "Reconnect this connection and reconcile its pending operation before replacing credentials.")
            operation["connection_id"] = connection_id
            item["pending_operation"] = command_id
            atomic_json(self.path, state)
            retained = self.vault.read(connection_id)
            data = retained["data"]
            if data.get("operation_id") != command_id:
                if "previous_vault_version" in operation and retained["version"] != operation["previous_vault_version"]:
                    raise ConfigurationError("credential-generation-changed", "Custody changed after this credential intent; reconcile it before replacement.")
                operation["previous_vault_version"] = retained["version"]
                atomic_json(self.path, state)
                self.vault.write(connection_id, previous_version=retained["version"], data={
                    "operation_id": command_id, "actor": actor, "api_key": api_key})
                retained = self.vault.read(connection_id)
                data = retained["data"]
            if data.get("operation_id") != command_id or data.get("actor") != actor or not isinstance(data.get("api_key"), str) or not hmac.compare_digest(data["api_key"], api_key):
                raise ProviderIntegrityError("Credential custody does not match the original operation.")
            operation["vault_version"] = retained["version"]
            item["credential_generation"] = digest({"connection": connection_id, "version": retained["version"], "operation": command_id})
            return self._finish(state, operation, item)

    def operation(self, command_id, *, actor, reconcile=False):
        identifier(command_id)
        with locked(self.lock, blocking=False):
            state = self._read()
            operation = state["operations"].get(command_id)
            if not operation or operation["actor"] != actor:
                raise ConfigurationError("operation-not-found", "This operator has no such connection operation.")
            if reconcile and operation["state"] == "pending" and operation["action"] == "connection.credentials":
                item = self._connection(state, operation["connection_id"])
                retained = self.vault.read(item["connection_id"])
                data = retained["data"]
                if data.get("operation_id") == command_id and data.get("actor") == actor and isinstance(data.get("api_key"), str):
                    operation["vault_version"] = retained["version"]
                    item["credential_generation"] = digest({"connection": item["connection_id"], "version": retained["version"], "operation": command_id})
                    self._finish(state, operation, item)
            return {k: copy.deepcopy(operation[k]) for k in ("command_id", "command_digest", "actor", "action", "connection_id", "state", "receipt")}

    @contextmanager
    def credential(self, connection_id):
        # Serialize rotation/disconnect against the exact short-lived key use.
        with locked(self.root / (digest(connection_id)[7:] + ".connection.lock"), blocking=False):
            with locked(self.lock, blocking=False):
                item = copy.deepcopy(self._connection(self._read(), connection_id))
            if item["state"] != "active" or item["pending_operation"] is not None or not item["credential_generation"]:
                raise ProviderUnavailable("This API connection needs credentials, reconciliation or reconnection before use.")
            retained = self.vault.read(connection_id)
            data = retained["data"]
            generation = digest({"connection": connection_id, "version": retained["version"], "operation": data.get("operation_id")})
            if generation != item["credential_generation"] or not isinstance(data.get("api_key"), str):
                raise ProviderIntegrityError("The API credential generation changed outside the accepted connection operation.")
            yield data["api_key"], generation
