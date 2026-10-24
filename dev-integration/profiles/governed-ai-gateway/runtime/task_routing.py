"""Explicit task routing after the existing gateway policy has admitted input."""
from __future__ import annotations

from typing import Any, Callable

from codex_adapter import ProviderCompletionUnknown
from model_configuration import ConfigurationError, InvocationJournal, ModelConfiguration, digest
from ollama_adapter import (OllamaAdapterError, ProviderBusy, ProviderOutputInvalid,
                            ProviderTimeout, ProviderUnavailable)
from strict_output_schema import OutputSchemaError, validate_output


class TaskRouting:
    def __init__(self, configuration: ModelConfiguration, journal: InvocationJournal,
                 adapter_factory: Callable):
        self.configuration, self.journal = configuration, journal
        self.adapter_factory = adapter_factory

    def invoke(self, *, request: dict[str, Any], profile: dict[str, Any], task: dict[str, Any],
               provider_input: dict[str, Any], system_prompt: str, prompt_version: str,
               complete: Callable) -> Any | None:
        task_id = profile["profile_id"] + "/" + task["task_kind"]
        snapshot = self.configuration.snapshot()
        selection = self.configuration.selection(snapshot, task_id)
        if selection is None:
            # Once revisioned routing is commissioned, even an unchanged source
            # binding is frozen. Clearing an override during a lost-response
            # retry must not dispatch the original invocation a second time.
            model_id = "source-binding:" + profile["profile_id"]
            selection = {"revision": snapshot["revision"], "configuration_digest": snapshot["digest"],
                         "task": task_id, "route": {"primary": {"model_id": model_id, "effort": None},
                         "fallbacks": [], "on_exhausted": "fail-closed"}, "models": {model_id: {
                             "backend_id": model_id, "model": profile["upstream_model"],
                             "model_digest": profile["model_digest"], "runtime_version": profile["runtime_version"]}}}
        identity = {"caller": request["caller_identity"]["caller_id"],
                    "operator": request["operator_identity"]["operator_id"],
                    "profile": profile["profile_id"], "task": task["task_kind"],
                    "invocation": request["caller_identity"]["decision_or_correlation_id"]}
        with self.journal.invocation(identity, digest(request), selection) as (record, fresh, finish):
            if not fresh:
                if record["state"] == "finished":
                    return record["result"]
                frozen = record["selection"]
                evidence = {"revision": frozen["revision"], "configuration_digest": frozen["configuration_digest"],
                            "task": frozen["task"], "attempts": [],
                            "selection_ref": "ai-routing-selection:" + digest({"selection": frozen, "identity": identity})[7:]}
                return complete(None, evidence, [], "provider-completion-unknown")
            attempts = []
            route = selection["route"]
            candidates = [route["primary"], *route["fallbacks"]]
            result, failure = None, "no-suitable-fallback"
            for candidate in candidates:
                model = selection["models"][candidate["model_id"]]
                attempt = {"backend_id": model["backend_id"], "model": model["model"],
                           "effort": candidate["effort"], "outcome": "pending"}
                attempts.append(attempt)
                try:
                    adapter = self.adapter_factory(model, candidate["effort"], profile["runtime_limits"])
                    result = adapter.invoke(input_payload=provider_input,
                                            output_schema=task["provider_output_schema_document"],
                                            system_prompt=system_prompt, prompt_version=prompt_version)
                    # Every backend, including injected/native extensions, must
                    # pass the same canonical schema before output is returned.
                    validate_output(result.output, task["provider_output_schema_document"])
                    attempt["outcome"] = "suggestion-produced"
                    failure = None
                    break
                except (ProviderUnavailable, ProviderBusy) as error:
                    # These errors must mean the backend did not submit a turn.
                    # Adapters must distinguish transport loss after submission.
                    attempt["outcome"] = error.code
                    failure = "no-suitable-fallback"
                except (ProviderCompletionUnknown, ProviderTimeout):
                    attempt["outcome"] = failure = "provider-completion-unknown"
                    break
                except (OutputSchemaError, ProviderOutputInvalid):
                    attempt["outcome"] = failure = "provider-output-invalid"
                    break
                except OllamaAdapterError as error:
                    attempt["outcome"] = failure = error.code
                    break
            evidence = {"revision": selection["revision"], "configuration_digest": selection["configuration_digest"],
                        "task": task_id, "attempts": attempts,
                        "selection_ref": "ai-routing-selection:" + digest({
                            "selection": selection, "identity": identity}).removeprefix("sha256:")}
            response = complete(result, evidence, attempts, failure)
            finish(response)
            return response
