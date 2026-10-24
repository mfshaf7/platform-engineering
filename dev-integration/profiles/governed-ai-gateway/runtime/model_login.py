"""Recoverable, operator-owned native device sign-in; never exports tokens."""
from __future__ import annotations

import json
from pathlib import Path
import queue
import threading
import time
from urllib.parse import urlparse

from codex_adapter import CodexAdapter, CodexProtocol
from model_configuration import ConfigurationError, atomic_json, digest, locked


TERMINAL = {"connected", "cancelled", "failed", "interrupted"}


class ModelLogin:
    def __init__(self, root: Path, backends, *, protocol_factory=CodexProtocol):
        self.root, self.backends = root, backends
        self.protocol_factory = protocol_factory
        self.active = {}
        self.guard = threading.Lock()

    def _paths(self, command_id):
        if not isinstance(command_id, str) or not command_id or len(command_id) > 200:
            raise ConfigurationError("invalid-command", "Login command identity is required.")
        name = digest(command_id)[7:]
        return self.root / (name + ".json"), self.root / (name + ".lock")

    def start(self, *, command_id, backend_id, actor):
        backend = self.backends.get(backend_id)
        if backend is None or not hasattr(backend, "account"):
            raise ConfigurationError("login-not-supported", "This admitted backend has no native account sign-in.")
        path, lock = self._paths(command_id)
        fingerprint = digest({"command_id": command_id, "backend_id": backend_id, "actor": actor})
        with locked(lock):
            if path.exists():
                record = json.loads(path.read_text())
                if record["request_digest"] != fingerprint:
                    raise ConfigurationError("command-conflict", "Login identity belongs to another request.")
                return record
            record = {"command_id": command_id, "request_digest": fingerprint, "backend_id": backend_id,
                      "actor": actor, "state": "starting", "verification_url": None, "user_code": None,
                      "failure": None}
            cancel = threading.Event()
            with self.guard:
                if self.active:
                    raise ConfigurationError("login-busy", "Finish or cancel the existing account sign-in first.")
                self.active[command_id] = cancel
            atomic_json(path, record)
            threading.Thread(target=self._run, args=(record, cancel), daemon=True).start()
            return record

    def read(self, *, command_id, actor):
        path, lock = self._paths(command_id)
        with locked(lock):
            if not path.exists():
                raise ConfigurationError("login-not-found", "The original login request was not found.")
            record = json.loads(path.read_text())
            if record["actor"] != actor:
                raise ConfigurationError("login-forbidden", "The original operator owns this login.")
            with self.guard:
                active = command_id in self.active
            if record["state"] not in TERMINAL and not active:
                # Reconcile the owner commit if a process died after Vault
                # accepted it but before the login journal was updated.
                account = self.backends[record["backend_id"]].account
                connected = account.completed_login(command_id)
                record.update(state="connected" if connected else "interrupted",
                              verification_url=None, user_code=None,
                              failure=None if connected else "native-login-process-interrupted")
                atomic_json(path, record)
            return record

    def cancel(self, *, command_id, actor):
        record = self.read(command_id=command_id, actor=actor)
        if record["state"] in TERMINAL:
            return record
        path, lock = self._paths(command_id)
        with locked(lock):
            record = json.loads(path.read_text())
            if record["state"] in TERMINAL:
                return record
            with self.guard:
                cancel = self.active.get(command_id)
                if cancel:
                    cancel.set()
            record["state"] = "cancel-requested"
            atomic_json(path, record)
        return record

    def _run(self, record, cancel):
        command_id, backend_id = record["command_id"], record["backend_id"]
        path, lock = self._paths(command_id)
        backend, protocol = self.backends[backend_id], None
        acquired = False
        try:
            acquired = CodexAdapter._slots.acquire(blocking=False)
            if not acquired:
                raise ValueError("Provider process slot is busy")
            with backend.account.project(allow_missing=True, login_command_id=command_id) as (home, persist):
                protocol = self.protocol_factory(executable=backend.executable, executable_digest=backend.executable_digest,
                                                 home=home, timeout_seconds=600)
                protocol.initialize(time.monotonic() + 10)
                login = protocol.request("account/login/start", {"type": "chatgptDeviceCode"}, time.monotonic() + 20)
                url = urlparse(login.get("verificationUrl", ""))
                if login.get("type") != "chatgptDeviceCode" or url.scheme != "https" or url.hostname not in {
                    "auth.openai.com", "auth0.openai.com", "chatgpt.com"} or url.username or url.password or \
                    not isinstance(login.get("loginId"), str) or not isinstance(login.get("userCode"), str) or \
                    len(login["userCode"]) > 128 or len(url.geturl()) > 2048:
                    raise ValueError("Invalid native device login instructions")
                with locked(lock):
                    current = json.loads(path.read_text())
                    if not cancel.is_set():
                        current.update(state="waiting-for-operator", verification_url=url.geturl(), user_code=login["userCode"])
                        atomic_json(path, current)
                deadline = time.monotonic() + 600
                while time.monotonic() < deadline:
                    if cancel.is_set():
                        protocol.send({"id": protocol.next_id, "method": "account/login/cancel", "params": {"loginId": login["loginId"]}})
                        with locked(lock):
                            record.update(state="cancelled", verification_url=None, user_code=None)
                            atomic_json(path, record)
                        return
                    try:
                        message = protocol.messages.get(timeout=1)
                    except queue.Empty:
                        continue
                    if message is None or message.get("protocol_failure") or "error" in message:
                        raise ValueError("Native login interrupted")
                    if message.get("method") == "account/login/completed":
                        params = message.get("params", {})
                        if params.get("loginId") != login["loginId"] or params.get("success") is not True:
                            raise ValueError("Native login did not complete")
                        with locked(lock):
                            if cancel.is_set():
                                record.update(state="cancelled", verification_url=None, user_code=None)
                            else:
                                persist(protocol.account_path.read_bytes())
                                record.update(state="connected", verification_url=None, user_code=None)
                            atomic_json(path, record)
                        return
                raise ValueError("Native device login expired")
        except Exception:
            # Raw account or transport failures never cross the owner boundary.
            with locked(lock):
                record.update(state="failed", failure="native-login-unavailable", verification_url=None, user_code=None)
                atomic_json(path, record)
        finally:
            try:
                if protocol:
                    protocol.close()
            finally:
                if acquired:
                    CodexAdapter._slots.release()
                with self.guard:
                    self.active.pop(command_id, None)
