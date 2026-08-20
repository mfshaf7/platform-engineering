from __future__ import annotations

from dataclasses import dataclass
import json
import threading
import time
from typing import Callable
import urllib.error
import urllib.request


CLASSIFICATION_SCHEMA = {
    "type": "object",
    "required": ["suggested_decision", "confidence"],
    "properties": {
        "suggested_decision": {
            "type": "string",
            "enum": ["out-of-scope", "proposed", "admitted"],
        },
        "confidence": {
            "type": "string",
            "enum": ["low", "medium", "high"],
        },
    },
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You classify workspace intake as one of three suggestions.
Return only JSON matching the supplied schema.
- out-of-scope: the entrant should not join this workspace.
- proposed: the entrant needs architecture or ownership discussion before admission.
- admitted: the entrant has a clear durable owner and belongs in the active workspace model.
Never treat your answer as approval. Never request or use tools."""


class OllamaAdapterError(RuntimeError):
    code = "provider-error"


class ProviderUnavailable(OllamaAdapterError):
    code = "provider-unavailable"


class ProviderTimeout(OllamaAdapterError):
    code = "provider-timeout"


class ProviderBusy(OllamaAdapterError):
    code = "provider-busy"


class ProviderIntegrityError(OllamaAdapterError):
    code = "provider-integrity-failed"


class ProviderOutputInvalid(OllamaAdapterError):
    code = "provider-output-invalid"


@dataclass(frozen=True)
class ProviderResult:
    output: dict[str, str]
    model_digest: str
    runtime_version: str
    latency_ms: int
    usage: dict[str, int]


class OllamaAdapter:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        expected_digest: str,
        expected_runtime_version: str,
        timeout_seconds: float = 30,
        retry_count: int = 1,
        max_concurrency: int = 2,
        max_output_tokens: int = 64,
        prompt_version: str = "intake-classifier-v1.0",
        opener: Callable[..., object] = urllib.request.urlopen,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.expected_digest = expected_digest
        self.expected_runtime_version = expected_runtime_version
        self.timeout_seconds = timeout_seconds
        self.retry_count = retry_count
        self.max_output_tokens = max_output_tokens
        self.prompt_version = prompt_version
        self._opener = opener
        self._slots = threading.BoundedSemaphore(max_concurrency)

    def classify(self, intake_packet: dict) -> ProviderResult:
        if not self._slots.acquire(blocking=False):
            raise ProviderBusy("provider concurrency limit reached")
        try:
            started = time.monotonic()
            runtime_version = self._read_runtime_version()
            model_digest = self._read_model_digest()
            response = self._request_json(
                "/api/chat",
                {
                    "model": self.model,
                    "stream": False,
                    "think": False,
                    "format": CLASSIFICATION_SCHEMA,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": json.dumps(intake_packet, sort_keys=True),
                        },
                    ],
                    "options": {
                        "temperature": 0,
                        "seed": 0,
                        "num_ctx": 4096,
                        "num_predict": self.max_output_tokens,
                    },
                    "keep_alive": "5m",
                },
            )
            output = self._parse_output(response)
            return ProviderResult(
                output=output,
                model_digest=model_digest,
                runtime_version=runtime_version,
                latency_ms=max(0, round((time.monotonic() - started) * 1000)),
                usage={
                    "prompt_tokens": int(response.get("prompt_eval_count") or 0),
                    "completion_tokens": int(response.get("eval_count") or 0),
                },
            )
        finally:
            self._slots.release()

    def _read_runtime_version(self) -> str:
        response = self._request_json("/api/version")
        version = str(response.get("version") or "")
        if version != self.expected_runtime_version:
            raise ProviderIntegrityError(
                f"Ollama version {version!r} does not match approved version "
                f"{self.expected_runtime_version!r}"
            )
        return version

    def _read_model_digest(self) -> str:
        response = self._request_json("/api/tags")
        models = response.get("models")
        if not isinstance(models, list):
            raise ProviderIntegrityError("Ollama model inventory is malformed")
        model = next(
            (
                item
                for item in models
                if isinstance(item, dict)
                and (item.get("name") == self.model or item.get("model") == self.model)
            ),
            None,
        )
        digest = str((model or {}).get("digest") or "")
        if digest != self.expected_digest:
            raise ProviderIntegrityError(
                f"model digest {digest!r} does not match approved digest "
                f"{self.expected_digest!r}"
            )
        return digest

    def _request_json(self, path: str, payload: dict | None = None) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="GET" if payload is None else "POST",
        )
        for attempt in range(self.retry_count + 1):
            try:
                with self._opener(request, timeout=self.timeout_seconds) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    if not isinstance(result, dict):
                        raise ProviderOutputInvalid("provider returned a non-object response")
                    return result
            except TimeoutError as exc:
                if attempt >= self.retry_count:
                    raise ProviderTimeout("provider request timed out") from exc
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, TimeoutError):
                    if attempt >= self.retry_count:
                        raise ProviderTimeout("provider request timed out") from exc
                elif attempt >= self.retry_count:
                    raise ProviderUnavailable("provider is unavailable") from exc
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise ProviderOutputInvalid("provider returned malformed JSON") from exc
        raise ProviderUnavailable("provider request failed")

    @staticmethod
    def _parse_output(response: dict) -> dict[str, str]:
        message = response.get("message")
        if not isinstance(message, dict):
            raise ProviderOutputInvalid("provider response is missing message")
        if message.get("thinking") or message.get("tool_calls"):
            raise ProviderOutputInvalid("thinking or tool output is not allowed")
        content = message.get("content")
        if not isinstance(content, str):
            raise ProviderOutputInvalid("provider response content is missing")
        try:
            output = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ProviderOutputInvalid("provider content is not JSON") from exc
        if not isinstance(output, dict) or set(output) != {"suggested_decision", "confidence"}:
            raise ProviderOutputInvalid("provider output fields do not match the schema")
        if output["suggested_decision"] not in {"out-of-scope", "proposed", "admitted"}:
            raise ProviderOutputInvalid("provider suggested_decision is invalid")
        if output["confidence"] not in {"low", "medium", "high"}:
            raise ProviderOutputInvalid("provider confidence is invalid")
        return output
