"""Experimental, bounded native API adapters. Credentials stay in owner custody.

The presets are reviewed destinations, not caller-supplied base URLs. Catalogue
metadata and a successful invocation are different evidence. No SDK retry,
redirect, tool execution or private-thinking projection is permitted here.
"""
from __future__ import annotations

from contextlib import ExitStack
import json
import re
import threading
import time
from urllib.parse import urlencode
import urllib.error
import urllib.request

from model_configuration import ConfigurationError
from ollama_adapter import (ProviderBusy, ProviderCompletionUnknown,
                            ProviderIntegrityError, ProviderOutputInvalid,
                            ProviderResult, ProviderUnavailable)
from strict_output_schema import OutputSchemaError, validate_output


PRESETS = {
    "claude-api": {"label": "Claude API", "origin": "https://api.anthropic.com", "path": "/v1/messages"},
    "deepseek-api": {"label": "DeepSeek API", "origin": "https://api.deepseek.com", "path": "/chat/completions"},
    "glm-api": {"label": "GLM · Z.AI Standard API", "origin": "https://api.z.ai", "path": "/api/paas/v4/chat/completions"},
}


def presets():
    return [{"provider": key, "label": value["label"], "endpoint_origin": value["origin"],
             "experimental": True, "qualification": "real-account-verification-pending",
             "catalogue_supported": key != "glm-api"}
            for key, value in PRESETS.items()]


def model_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/+@-]{0,199}", value):
        raise ConfigurationError("invalid-model", "Enter one bounded provider model identifier.")
    return value


class ApiAccessDenied(ProviderIntegrityError):
    operator_message = "The provider denied API access. Check the API key and this account's API eligibility."


class ApiRejected(ProviderIntegrityError):
    operator_message = "The provider rejected this model or its native settings. Review the model and capabilities."


class ApiOutputInvalid(ProviderOutputInvalid):
    operator_message = "The provider did not return a complete response matching the task contract."


class NoApiRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward an Authorization header to another destination.
        return None


def _efforts(value):
    if not isinstance(value, list) or not value or len(value) > 32 or any(
            x is not None and type(x) not in {str, bool} or isinstance(x, str) and not 0 < len(x) <= 100
            for x in value):
        raise ProviderIntegrityError("The provider's native control metadata is invalid.")
    if len({(type(x).__name__, str(x)) for x in value}) != len(value):
        raise ProviderIntegrityError("The provider's native controls contain duplicate choices.")
    return value


def glm_efforts(name):
    # These are protocol capability rules, not a recommended model catalogue.
    # Compatibility aliases which silently map to another strength are omitted.
    if re.fullmatch(r"glm-5\.3(?:-flash)?", name, re.I):
        return ["low", "high", "max"]
    if re.fullmatch(r"glm-5\.2(?:-flash)?", name, re.I):
        return ["none", "high", "max"]
    if re.fullmatch(r"glm-(?:4\.[67]|5(?:\.[01])?)(?:-flash)?", name, re.I):
        return [False, True]
    # Unknown model: the provider default is explicit; do not invent controls.
    return [None]


def claude_grammar(schema):
    """Native grammar projection; the original task schema remains authoritative.

    Claude does not implement string/array length constraints in its grammar.
    Keep them in the full schema in the prompt and enforce them locally after
    completion. Never change the canonical contract or accept partial output.
    """
    result = {k: v for k, v in schema.items() if k not in {
        "$id", "$schema", "const", "minLength", "maxLength", "minItems", "maxItems"}}
    if "const" in schema:
        result["enum"] = [schema["const"]]
    if "properties" in result:
        result["properties"] = {k: claude_grammar(v) for k, v in result["properties"].items()}
    if "items" in result:
        result["items"] = claude_grammar(result["items"])
    return result


class ApiBackend:
    _slots = threading.BoundedSemaphore(2)

    def __init__(self, provider, credential, *, verification_current=None, opener=None):
        if provider not in PRESETS:
            raise ConfigurationError("provider-not-admitted", "Choose a supported provider preset.")
        self.provider, self.credential = provider, credential
        self.verification_current = verification_current or (lambda model, binding: True)
        self.opener = opener or urllib.request.build_opener(NoApiRedirect()).open

    def _request(self, path, key, payload=None, *, timeout=8, max_bytes=1_000_000):
        headers = {"Authorization": "Bearer " + key, "Accept": "application/json", "Content-Type": "application/json"}
        if self.provider == "claude-api":
            headers["anthropic-version"] = "2026-10-21"
        request = urllib.request.Request(PRESETS[self.provider]["origin"] + path,
            data=None if payload is None else json.dumps(payload, ensure_ascii=False).encode(), headers=headers)
        try:
            with self.opener(request, timeout=timeout) as response:
                raw = response.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise ApiOutputInvalid("The provider response exceeds the accepted byte limit.")
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise ApiOutputInvalid("The provider response is not a JSON object.")
                return value
        except urllib.error.HTTPError as error:
            # Native error bodies can contain arbitrary content. Do not read,
            # persist, log or rethrow them. A returned 429 rejects this request.
            if error.code == 429:
                raise ProviderBusy("The provider rejected the request at its capacity boundary.") from None
            if error.code in {401, 403}:
                raise ApiAccessDenied(ApiAccessDenied.operator_message) from None
            if 400 <= error.code < 500 or 300 <= error.code < 400:
                raise ApiRejected(ApiRejected.operator_message) from None
            if payload is not None:
                raise ProviderCompletionUnknown("The provider did not confirm the submitted request's outcome.") from None
            raise ProviderUnavailable("The provider catalogue is unavailable.") from None
        except (OSError, TimeoutError, urllib.error.URLError):
            if payload is not None:
                raise ProviderCompletionUnknown("The submitted request's outcome is unknown; do not resubmit automatically.") from None
            raise ProviderUnavailable("The provider catalogue is unavailable.") from None
        except (ValueError, UnicodeError):
            raise ApiOutputInvalid("The provider response is not valid bounded JSON.") from None

    def discover(self):
        if self.provider == "glm-api":
            raise ConfigurationError("manual-model-required", "Enter a Z.AI model identifier and verify it. This preset has no admitted catalogue API.")
        result, after = [], None
        deadline = time.monotonic() + 12
        with self.credential() as (key, _):
            for _page in range(4):
                path = "/v1/models" if self.provider == "claude-api" else "/models"
                if self.provider == "claude-api":
                    path += "?" + urlencode({"limit": 100, **({"after_id": after} if after else {})})
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ProviderUnavailable("The bounded provider catalogue check did not complete.")
                value = self._request(path, key, timeout=min(8, remaining))
                items = value.get("data")
                if not isinstance(items, list) or len(items) > 256 or any(not isinstance(x, dict) for x in items):
                    raise ProviderIntegrityError("The provider catalogue is invalid.")
                for item in items:
                    name = model_name(item.get("id"))
                    if self.provider == "claude-api":
                        caps = item.get("capabilities") or {}
                        if not isinstance(caps, dict):
                            raise ProviderIntegrityError("The Claude capability metadata is invalid.")
                        effort = caps.get("effort") or {}
                        if not isinstance(effort, dict):
                            raise ProviderIntegrityError("The Claude effort metadata is invalid.")
                        levels = [name for name in ("low", "medium", "high", "xhigh", "max")
                                  if isinstance(effort.get(name), dict) and effort[name].get("supported") is True]
                        levels = levels or [None]
                    else:
                        effort = item.get("effort") or {}
                        if not isinstance(effort, dict):
                            raise ProviderIntegrityError("The DeepSeek effort metadata is invalid.")
                        native = effort.get("supported_levels")
                        levels = ["none", *_efforts(native)] if native else [None]
                    result.append({"model": name, "supported_efforts": _efforts(levels),
                                   "model_digest": None, "runtime_version": None})
                if len(result) > 256:
                    raise ProviderIntegrityError("The provider catalogue exceeds its bounded size.")
                if self.provider != "claude-api" or not value.get("has_more"):
                    if len({x["model"] for x in result}) != len(result):
                        raise ProviderIntegrityError("The provider catalogue contains ambiguous model identifiers.")
                    return result
                next_id = value.get("last_id")
                if not isinstance(next_id, str) or not next_id or len(next_id) > 200 or next_id == after:
                    raise ProviderIntegrityError("The provider catalogue pagination is invalid.")
                after = next_id
        raise ProviderIntegrityError("The provider catalogue exceeds its bounded page count.")

    def metadata(self, name):
        name = model_name(name)
        if self.provider == "glm-api":
            return {"model": name, "supported_efforts": glm_efforts(name), "model_digest": None, "runtime_version": None}
        value = next((x for x in self.discover() if x["model"] == name), None)
        if value is None:
            raise ConfigurationError("model-not-advertised", "This API connection does not advertise that model.")
        return value

    def adapter(self, model, effort, limits):
        return ApiAdapter(self, model, effort, limits)


class ApiAdapter:
    def __init__(self, backend, model, effort, limits):
        self.backend, self.model, self.effort, self.limits = backend, model, effort, limits

    def invoke(self, *, input_payload, output_schema, prompt_version, system_prompt):
        if not self.backend._slots.acquire(blocking=False):
            raise ProviderBusy("The bounded API provider capacity is in use before submission.")
        binding = None
        try:
            with ExitStack() as projection:
                try:
                    key, binding = projection.enter_context(self.backend.credential())
                except BlockingIOError:
                    raise ProviderBusy("This API connection is in use before submission.") from None
                if self.effort not in self.model["supported_efforts"]:
                    raise ProviderIntegrityError("The selected native model control is not supported.")
                if not self.limits.get("verification", False) and not self.backend.verification_current(self.model, binding):
                    raise ProviderIntegrityError("This connection's credential generation changed; verify the model again.")
                started = time.monotonic()
                prompt = system_prompt + "\nReturn only a JSON object matching this exact task schema. Never use tools.\n" + json.dumps(output_schema)
                content = json.dumps(input_payload, ensure_ascii=False)
                payload = {"model": self.model["model"], "stream": False,
                           "max_tokens": self.limits["max_output_tokens"]}
                if self.backend.provider == "claude-api":
                    payload.update(system=prompt, messages=[{"role": "user", "content": content}],
                                   output_config={"format": {"type": "json_schema", "schema": claude_grammar(output_schema)}})
                    if self.effort is not None:
                        payload["output_config"]["effort"] = self.effort
                else:
                    payload.update(messages=[{"role": "system", "content": prompt}, {"role": "user", "content": content}],
                                   response_format={"type": "json_object"})
                    if type(self.effort) is bool:
                        payload["thinking"] = {"type": "enabled" if self.effort else "disabled"}
                    elif self.effort is not None:
                        payload["reasoning_effort"] = self.effort
                value = self.backend._request(PRESETS[self.backend.provider]["path"], key, payload,
                    timeout=self.limits["timeout_seconds"], max_bytes=self.limits.get("max_output_bytes", 65536))
                if value.get("model") != self.model["model"]:
                    raise ProviderIntegrityError("The provider returned a different model identity.")
                if self.backend.provider == "claude-api":
                    blocks = value.get("content")
                    if value.get("stop_reason") != "end_turn" or not isinstance(blocks, list):
                        raise ApiOutputInvalid("The Claude response is not a complete final turn.")
                    text = [b.get("text") for b in blocks if isinstance(b, dict) and b.get("type") == "text"]
                    if len(text) != 1 or not isinstance(text[0], str) or any(
                            not isinstance(b, dict) or b.get("type") not in {"text", "thinking", "redacted_thinking"} for b in blocks):
                        raise ApiOutputInvalid("The Claude response is not one bounded final text result.")
                    final = text[0]
                    usage_map = {"input_tokens": "input_tokens", "output_tokens": "output_tokens"}
                else:
                    choices = value.get("choices")
                    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
                        raise ApiOutputInvalid("The provider returned ambiguous final choices.")
                    choice = choices[0]
                    message = choice.get("message")
                    if (choice.get("finish_reason") != "stop" or not isinstance(message, dict)
                            or message.get("role") != "assistant" or message.get("tool_calls") or message.get("refusal")
                            or not isinstance(message.get("content"), str)):
                        raise ApiOutputInvalid("The provider did not complete a final assistant response.")
                    final = message["content"]
                    usage_map = {"prompt_tokens": "input_tokens", "completion_tokens": "output_tokens"}
                try:
                    output = json.loads(final)
                    validate_output(output, output_schema)
                except (ValueError, OutputSchemaError):
                    raise ApiOutputInvalid(ApiOutputInvalid.operator_message) from None
                native_usage = value.get("usage")
                usage = {target: native_usage[source] for source, target in usage_map.items()
                         if isinstance(native_usage, dict) and type(native_usage.get(source)) is int and native_usage[source] >= 0}
                return ProviderResult(output=output, model_digest=None, runtime_version=None,
                    latency_ms=round((time.monotonic() - started) * 1000), usage=usage,
                    prompt_version=prompt_version, account_binding=binding)
        except (ProviderIntegrityError, ProviderOutputInvalid, ProviderCompletionUnknown, ProviderUnavailable, ProviderBusy) as error:
            error.account_binding = binding
            raise
        finally:
            self.backend._slots.release()
