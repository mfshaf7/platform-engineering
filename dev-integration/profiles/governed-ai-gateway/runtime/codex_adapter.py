"""Bounded Codex app-server transport, with owner-projected account custody.

The executable, isolated HOME and CODEX_HOME belong to Platform. No interactive
Codex configuration, repository mount, plugin or provider secret reaches a
caller. A scratch directory and a fresh ephemeral thread are used per turn.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import tempfile
import threading
import time
from typing import Any

from ollama_adapter import (OllamaAdapterError, ProviderBusy, ProviderIntegrityError,
                            ProviderOutputInvalid, ProviderResult, ProviderUnavailable, ProviderCompletionUnknown)
from strict_output_schema import OutputSchemaError, validate_output


class CodexProtocol:
    MAX_MESSAGE_BYTES = 2_000_000

    def __init__(self, *, executable: Path, executable_digest: str,
                 home: Path, timeout_seconds: float = 120):
        if executable.is_symlink() or not executable.is_file():
            raise ProviderIntegrityError("Pinned Codex executable integrity is unavailable.")
        with executable.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != executable_digest:
                raise ProviderIntegrityError("Pinned Codex executable integrity is unavailable.")
        if not home.is_dir() or home.is_symlink():
            raise ProviderIntegrityError("Platform must project a private Codex account home.")
        # Only projected auth is allowed. Avoid a second, implicit credential or
        # settings source through a shared HOME, config.toml, MCP or plugins.
        if set(p.name for p in home.iterdir()) - {"auth.json"}:
            raise ProviderIntegrityError("Provider projection may contain only its managed account.")
        self.timeout = timeout_seconds
        self._scratch = tempfile.TemporaryDirectory(prefix="governed-codex-")
        scratch = Path(self._scratch.name)
        self.cwd = str(scratch / "work")
        Path(self.cwd).mkdir(mode=0o700)
        codex_home = scratch / "codex"
        codex_home.mkdir(mode=0o700)
        auth = home / "auth.json"
        if auth.exists():
            if auth.is_symlink() or auth.stat().st_mode & 0o077:
                self._scratch.cleanup()
                raise ProviderIntegrityError("Provider account projection must be a private regular file.")
            target = codex_home / "auth.json"
            target.write_bytes(auth.read_bytes())
            target.chmod(0o600)
        self.account_path = codex_home / "auth.json"
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(scratch),
               "CODEX_HOME": str(codex_home), "TMPDIR": str(scratch), "LANG": "C.UTF-8"}
        try:
            self.process = subprocess.Popen(
                [str(executable), "app-server", "--listen", "stdio://"],
                cwd=self.cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, start_new_session=True,
            )
        except OSError:
            self._scratch.cleanup()
            raise ProviderUnavailable("Pinned Codex runtime is unavailable before inference.") from None
        self.messages: queue.Queue = queue.Queue(maxsize=256)
        self._reader = threading.Thread(target=self._read_messages, daemon=True)
        self._reader.start()
        self.next_id = 1
        self.turn_submitted = False

    def _read_messages(self):
        try:
            while True:
                line = self.process.stdout.readline(self.MAX_MESSAGE_BYTES + 1)
                if not line:
                    self.messages.put_nowait(None)
                    return
                if len(line) > self.MAX_MESSAGE_BYTES or not line.endswith(b"\n"):
                    raise ValueError()
                self.messages.put_nowait(json.loads(line))
        except (ValueError, queue.Full, OSError):
            try:
                self.messages.put_nowait({"protocol_failure": True})
            except queue.Full:
                pass

    def send(self, message: dict[str, Any]):
        try:
            self.process.stdin.write(json.dumps(message).encode() + b"\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as error:
            if self.turn_submitted:
                raise ProviderCompletionUnknown("Reconcile the original provider turn before another attempt.") from error
            raise ProviderUnavailable("Codex app-server is unavailable before inference.") from error

    def receive(self, deadline: float):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            self._lost_completion()
        try:
            message = self.messages.get(timeout=remaining)
        except queue.Empty:
            self._lost_completion()
        if message is None or message.get("protocol_failure"):
            self._lost_completion()
        # A server request is an attempted tool/approval action. Fail closed
        # before replying or dispatching it; no action executor exists here.
        if "method" in message and "id" in message:
            raise ProviderIntegrityError("The inference-only provider requested an action.")
        return message

    def _lost_completion(self):
        if self.turn_submitted:
            raise ProviderCompletionUnknown("Provider completion is unknown; retain the original invocation.")
        raise ProviderUnavailable("Codex is unavailable before a model turn was submitted.")

    def request(self, method: str, params: dict[str, Any], deadline: float):
        request_id = self.next_id
        self.next_id += 1
        self.send({"id": request_id, "method": method, "params": params})
        while True:
            message = self.receive(deadline)
            if message.get("id") == request_id:
                if "error" in message:
                    # Do not expose raw provider errors, prompts or account data.
                    raise ProviderUnavailable("Codex rejected the bounded metadata request.")
                return message.get("result", {})

    def initialize(self, deadline: float):
        result = self.request("initialize", {"clientInfo": {"name": "governed-ai-gateway", "version": "1.0"},
                                             "capabilities": {"experimentalApi": False}}, deadline)
        self.runtime_version = result.get("userAgent", "codex-app-server")
        self.send({"method": "initialized", "params": {}})

    def models(self, deadline: float) -> list[dict[str, Any]]:
        models, cursor = [], None
        for _ in range(10):
            page = self.request("model/list", {"cursor": cursor, "limit": 100}, deadline)
            if not isinstance(page.get("data"), list):
                raise ProviderIntegrityError("Codex returned an invalid model catalogue.")
            for model in page["data"]:
                efforts = [entry["reasoningEffort"] for entry in model.get("supportedReasoningEfforts", [])]
                if not isinstance(model.get("model"), str) or not efforts or any(not isinstance(x, str) for x in efforts):
                    raise ProviderIntegrityError("Codex model effort metadata is invalid.")
                models.append({"model": model["model"], "supported_efforts": efforts,
                               "model_digest": None, "runtime_version": self.runtime_version})
            cursor = page.get("nextCursor")
            if not cursor:
                return models
        raise ProviderIntegrityError("Codex catalogue exceeded the bounded page limit.")

    def connection(self, deadline: float):
        # Fresh app-server, authenticated native remote read. A catalogue or
        # account/read alone may be local; neither proves remote access.
        result = self.request("account/rateLimits/read", {}, deadline)
        if not isinstance(result, dict) or not isinstance(result.get("rateLimits"), dict):
            raise ProviderIntegrityError("Codex returned invalid connection metadata.")
        for name in ("primary", "secondary"):
            window = result["rateLimits"].get(name)
            if window is not None:
                if not isinstance(window, dict) or type(window.get("usedPercent")) not in (int, float) or not 0 <= window["usedPercent"] <= 100:
                    raise ProviderIntegrityError("Codex returned invalid connection metadata.")
                if window["usedPercent"] >= 100:
                    raise ProviderBusy("The authenticated provider reports exhausted capacity.")

    def turn(self, *, model: str, effort: str, system_prompt: str,
             input_payload: dict[str, Any], output_schema: dict[str, Any], deadline: float):
        thread = self.request("thread/start", {
            "model": model, "cwd": self.cwd, "sandbox": "read-only", "approvalPolicy": "never",
            "ephemeral": True, "config": {"features.shell_tool": False, "web_search": "disabled"},
            "developerInstructions": system_prompt + "\nUse no tools. Return only the schema-constrained answer.",
        }, deadline)
        thread_id = thread.get("thread", {}).get("id")
        if not isinstance(thread_id, str) or thread.get("model") != model or thread.get("cwd") != self.cwd or thread.get("approvalPolicy") != "never" or \
                thread.get("modelProvider") != "openai" or thread.get("sandbox", {}).get("type") != "readOnly" or \
                thread.get("sandbox", {}).get("networkAccess", False) is not False:
            raise ProviderIntegrityError("Codex did not bind the requested model and isolated thread.")
        request_id = self.next_id
        self.next_id += 1
        # From this point, connection loss cannot justify automatic fallback.
        self.turn_submitted = True
        self.send({"id": request_id, "method": "turn/start", "params": {
            "threadId": thread_id, "model": model, "effort": effort,
            "input": [{"type": "text", "text": json.dumps(input_payload)}], "outputSchema": output_schema,
        }})
        output, turn_id = None, None
        while True:
            message = self.receive(deadline)
            if "error" in message:
                raise ProviderCompletionUnknown("Codex turn was not completed; reconcile its original invocation.")
            if message.get("id") == request_id and "result" in message:
                turn_id = message["result"].get("turn", {}).get("id")
                if not isinstance(turn_id, str):
                    raise ProviderIntegrityError("Codex did not bind the actual turn identity.")
            method, params = message.get("method"), message.get("params", {})
            if method in {"item/started", "item/completed"}:
                if params.get("threadId") != thread_id:
                    raise ProviderIntegrityError("Codex returned another thread's item.")
                kind = params.get("item", {}).get("type")
                if kind not in {"userMessage", "agentMessage", "reasoning", "plan", "contextCompaction"}:
                    raise ProviderIntegrityError("A tool item is forbidden in bounded model inference.")
                if method == "item/completed" and kind == "agentMessage":
                    output = params["item"].get("text")
            if method == "turn/completed":
                if params.get("threadId") != thread_id or params.get("turn", {}).get("id") != turn_id or turn_id is None:
                    raise ProviderIntegrityError("Codex returned another turn's completion.")
                if params.get("turn", {}).get("status") != "completed":
                    raise ProviderCompletionUnknown("The original Codex turn did not produce a completed result.")
                try:
                    value = json.loads(output)
                    validate_output(value, output_schema)
                    return value
                except (ValueError, TypeError, OutputSchemaError) as error:
                    raise ProviderOutputInvalid("Codex output does not match the admitted task schema.") from error

    def close(self):
        try:
            if self.process.poll() is None:
                os.killpg(self.process.pid, signal.SIGTERM)
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait(timeout=3)
            self.process.stdin.close()
            self.process.stdout.close()
            self._reader.join(timeout=1)
        finally:
            self._scratch.cleanup()


class CodexAdapter:
    # The complete gateway process shares one provider slot, including models
    # selected by different task profiles. Local memory use remains bounded.
    _slots = threading.BoundedSemaphore(1)

    def __init__(self, *, executable: Path, executable_digest: str, home: Path,
                 model: str, effort: str, timeout_seconds: float = 120,
                 account_sink=None, protocol_factory=CodexProtocol, max_output_bytes: int = 65536):
        self.settings = {"executable": executable, "executable_digest": executable_digest,
                         "home": home, "timeout_seconds": timeout_seconds}
        self.model, self.effort = model, effort
        self.timeout_seconds = timeout_seconds
        self.account_sink = account_sink
        self.protocol_factory = protocol_factory
        self.max_output_bytes = max_output_bytes

    def invoke(self, *, input_payload: dict, output_schema: dict, prompt_version: str, system_prompt: str):
        if not self._slots.acquire(blocking=False):
            raise ProviderBusy("Codex provider concurrency limit reached.")
        protocol = None
        started = time.monotonic()
        try:
            protocol = self.protocol_factory(**self.settings)
            deadline = started + self.timeout_seconds
            protocol.initialize(deadline)
            model = next((x for x in protocol.models(deadline) if x["model"] == self.model), None)
            if model is None or self.effort not in model["supported_efforts"]:
                raise ProviderIntegrityError("Selected model and effort are absent from the current native catalogue.")
            value = protocol.turn(model=self.model, effort=self.effort, input_payload=input_payload,
                                  system_prompt=system_prompt, output_schema=output_schema, deadline=deadline)
            if len(json.dumps(value).encode()) > self.max_output_bytes:
                raise ProviderOutputInvalid("The bounded Codex answer exceeds the task byte limit.")
            # Authentication refresh remains in Platform custody; a sink must
            # persist it to the dedicated Vault path using compare-and-swap.
            if self.account_sink:
                try:
                    if not protocol.account_path.is_file():
                        raise ValueError("Native account projection is absent")
                    self.account_sink(protocol.account_path.read_bytes())
                except Exception:
                    # The turn has already completed. A custody failure is not
                    # pre-submission unavailability and must never cause a
                    # second provider to run through the fallback path.
                    raise ProviderIntegrityError("Completed Codex turn account custody could not be committed.") from None
            return ProviderResult(output=value, model_digest=None, runtime_version=model["runtime_version"],
                                  latency_ms=int((time.monotonic() - started) * 1000), usage={}, prompt_version=prompt_version)
        finally:
            try:
                if protocol:
                    protocol.close()
            finally:
                self._slots.release()
