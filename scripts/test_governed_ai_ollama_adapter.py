from __future__ import annotations

import json
from pathlib import Path
import socket
import sys
import unittest
import urllib.error


RUNTIME_ROOT = (
    Path(__file__).resolve().parents[1]
    / "dev-integration/profiles/governed-ai-gateway/runtime"
)
sys.path.insert(0, str(RUNTIME_ROOT))

from ollama_adapter import (  # noqa: E402
    OllamaAdapter,
    ProviderIntegrityError,
    ProviderOutputInvalid,
    ProviderTimeout,
    ProviderUnavailable,
)


DIGEST = "500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41"


class FakeResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def valid_opener(request, **_kwargs):
    if request.full_url.endswith("/api/version"):
        return FakeResponse({"version": "0.32.14"})
    if request.full_url.endswith("/api/tags"):
        return FakeResponse({"models": [{"name": "qwen3:8b", "digest": DIGEST}]})
    request_body = json.loads(request.data)
    assert request_body["think"] is False
    assert "tools" not in request_body
    assert request_body["format"]["additionalProperties"] is False
    return FakeResponse(
        {
            "message": {
                "role": "assistant",
                "content": json.dumps(
                    {"suggested_decision": "proposed", "confidence": "medium"}
                ),
            },
            "prompt_eval_count": 30,
            "eval_count": 12,
        }
    )


def adapter(opener=valid_opener, **overrides) -> OllamaAdapter:
    values = {
        "base_url": "http://ollama.test",
        "model": "qwen3:8b",
        "expected_digest": DIGEST,
        "expected_runtime_version": "0.32.14",
        "retry_count": 0,
        "opener": opener,
    }
    values.update(overrides)
    return OllamaAdapter(**values)


class OllamaAdapterTests(unittest.TestCase):
    def test_valid_result_is_bounded_and_structured(self) -> None:
        result = adapter().classify({"operator_supplied_intake_notes": "A new component."})

        self.assertEqual(result.output["suggested_decision"], "proposed")
        self.assertEqual(result.output["confidence"], "medium")
        self.assertEqual(result.model_digest, DIGEST)
        self.assertEqual(result.runtime_version, "0.32.14")
        self.assertEqual(result.usage, {"prompt_tokens": 30, "completion_tokens": 12})

    def test_model_digest_drift_fails_closed(self) -> None:
        def opener(request, **_kwargs):
            if request.full_url.endswith("/api/version"):
                return FakeResponse({"version": "0.32.14"})
            return FakeResponse({"models": [{"name": "qwen3:8b", "digest": "wrong"}]})

        with self.assertRaises(ProviderIntegrityError):
            adapter(opener).classify({"operator_supplied_intake_notes": "test"})

    def test_extra_output_field_fails_closed(self) -> None:
        def opener(request, **_kwargs):
            if request.full_url.endswith("/api/version"):
                return FakeResponse({"version": "0.32.14"})
            if request.full_url.endswith("/api/tags"):
                return FakeResponse({"models": [{"name": "qwen3:8b", "digest": DIGEST}]})
            return FakeResponse(
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "suggested_decision": "admitted",
                                "confidence": "high",
                                "explanation": "not allowed",
                            }
                        )
                    }
                }
            )

        with self.assertRaises(ProviderOutputInvalid):
            adapter(opener).classify({"operator_supplied_intake_notes": "test"})

    def test_thinking_output_fails_closed(self) -> None:
        def opener(request, **_kwargs):
            if request.full_url.endswith("/api/version"):
                return FakeResponse({"version": "0.32.14"})
            if request.full_url.endswith("/api/tags"):
                return FakeResponse({"models": [{"name": "qwen3:8b", "digest": DIGEST}]})
            return FakeResponse(
                {
                    "message": {
                        "content": '{"suggested_decision":"proposed","confidence":"low"}',
                        "thinking": "hidden reasoning",
                    }
                }
            )

        with self.assertRaises(ProviderOutputInvalid):
            adapter(opener).classify({"operator_supplied_intake_notes": "test"})

    def test_unavailable_provider_fails_closed(self) -> None:
        def opener(_request, **_kwargs):
            raise urllib.error.URLError("offline")

        with self.assertRaises(ProviderUnavailable):
            adapter(opener).classify({"operator_supplied_intake_notes": "test"})

    def test_timeout_fails_closed(self) -> None:
        def opener(_request, **_kwargs):
            raise urllib.error.URLError(socket.timeout("slow"))

        with self.assertRaises(ProviderTimeout):
            adapter(opener).classify({"operator_supplied_intake_notes": "test"})

    def test_concurrency_exhaustion_fails_closed(self) -> None:
        instance = adapter(max_concurrency=1)
        self.assertTrue(instance._slots.acquire(blocking=False))
        try:
            with self.assertRaisesRegex(RuntimeError, "concurrency limit"):
                instance.classify({"operator_supplied_intake_notes": "test"})
        finally:
            instance._slots.release()


if __name__ == "__main__":
    unittest.main()
