from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


REQUIRED_CALLER_FIELDS = {
    "caller_id",
    "caller_repo",
    "caller_workflow",
    "decision_or_correlation_id",
    "requested_profile_id",
}


@dataclass(frozen=True)
class InvocationDecision:
    allowed: bool
    reasons: tuple[str, ...]
    profile: dict[str, Any] | None
    task: dict[str, Any] | None
    input_payload: dict[str, Any]
    compatibility_mode: bool


class GatewayPolicy:
    def __init__(self, profile_selections: dict[str, Any]) -> None:
        profiles = profile_selections.get("profiles")
        if not isinstance(profiles, dict) or not profiles:
            raise ValueError("profile selections must contain profiles")
        self.profiles = profiles

    def evaluate(self, request: dict[str, Any]) -> InvocationDecision:
        reasons: list[str] = []
        profile_id = request.get("profile_id")
        profile = self.profiles.get(profile_id)
        if not isinstance(profile, dict):
            return InvocationDecision(
                allowed=False,
                reasons=("profile-not-allowed",),
                profile=None,
                task=None,
                input_payload={},
                compatibility_mode=False,
            )

        caller_identity = request.get("caller_identity")
        if not isinstance(caller_identity, dict):
            caller_identity = {}
        missing_caller = sorted(
            field for field in REQUIRED_CALLER_FIELDS if not caller_identity.get(field)
        )
        if missing_caller:
            reasons.append("missing-caller-identity:" + ",".join(missing_caller))
        caller_id = caller_identity.get("caller_id")
        if caller_id not in profile.get("allowed_callers", []):
            reasons.append("caller-not-allowed")
        if isinstance(caller_id, str) and "/" in caller_id:
            expected_repo, expected_workflow = caller_id.split("/", 1)
            if (
                caller_identity.get("caller_repo") != expected_repo
                or caller_identity.get("caller_workflow") != expected_workflow
            ):
                reasons.append("caller-identity-mismatch")
        if caller_identity.get("requested_profile_id") != profile_id:
            reasons.append("profile-identity-mismatch")

        max_request_bytes = profile.get("runtime_limits", {}).get(
            "max_request_bytes"
        )
        request_bytes = len(
            json.dumps(request, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        )
        if not isinstance(max_request_bytes, int) or request_bytes > max_request_bytes:
            reasons.append("request-too-large-for-profile")

        task, compatibility_mode = self._resolve_task(request, profile, reasons)
        output_schema_ref = request.get("provider_output_schema_ref")
        if task is not None and output_schema_ref != task["provider_output_schema_ref"]:
            reasons.append("output-schema-mismatch")

        if profile.get("profile_status") != "active":
            reasons.append("profile-not-active")
        if profile.get("binding_status") != "active":
            reasons.append("binding-not-active")
        if profile.get("provider_route_status") != "active":
            reasons.append("provider-route-not-active")
        if profile.get("profile_activation_allowed") is not True:
            reasons.append("profile-activation-not-allowed")
        if profile.get("activation_eligible") is not True:
            reasons.append("model-selection-not-activation-eligible")

        operator_identity = request.get("operator_identity")
        if not isinstance(operator_identity, dict) or not operator_identity.get(
            "operator_id"
        ):
            reasons.append("operator-identity-missing")

        input_payload = request.get("input")
        if not isinstance(input_payload, dict):
            reasons.append("input-must-be-object")
            input_payload = {}
        if task is not None:
            self._validate_input(input_payload, task["input_contract"], reasons)

        return InvocationDecision(
            allowed=not reasons,
            reasons=tuple(dict.fromkeys(reasons)),
            profile=profile,
            task=task,
            input_payload=input_payload,
            compatibility_mode=compatibility_mode,
        )

    @staticmethod
    def _resolve_task(
        request: dict[str, Any],
        profile: dict[str, Any],
        reasons: list[str],
    ) -> tuple[dict[str, Any] | None, bool]:
        provided = request.get("task")
        compatibility_mode = provided is None
        if provided is None:
            default_kind = profile.get("default_task_kind")
            if not default_kind:
                reasons.append("task-contract-required")
                return None, compatibility_mode
            task = profile.get("task_contracts", {}).get(default_kind)
            return task if isinstance(task, dict) else None, compatibility_mode
        if not isinstance(provided, dict):
            reasons.append("task-contract-invalid")
            return None, compatibility_mode
        expected = profile.get("task_contracts", {}).get(provided.get("kind"))
        if not isinstance(expected, dict):
            reasons.append("task-kind-not-allowed")
            return None, compatibility_mode
        if set(provided) != {"kind", "contract_ref", "version"}:
            reasons.append("task-contract-invalid")
        if provided.get("contract_ref") != expected.get("contract_ref"):
            reasons.append("task-contract-mismatch")
        if provided.get("version") != expected.get("contract_version"):
            reasons.append("task-version-mismatch")
        return expected, compatibility_mode

    @staticmethod
    def _validate_input(
        input_payload: dict[str, Any],
        contract: dict[str, Any],
        reasons: list[str],
    ) -> None:
        allowed = set(contract.get("allowed_fields", []))
        required = set(contract.get("required_fields", []))
        unexpected = sorted(set(input_payload).difference(allowed))
        missing = sorted(
            field
            for field in required
            if field not in input_payload
            or input_payload[field] is None
            or input_payload[field] == ""
        )
        if unexpected:
            reasons.append("input-field-not-allowed:" + ",".join(unexpected))
        if missing:
            reasons.append("input-field-required:" + ",".join(missing))
        packet_fields = contract.get("model_safe_packet_required_fields", [])
        if packet_fields and "model_safe_packet" in input_payload:
            packet = input_payload["model_safe_packet"]
            if not isinstance(packet, dict) or any(
                not isinstance(packet.get(field), str) or not packet.get(field)
                for field in packet_fields
            ):
                reasons.append("model-safe-packet-invalid")
