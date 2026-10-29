from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import hmac
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
from typing import Any

from gateway_policy import GatewayPolicy, InvocationDecision
from ollama_adapter import OllamaAdapter, OllamaAdapterError, ProviderIntegrityError, SYSTEM_PROMPT
from model_configuration import ConfigurationError, InvocationJournal
from model_management import ModelManagement
from task_routing import TaskRouting
from urllib.parse import urlparse, parse_qs


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def prepare_audit_ledger(root: Path) -> Path:
    """Preserve a stopped legacy writer's ledger under the current nonroot owner.

    The retained volume already permits directory writes. No root permission,
    recursive ownership change, event rewriting or privilege escalation is used.
    The managed deployment stops the preceding writer before this handoff.
    """
    root.mkdir(parents=True, exist_ok=True)
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise OSError("The audit root must be a regular directory.")
    ledger = root / "audit-ledger.jsonl"
    try:
        original = ledger.lstat()
    except FileNotFoundError:
        descriptor = os.open(ledger, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
    else:
        if not stat.S_ISREG(original.st_mode):
            raise OSError("The retained audit ledger must be a regular file.")
        if original.st_uid != os.geteuid():
            temporary = None
            try:
                descriptor = os.open(ledger, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(descriptor, "rb") as source, tempfile.NamedTemporaryFile(
                    dir=root, prefix=".audit-owner-", delete=False,
                ) as target:
                    temporary = Path(target.name)
                    opened = os.fstat(source.fileno())
                    if (opened.st_dev, opened.st_ino) != (original.st_dev, original.st_ino):
                        raise OSError("The retained audit ledger changed before handoff.")
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                    target.flush()
                    os.fsync(target.fileno())
                current = ledger.lstat()
                if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
                    original.st_dev, original.st_ino, original.st_size, original.st_mtime_ns,
                ):
                    raise OSError("The retained audit ledger changed during handoff.")
                os.replace(temporary, ledger)
                temporary = None
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
    descriptor = os.open(ledger, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        current = os.fstat(descriptor)
        if not stat.S_ISREG(current.st_mode) or current.st_uid != os.geteuid():
            raise OSError("The audit ledger must belong to the serving owner.")
        os.fchmod(descriptor, 0o600)
    finally:
        os.close(descriptor)
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return ledger


class GatewayRuntime:
    def __init__(
        self,
        *,
        selections: dict[str, Any],
        audit_root: Path,
        compatibility_profile_id: str,
        provider_base_url: str | None = None,
        adapters: dict[str, Any] | None = None,
        management: ModelManagement | None = None,
    ) -> None:
        self.selections = selections
        self.profiles = selections["profiles"]
        self.policy = GatewayPolicy(selections)
        self.audit_root = audit_root
        self.audit_ledger = prepare_audit_ledger(audit_root)
        self.compatibility_profile_id = compatibility_profile_id
        self.management = management
        if compatibility_profile_id not in self.profiles:
            raise ValueError("compatibility profile is missing from selections")
        self.max_request_bytes = max(
            profile["runtime_limits"]["max_request_bytes"]
            for profile in self.profiles.values()
        )
        self.adapters = adapters or self._build_adapters(provider_base_url)
        self.routing = TaskRouting(management.configuration, InvocationJournal(audit_root / "invocations"),
                                   self._routed_adapter) if management else None

    def _routed_adapter(self, model, effort, limits):
        if model["backend_id"].startswith("source-binding:"):
            return self.adapters[model["backend_id"].removeprefix("source-binding:")]
        return self.management.adapter(model, effort, limits)

    @classmethod
    def from_environment(cls) -> "GatewayRuntime":
        selections_path = Path(
            os.environ.get(
                "GOVERNED_AI_PROFILE_SELECTIONS_PATH",
                "/app/model-profile-selections.json",
            )
        )
        selections = json.loads(selections_path.read_text(encoding="utf-8"))
        audit_root = Path(os.environ.get("GOVERNED_AI_AUDIT_ROOT", "/var/lib/governed-ai-gateway"))
        return cls(
            selections=selections,
            audit_root=Path(
                os.environ.get(
                    "GOVERNED_AI_AUDIT_ROOT", "/var/lib/governed-ai-gateway"
                )
            ),
            compatibility_profile_id=os.environ.get(
                "GOVERNED_AI_COMPATIBILITY_PROFILE_ID", "intake-classifier-v1"
            ),
            provider_base_url=os.environ.get("GOVERNED_AI_OLLAMA_BASE_URL"),
            management=ModelManagement.from_environment(selections, audit_root / "model-management"),
        )

    def _build_adapters(self, provider_base_url: str | None) -> dict[str, OllamaAdapter]:
        adapters: dict[str, OllamaAdapter] = {}
        for profile_id, profile in self.profiles.items():
            if profile["provider"] != "ollama":
                continue
            endpoint = provider_base_url or profile["endpoint_origin"]
            limits = profile["runtime_limits"]
            adapters[profile_id] = OllamaAdapter(
                base_url=endpoint,
                model=profile["upstream_model"],
                expected_digest=profile["model_digest"],
                expected_runtime_version=profile["runtime_version"],
                timeout_seconds=limits["timeout_seconds"],
                retry_count=0 if self.management else limits["retry_count"],
                max_concurrency=limits["max_concurrency"],
                max_output_tokens=limits["max_output_tokens"],
                conservative_completion=bool(self.management),
                max_response_bytes=65536 if self.management else None,
                shared_provider_limit=bool(self.management),
                keep_alive=0 if self.management else "5m",
            )
        return adapters

    def append_audit(self, event: dict[str, Any]) -> dict[str, Any]:
        self.audit_root.mkdir(parents=True, exist_ok=True)
        recorded = dict(event)
        recorded["event_time"] = utc_now()
        recorded["event_digest"] = canonical_digest(recorded)
        with self.audit_ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(recorded, sort_keys=True) + "\n")
        return recorded

    def latest_audit_event(self) -> dict[str, Any]:
        if not self.audit_ledger.exists():
            return {"event_count": 0, "latest": None}
        lines = [
            line
            for line in self.audit_ledger.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        return {
            "event_count": len(lines),
            "latest": json.loads(lines[-1]) if lines else None,
        }

    @staticmethod
    def selected_binding_evidence(profile: dict[str, Any]) -> dict[str, Any]:
        fields = (
            "profile_id",
            "profile_status",
            "environment",
            "binding_id",
            "binding_status",
            "provider",
            "provider_route",
            "provider_route_status",
            "upstream_model",
            "model_digest",
            "runtime_version",
            "profile_registry_digest",
            "access_plane_digest",
            "selection_digest",
            "selection_ref",
            "fallback_mode",
            "activation_eligible",
        )
        evidence = {field: profile[field] for field in fields}
        evidence["upstream_model_digest"] = evidence.pop("model_digest")
        evidence["provider_runtime_version"] = evidence.pop("runtime_version")
        return evidence

    def readiness(self) -> dict[str, Any]:
        compatibility = self.profiles[self.compatibility_profile_id]
        audit_ready = self.audit_storage_ready()
        # Eligibility is policy truth; readiness also observes actual provider
        # version and model digest. Share one bounded metadata probe across
        # identical bindings, without inference or an unbounded retry loop.
        bindings: dict[tuple, tuple[bool, str | None]] = {}
        provider_states: dict[str, tuple[bool, str | None]] = {}
        for profile_id, profile in self.profiles.items():
            adapter = self.adapters.get(profile_id)
            state = (False, "profile-ineligible")
            if not audit_ready:
                state = (False, "audit-storage-unavailable")
            elif profile["activation_eligible"] is True:
                key = (getattr(adapter, "base_url", profile["endpoint_origin"]),
                       profile["upstream_model"], profile["model_digest"], profile["runtime_version"])
                if key not in bindings:
                    if adapter is None:
                        bindings[key] = (False, "provider-unconfigured")
                    else:
                        try:
                            adapter.verify_binding()
                            bindings[key] = (True, None)
                        except ProviderIntegrityError:
                            bindings[key] = (False, "provider-integrity-failed")
                        except OllamaAdapterError:
                            bindings[key] = (False, "provider-unavailable")
                state = bindings[key]
            provider_states[profile_id] = state
        ready_profile_ids = sorted(
            profile_id
            for profile_id, profile in self.profiles.items()
            if provider_states[profile_id][0]
        )
        profile_states = {
            profile_id: {
                "status": profile["profile_status"],
                "activation_allowed": profile["profile_activation_allowed"],
                "activation_eligible": profile["activation_eligible"],
                "ready": profile_id in ready_profile_ids,
                "failure": provider_states[profile_id][1],
                "task_kinds": sorted(profile["task_contracts"]),
            }
            for profile_id, profile in sorted(self.profiles.items())
        }
        management_state = None
        if self.management:
            try:
                snapshot = self.management.configuration.snapshot()
                token_present = bool(Path(self.management.authority["token_file"]).read_text().strip())
                management_state = {"ready": token_present, "configuration_revision": snapshot["revision"],
                                    "provider_availability": "requires-explicit-verification-or-invocation"}
            except (OSError, ConfigurationError, KeyError):
                management_state = {"ready": False, "failure": "model-management-unavailable"}
        return {
            # The management API must stay reachable to repair selection or
            # sign in when every selected provider is unavailable. This is API
            # readiness, not a claim of provider entitlement or successful AI.
            "ready": audit_ready and (bool(ready_profile_ids) or bool(management_state and management_state["ready"])),
            "audit_storage_ready": audit_ready,
            **({"model_management": management_state} if management_state is not None else {}),
            "ready_profile_ids": ready_profile_ids,
            "profile_id": compatibility["profile_id"],
            "profile_status": compatibility["profile_status"],
            "compatibility_profile_ready": (
                compatibility["profile_id"] in ready_profile_ids
            ),
            "access_plane_activation_allowed": compatibility[
                "profile_activation_allowed"
            ],
            "upstream_provider": compatibility["provider"],
            "provider_route": compatibility["provider_route"],
            "upstream_model": compatibility["upstream_model"],
            "upstream_model_digest": compatibility["model_digest"],
            "provider_runtime_version": compatibility["runtime_version"],
            "selected_binding": self.selected_binding_evidence(compatibility),
            "profiles": profile_states,
            "provider_credential_required": compatibility["credential_required"],
            "raw_provider_token_projected": False,
        }

    def provider_custody(self) -> dict[str, Any]:
        compatibility = self.profiles[self.compatibility_profile_id]
        return {
            "provider_credential_required": compatibility["credential_required"],
            "provider_secret_available": False,
            "upstream_provider": compatibility["provider"],
            "provider_route": compatibility["provider_route"],
            "upstream_model": compatibility["upstream_model"],
            "provider_secret_ref": None,
            "consumer_provider_credentials_allowed": False,
            "provider_secret_projected_to_consumers": False,
            "token_value_projected": False,
        }

    def audit_storage_ready(self) -> bool:
        try:
            descriptor = os.open(self.audit_ledger, os.O_WRONLY | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                metadata = os.fstat(descriptor)
                return stat.S_ISREG(metadata.st_mode) and metadata.st_uid == os.geteuid() and stat.S_IMODE(metadata.st_mode) == 0o600
            finally:
                os.close(descriptor)
        except OSError:
            return False

    def invoke(self, request: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if not self.audit_storage_ready():
            return 503, {"policy_decision": "deny", "reasons": ["audit-storage-unavailable"]}
        decision = self.policy.evaluate(request)
        profile = decision.profile
        task = decision.task
        correlation_id = (
            (request.get("caller_identity") or {}).get("decision_or_correlation_id")
            or request.get("correlation_id")
        )
        event_base = self._event_base(request, decision, correlation_id)
        if not decision.allowed:
            event = self.append_audit(
                {
                    **event_base,
                    "outcome": "denied",
                    "provider_schema_valid": False,
                    "provider_latency_ms": 0,
                    "provider_usage": {},
                }
            )
            return 403, {
                "policy_decision": "deny",
                "reasons": list(decision.reasons),
                "audit_ref": f"local-ledger:{event['event_digest']}",
            }

        adapter = self.adapters.get(profile["profile_id"])
        if adapter is None and self.routing is None:
            event = self.append_audit(
                {
                    **event_base,
                    "outcome": "provider-unavailable",
                    "provider_schema_valid": False,
                    "provider_latency_ms": 0,
                    "provider_usage": {},
                }
            )
            return 503, {
                "policy_decision": "deny",
                "reasons": ["provider-unavailable"],
                "audit_ref": f"local-ledger:{event['event_digest']}",
            }

        system_prompt, provider_input, prompt_version = self._provider_request(
            decision
        )
        if self.routing:
            try:
                return self.routing.invoke(
                    request=request, profile=profile, task=task, provider_input=provider_input,
                    system_prompt=system_prompt, prompt_version=prompt_version,
                    complete=lambda result, selection, attempts, failure: self._routed_result(
                        request, decision, event_base, correlation_id, result, selection, attempts, failure),
                )
            except ConfigurationError as error:
                event = self.append_audit({**event_base, "outcome": error.code,
                                           "provider_schema_valid": False, "provider_latency_ms": 0, "provider_usage": {}})
                return 409, {"policy_decision": "deny", "reasons": [error.code],
                             "audit_ref": f"local-ledger:{event['event_digest']}"}
        try:
            provider_result = adapter.invoke(
                input_payload=provider_input,
                output_schema=task["provider_output_schema_document"],
                prompt_version=prompt_version,
                system_prompt=system_prompt,
            )
        except OllamaAdapterError as exc:
            event = self.append_audit(
                {
                    **event_base,
                    "outcome": exc.code,
                    "provider_schema_valid": False,
                    "provider_latency_ms": 0,
                    "provider_usage": {},
                }
            )
            return (504 if exc.code == "provider-timeout" else 503), {
                "policy_decision": "deny",
                "reasons": [exc.code],
                "audit_ref": f"local-ledger:{event['event_digest']}",
            }

        event = self.append_audit(
            {
                **event_base,
                "upstream_model_digest": provider_result.model_digest,
                "provider_runtime_version": provider_result.runtime_version,
                "prompt_version": provider_result.prompt_version,
                "outcome": "suggestion-produced",
                "provider_schema_valid": True,
                "provider_latency_ms": provider_result.latency_ms,
                "provider_usage": provider_result.usage,
            }
        )
        audit_ref = f"local-ledger:{event['event_digest']}"
        if decision.compatibility_mode:
            return 200, {
                "profile_id": profile["profile_id"],
                "policy_status": profile["profile_status"],
                "policy_decision": "allow",
                "decision_id": correlation_id,
                "generated_at": event["event_time"],
                "confidence": provider_result.output["confidence"],
                "caller_id": (request.get("caller_identity") or {}).get("caller_id"),
                "invocation_path": profile["invocation_path"],
                "binding_selection_ref": profile["selection_ref"],
                "suggested_decision": provider_result.output["suggested_decision"],
                "audit_ref": audit_ref,
            }
        return 200, {
            "profile_id": profile["profile_id"],
            "policy_status": profile["profile_status"],
            "policy_decision": "allow",
            "decision_id": correlation_id,
            "generated_at": event["event_time"],
            "caller_id": (request.get("caller_identity") or {}).get("caller_id"),
            "invocation_path": profile["invocation_path"],
            "binding_selection_ref": profile["selection_ref"],
            "task": {
                "kind": task["task_kind"],
                "contract_ref": task["contract_ref"],
                "version": task["contract_version"],
            },
            "output": provider_result.output,
            "audit_ref": audit_ref,
        }

    def _routed_result(self, request, decision, event_base, correlation_id, result, selection, attempts, failure):
        event_base = dict(event_base)
        if attempts:
            selected = attempts[-1]
            backend_id = selected["backend_id"]
            event_base.update(upstream_provider=self.management.configuration.backends.get(backend_id, {}).get(
                "provider", decision.profile["provider"]),
                provider_route=decision.profile["provider_route"] if backend_id.startswith("source-binding:") else backend_id,
                upstream_model=selected["model"])
        event = self.append_audit({**event_base, "effective_selection": selection,
                                   "outcome": failure or "suggestion-produced",
                                   "provider_schema_valid": failure is None,
                                   "provider_latency_ms": result.latency_ms if result else 0,
                                   "provider_usage": result.usage if result else {},
                                   "upstream_model_digest": result.model_digest if result else None,
                                   "provider_runtime_version": result.runtime_version if result else None,
                                   "prompt_version": result.prompt_version if result else None})
        audit_ref = f"local-ledger:{event['event_digest']}"
        if failure:
            response = {"policy_decision": "deny", "reasons": [failure], "audit_ref": audit_ref}
            if request.get("selection_evidence_version") == 1:
                response["effective_selection"] = selection
            return 503, response
        profile, task = decision.profile, decision.task
        response = {"profile_id": profile["profile_id"], "policy_status": profile["profile_status"],
                    "policy_decision": "allow", "decision_id": correlation_id, "generated_at": event["event_time"],
                    "caller_id": request["caller_identity"]["caller_id"], "invocation_path": profile["invocation_path"],
                    "binding_selection_ref": profile["selection_ref"], "audit_ref": audit_ref}
        if decision.compatibility_mode:
            response.update(confidence=result.output["confidence"], suggested_decision=result.output["suggested_decision"])
        else:
            response.update(task={"kind": task["task_kind"], "contract_ref": task["contract_ref"], "version": task["contract_version"]},
                            output=result.output)
        # Existing consumers retain their original output wire. New consumers
        # explicitly negotiate actual runtime selection evidence separately.
        if request.get("selection_evidence_version") == 1:
            response["effective_selection"] = selection
        return 200, response

    def _event_base(
        self,
        request: dict[str, Any],
        decision: InvocationDecision,
        correlation_id: str | None,
    ) -> dict[str, Any]:
        profile = decision.profile or {}
        task = decision.task or {}
        model_safe_packet = decision.input_payload.get("model_safe_packet")
        return {
            "correlation_id": correlation_id,
            "caller_identity": request.get("caller_identity") or {},
            "operator_identity": request.get("operator_identity") or {},
            "approved_profile_id": profile.get("profile_id"),
            "selected_binding": (
                self.selected_binding_evidence(profile) if profile else None
            ),
            "access_plane_activation_allowed": profile.get(
                "profile_activation_allowed", False
            ),
            "requested_profile_id": request.get("profile_id"),
            "invocation_path": profile.get("invocation_path"),
            "upstream_provider": profile.get("provider"),
            "provider_route": profile.get("provider_route"),
            "upstream_model": profile.get("upstream_model"),
            "upstream_model_digest": profile.get("model_digest"),
            "provider_runtime_version": profile.get("runtime_version"),
            "prompt_version": task.get("prompt_version"),
            "task_kind": task.get("task_kind"),
            "task_contract_ref": task.get("contract_ref"),
            "task_contract_version": task.get("contract_version"),
            "purpose": profile.get("purpose"),
            "output_schema_ref": task.get("provider_output_schema_ref"),
            "policy_decision": "allow" if decision.allowed else "deny",
            "policy_reasons": list(decision.reasons),
            "operator_acceptance_state": request.get(
                "operator_acceptance_state", "not-recorded"
            ),
            "override_reason": request.get("override_reason"),
            "model_safe_packet_ref": (model_safe_packet or {}).get("packet_ref"),
            "redaction_receipt_ref": (model_safe_packet or {}).get(
                "redaction_receipt_ref"
            ),
            "provider_secret_ref": None,
            "provider_secret_projected": False,
        }

    @staticmethod
    def _provider_request(
        decision: InvocationDecision,
    ) -> tuple[str, dict[str, Any], str]:
        task = decision.task
        payload = dict(decision.input_payload)
        if task["instruction_source"] == "gateway-profile":
            return SYSTEM_PROMPT, payload, task["prompt_version"]
        system_prompt = payload.pop("task_instruction")
        return (
            system_prompt,
            payload,
            f"{task['contract_ref']}:{task['task_kind']}:{task['contract_version']}",
        )


class Handler(BaseHTTPRequestHandler):
    server_version = "GovernedAIGatewayDevInt/2.0"

    @property
    def runtime(self) -> GatewayRuntime:
        return self.server.runtime  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: object) -> None:
        return

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        if length > self.runtime.max_request_bytes:
            raise ValueError("request-too-large")
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("request-must-be-object")
        return payload

    def do_GET(self) -> None:
        if self.path.startswith("/v1/model-management/"):
            self.management_request()
            return
        if self.path == "/healthz":
            self.send_json(200, {"status": "ok", "component": "governed-ai-gateway"})
            return
        if self.path == "/readyz":
            payload = self.runtime.readiness()
            self.send_json(200 if payload["ready"] else 503, payload)
            return
        if self.path == "/v1/provider/custody":
            self.send_json(200, self.runtime.provider_custody())
            return
        if self.path == "/v1/audit/events/latest":
            self.send_json(200, self.runtime.latest_audit_event())
            return
        self.send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path.startswith("/v1/model-management/"):
            self.management_request()
            return
        if self.path != "/v1/governed-ai/invoke":
            self.send_json(404, {"error": "not_found"})
            return
        try:
            request = self.read_json()
        except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.send_json(400, {"error": "invalid-request", "reason": str(exc)})
            return
        status, payload = self.runtime.invoke(request)
        self.send_json(status, payload)

    def management_request(self):
        manager = self.runtime.management
        if manager is None:
            self.send_json(503, {"error": "model-management-not-commissioned"})
            return
        try:
            authority = manager.authority
            token = Path(authority["token_file"]).read_text().strip()
            if not token or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + token) or \
                    self.headers.get("X-Platform-Caller") != authority["caller_id"] or \
                    self.headers.get("X-Platform-Operator") != authority["operator_id"]:
                self.send_json(403, {"error": "model-management-forbidden"})
                return
            parsed = urlparse(self.path)
            if self.command == "GET" and parsed.path == "/v1/model-management/backends" and not parsed.query:
                self.send_json(200, manager.describe_backends())
            elif self.command == "POST" and parsed.path == "/v1/model-management/health" and not parsed.query:
                if self.read_json() != {}:
                    raise ConfigurationError("invalid-command", "Provider observation refresh accepts no destinations or commands.")
                self.send_json(200, manager.refresh_health())
            elif self.command == "GET" and parsed.path == "/v1/model-management/configuration":
                query = parse_qs(parsed.query)
                if query and (set(query) != {"revision"} or len(query["revision"]) != 1 or not query["revision"][0].isdigit()):
                    raise ConfigurationError("invalid-command", "Select one retained configuration revision.")
                self.send_json(200, manager.configuration.snapshot(int(query["revision"][0]) if query else None))
            elif self.command == "GET" and parsed.path == "/v1/model-management/catalogue":
                query = parse_qs(parsed.query)
                if set(query) not in ({"backend_id"}, {"backend_id", "model"}) or len(query["backend_id"]) != 1 or len(query.get("model", [None])) != 1:
                    raise ConfigurationError("invalid-command", "Select exactly one admitted backend.")
                self.send_json(200, manager.catalogue(query["backend_id"][0], query.get("model", [None])[0]))
            elif self.command == "GET" and parsed.path == "/v1/model-management/account-login":
                query = parse_qs(parsed.query)
                if set(query) != {"command_id"} or len(query["command_id"]) != 1:
                    raise ConfigurationError("invalid-command", "Read the original account login command.")
                self.send_json(200, manager.logins.read(command_id=query["command_id"][0], actor=authority["operator_id"]))
            elif self.command == "POST" and parsed.path == "/v1/model-management/commands":
                self.send_json(200, manager.command(self.read_json(), actor=authority["operator_id"]))
            else:
                self.send_json(404, {"error": "not_found"})
        except ConfigurationError as error:
            self.send_json(409, {"error": error.code, "message": str(error)})
        except OllamaAdapterError as error:
            self.send_json(503, {"error": error.code})
        except (OSError, ValueError, KeyError, TypeError, BlockingIOError):
            self.send_json(503, {"error": "model-management-unavailable"})


def main() -> None:
    runtime = GatewayRuntime.from_environment()
    runtime.audit_root.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    server.runtime = runtime  # type: ignore[attr-defined]
    server.serve_forever()


if __name__ == "__main__":
    main()
