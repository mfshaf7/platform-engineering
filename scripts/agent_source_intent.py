"""Finite credential effects for authenticated, OOS-approved source intents.

Not a public mint API. The existing Platform provider authenticates OOS and
verifies its exact operator-approved command before calling this module. OOS
resolves canonical subject/start/session truth; Platform independently enforces
its repository/provider contract and retains all secret custody.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, Callable

import agent_source_identity as identity
import agent_source_bootstrap as bootstrap


ACTION_SET = {"agent-source.issue", "agent-source.renew", "agent-source.revoke"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+\-]{0,255}$")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")


class SourceIntentError(identity.IdentityError):
    """Only fixed, secret-free failure metadata may cross the provider boundary."""

    def __init__(self, code: str, message: str, *, retry_after: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.retry_after = retry_after


def digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise identity.IdentityError("source intent expiry must be a timezone-qualified timestamp")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise identity.IdentityError("source intent expiry is invalid") from None
    if result.utcoffset() is None:
        raise identity.IdentityError("source intent expiry must be timezone-qualified")
    return result


def read_state(path: Path) -> dict[str, Any]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077:
            raise identity.IdentityError("source intent state must be a private regular file")
        value = json.load(stream)
    if not isinstance(value, dict):
        raise identity.IdentityError("source intent state is invalid")
    return value


def validate_input(value: Any, *, caller_id: str, operator_id: str, _bootstrap: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"source_intent", "session_id"}:
        raise identity.IdentityError("source credential input must contain only source_intent and session_id")
    intent = value["source_intent"]
    fields = {
        "schema_version", "purpose", "intent_id", "caller_id", "operator_id", "subject",
        "source_start_digest", "repository", "repository_id", "installation_id",
        "landing_unit_id", "branch", "fetched_base", "human_reviewer_id", "expires_at",
        "supersedes_intent_digest",
    }
    if not isinstance(intent, dict) or set(intent) != fields or type(intent.get("schema_version")) is not int or intent["schema_version"] != 1:
        raise identity.IdentityError("source intent fields are invalid")
    if intent["purpose"] != (bootstrap.PURPOSE if _bootstrap else "ordinary-source"):
        raise identity.IdentityError("ordinary source issuance cannot authorize trusted bootstrap")
    if intent["caller_id"] != caller_id or intent["operator_id"] != operator_id:
        raise identity.IdentityError("source intent caller or operator binding is invalid")
    if not IDENTIFIER.fullmatch(str(intent["intent_id"])) or not DIGEST.fullmatch(str(intent["source_start_digest"])):
        raise identity.IdentityError("source intent identity or approved start digest is invalid")
    if intent["supersedes_intent_digest"] is not None and not DIGEST.fullmatch(str(intent["supersedes_intent_digest"])):
        raise identity.IdentityError("source intent predecessor digest is invalid")
    for key in ("repository_id", "installation_id"):
        if type(intent[key]) is not int or intent[key] <= 0:
            raise identity.IdentityError("source intent provider coordinates are invalid")
    for key in ("repository", "landing_unit_id", "branch", "fetched_base", "human_reviewer_id"):
        if not isinstance(intent[key], str):
            raise identity.IdentityError("source intent source coordinates are invalid")
    subject = intent["subject"]
    if not isinstance(subject, dict):
        raise identity.IdentityError("source intent requires a real subject binding")
    if _bootstrap:
        bootstrap.validate_subject(subject)
    elif subject.get("kind") == "delivery":
        if (set(subject) != {"kind", "work_item_ref", "snapshot_digest"}
                or not re.fullmatch(r"work-item-[1-9][0-9]*", str(subject["work_item_ref"]))
                or not DIGEST.fullmatch(str(subject["snapshot_digest"]))):
            raise identity.IdentityError("source intent Delivery subject is invalid")
    elif subject.get("kind") == "prototype":
        if set(subject) != {"kind", "prototype_id", "registry_ref", "registry_revision", "source_ref", "source_revision"}:
            raise identity.IdentityError("source intent Prototype subject fields are invalid")
        if not re.fullmatch(r"prototype:[a-z0-9]+(?:-[a-z0-9]+)*", str(subject["prototype_id"])):
            raise identity.IdentityError("source intent Prototype identity is invalid")
        slug = subject["prototype_id"].removeprefix("prototype:")
        if subject["registry_ref"] != f"record://prototypes/{slug}":
            raise identity.IdentityError("source intent registry identity is invalid")
        for key in ("registry_revision", "source_revision"):
            if not identity.REVISION_PATTERN.fullmatch(str(subject[key])):
                raise identity.IdentityError("source intent subject revision is invalid")
        source = subject["source_ref"]
        if (not isinstance(source, str) or not re.fullmatch(r"repo://[a-z0-9][a-z0-9._/-]*", source)
                or any(part in {"", ".", ".."} for part in source.removeprefix("repo://").split("/"))):
            raise identity.IdentityError("source intent source reference is invalid")
    else:
        raise identity.IdentityError("source intent subject kind is not admitted")
    session = value["session_id"]
    if session is not None and (not isinstance(session, str) or not IDENTIFIER.fullmatch(session)):
        raise identity.IdentityError("source intent session identity is invalid")
    timestamp(intent["expires_at"])
    return json.loads(json.dumps(value))


def validate_operation_input(value: Any, *, caller_id: str, operator_id: str) -> dict[str, Any]:
    """Explicit dispatcher for the authenticated Platform-operation boundary.

    Ordinary source consumers keep validate_input's default deny for bootstrap.
    """
    is_bootstrap = isinstance(value, dict) and isinstance(value.get("source_intent"), dict) and value["source_intent"].get("purpose") == bootstrap.PURPOSE
    return validate_input(value, caller_id=caller_id, operator_id=operator_id, _bootstrap=is_bootstrap)


def operate(
    args: argparse.Namespace, *, state_root: Path, action: str, command_id: str,
    input_value: dict[str, Any], caller_id: str, operator_id: str,
    inventory_reader: Callable[[], identity.RepositoryInventorySnapshot] | None = None,
) -> dict[str, Any]:
    """Execute only after authenticated provider command authorization.

    Durable non-secret intent/tombstone state lives inside the existing
    provider's private state root, not inside ephemeral credential storage.
    The existing projection lock serializes issuer/consumer access and intents
    that attempt to share a Landing Unit. No branch or worktree is created.
    """
    if action not in ACTION_SET or not isinstance(command_id, str) or not IDENTIFIER.fullmatch(command_id):
        raise identity.IdentityError("source credential action or command identity is invalid")
    value = validate_operation_input(input_value, caller_id=caller_id, operator_id=operator_id)
    intent, session_id = value["source_intent"], value["session_id"]
    bootstrap_projection = bootstrap.projection(intent["subject"]) if intent["purpose"] == bootstrap.PURPOSE else {}
    def admitted_contract() -> identity.Contract:
        if bootstrap_projection:
            if inventory_reader is None:
                raise identity.IdentityError("bootstrap requires the current trusted canonical record reader; no engineering CLI fallback")
            return bootstrap.contract_from_snapshot(identity.load_contract(args.contract), inventory_reader(), intent)
        return identity.load_operating_contract(args, inventory_reader=inventory_reader)
    # Revocation must remain possible after inventory retirement or suspension.
    if action == "agent-source.revoke":
        contract = identity.load_contract(args.contract)
        # Revocation uses immutable retained intent/projection bindings below,
        # never current admission. It cannot mint or broaden a token.
        repository = identity.Repository(intent["repository"], intent["repository_id"])
        contract = identity.replace(contract, repositories=(repository,))
        contract = identity.purpose_contract(contract, bootstrap_projection)
    else:
        contract = admitted_contract()
    contract = identity.select_installation(contract, intent["repository"])
    repository = identity._validate_session_inputs(
        contract, landing_unit_id=intent["landing_unit_id"], repository_name=intent["repository"],
        branch=intent["branch"], fetched_base=intent["fetched_base"], human_reviewer_id=intent["human_reviewer_id"],
    )
    if intent["repository_id"] != repository.provider_repository_id or intent["installation_id"] != contract.installation_id:
        raise identity.IdentityError("source intent does not match exact Platform provider coordinates")
    intent_digest = digest(intent)
    operation_digest = digest({"action": action, "input": value})
    root = identity.runtime_root(contract, args)
    directory = identity.session_directory(root, intent["landing_unit_id"])
    # This path is derived by Platform, never selected by an HTTP request.
    path = state_root / "source-intents" / f"{directory.name}.json"
    with identity.projection_lock(contract, root):
        alias = state_root / "source-intent-ids" / f"{hashlib.sha256(intent['intent_id'].encode()).hexdigest()}.json"
        alias_value = {"intent_digest": intent_digest, "landing_unit_id": intent["landing_unit_id"]}
        if alias.exists():
            if read_state(alias) != alias_value:
                raise identity.IdentityError("source intent identity is already bound to different source truth")
        state = None
        successor_admitted = False
        if path.exists():
            state = read_state(path)
            if state.get("intent_digest") != digest(state.get("intent")):
                raise identity.IdentityError("source intent state digest is invalid")
            if state.get("intent_digest") != intent_digest or state.get("intent") != intent:
                historical_path = state_root / "source-intent-history" / f"{intent_digest.removeprefix('sha256:')}.json"
                if historical_path.exists():
                    historical = read_state(historical_path)
                    recorded = historical.get("operations", {}).get(command_id)
                    if historical.get("intent") == intent and recorded is not None and recorded["digest"] == operation_digest:
                        return recorded["receipt"]
                    raise identity.IdentityError("source intent is superseded; historical commands cannot act on its successor")
                previous = state["intent"]
                previous_subject = previous["subject"]
                subject_key = {"delivery": "work_item_ref", "prototype": "prototype_id", "repository-bootstrap": "owner_repo"}[previous_subject["kind"]]
                same_subject = (intent["subject"].get("kind") == previous_subject["kind"]
                                and intent["subject"].get(subject_key) == previous_subject[subject_key])
                unchanged = ("caller_id", "operator_id", "repository", "repository_id", "installation_id", "landing_unit_id", "human_reviewer_id")
                current = identity.read_credential(contract, directory)
                if (action not in {"agent-source.issue", "agent-source.revoke"} or state["state"] != "revoked" or state["pending"] is not None or current is not None
                        or intent["supersedes_intent_digest"] != state["intent_digest"]
                        or intent["intent_id"] == previous["intent_id"] or not same_subject
                        or any(intent[key] != previous[key] for key in unchanged)):
                    raise identity.IdentityError("Landing Unit is already bound to another approved source intent; an exact revoked predecessor is required")
                history_path = state_root / "source-intent-history" / f"{state['intent_digest'].removeprefix('sha256:')}.json"
                identity.write_json_atomic(history_path, state)
                state = None
                successor_admitted = True
        current = identity.read_credential(contract, directory)
        if state is None:
            if action == "agent-source.renew" or current is not None:
                raise identity.IdentityError("source intent must be issued first; existing credentials cannot be borrowed")
            if intent["supersedes_intent_digest"] is not None and not successor_admitted:
                raise identity.IdentityError("source intent predecessor is not a retired Platform intent")
            state = {"schema_version": 1, "intent": intent, "intent_digest": intent_digest,
                     "session_id": session_id, "state": "approved", "pending": None, "operations": {}}
        recorded = state["operations"].get(command_id)
        if recorded is not None:
            if recorded["digest"] != operation_digest:
                raise identity.IdentityError("source credential command replay conflicts with its original input")
            return recorded["receipt"]
        if state["state"] == "revoked" and action != "agent-source.revoke":
            raise identity.IdentityError("revoked source intent cannot issue or renew credentials")
        if state["session_id"] is not None and session_id != state["session_id"]:
            raise identity.IdentityError("source intent is bound to a different session")
        if session_id is not None:
            state["session_id"] = session_id
        now = datetime.now(timezone.utc)
        if action != "agent-source.revoke" and timestamp(intent["expires_at"]) <= now:
            raise SourceIntentError("platform_source_intent_expired", "The approved source intent has expired.")
        if action != "agent-source.revoke" and (root / contract.suspension_filename).exists():
            raise identity.IdentityError("Agent source token issuance is suspended")
        binding = {
            "landing_unit_id": intent["landing_unit_id"], "repository": intent["repository"],
            "repository_id": intent["repository_id"], "installation_id": intent["installation_id"],
            "branch": intent["branch"], "fetched_base": intent["fetched_base"],
            "human_reviewer_id": intent["human_reviewer_id"],
        }
        credential_identity = {"identity_id": contract.identity_id, "logical_agent_id": contract.logical_agent_id,
                               "provider_principal": contract.provider_principal, "app_id": contract.app_id}
        if current is not None and ((not bootstrap_projection and "purpose" in current)
                or any(current.get(key) != expected for key, expected in {**binding, **credential_identity, **bootstrap_projection}.items())):
            raise identity.IdentityError("projected credential differs from the approved source intent")
        if not alias.exists():
            identity.write_json_atomic(alias, alias_value)
        pending = state["pending"]
        if pending is not None:
            if pending.get("stage") == "preparing":
                # Custody/provider preflight failed before the actual mint call.
                # Do not impose an unknown-issuance wait on a known no-mint phase.
                state["pending"] = None
                pending = None
        if pending is not None:
            if pending["command_id"] != command_id or pending["digest"] != operation_digest:
                if action != "agent-source.revoke":
                    raise identity.IdentityError("recover the original uncertain credential operation first")
            elif action != "agent-source.revoke":
                # A completed atomic projection can recover a lost acknowledgement.
                if current is not None and current["token_expires_at"] != pending["prior_expiry"]:
                    pass
                elif now < timestamp(pending["started_at"]) + timedelta(seconds=contract.maximum_token_lifetime_seconds):
                    deadline = timestamp(pending["started_at"]) + timedelta(seconds=contract.maximum_token_lifetime_seconds)
                    raise SourceIntentError("platform_source_issuance_uncertain", "Credential issuance outcome uncertain; retry the original operation after maximum token expiry.", retry_after=deadline.isoformat().replace("+00:00", "Z"))
                else:
                    pending = None
        if action == "agent-source.revoke":
            # Persist the tombstone BEFORE revoking, so a crash cannot reopen intent.
            state["state"] = "revoked"
            identity.write_json_atomic(path, state)
            if current is not None:
                identity.safe_revoke(identity.provider_client(contract, args), current["token"])
                identity._remove_session(directory)
            elif pending is not None and now < timestamp(pending["started_at"]) + timedelta(seconds=contract.maximum_token_lifetime_seconds):
                deadline = timestamp(pending["started_at"]) + timedelta(seconds=contract.maximum_token_lifetime_seconds)
                raise SourceIntentError("platform_source_revocation_expiry_pending", "Source intent revoked; unprojected issuance remains uncertain until maximum token expiry.", retry_after=deadline.isoformat().replace("+00:00", "Z"))
            outcome, expiry = "revoked", None
        else:
            remaining = (timestamp(current["token_expires_at"]) - now).total_seconds() if current else 0
            if action == "agent-source.issue" and state["state"] == "issued" and remaining <= contract.rotate_before_expiry_seconds:
                raise SourceIntentError("platform_source_renewal_required", "Credential renewal is required; issue replay does not rotate.")
            if current is None or remaining <= contract.rotate_before_expiry_seconds:
                if pending is None:
                    state["pending"] = {"command_id": command_id, "digest": operation_digest,
                                        "stage": "preparing",
                                        "prior_expiry": current["token_expires_at"] if current else None,
                                        "started_at": now.isoformat().replace("+00:00", "Z")}
                    identity.write_json_atomic(path, state)
                    issue_args = argparse.Namespace(**vars(args))
                    for key in ("landing_unit_id", "branch", "fetched_base", "human_reviewer_id"):
                        setattr(issue_args, key, intent[key])
                    if bootstrap_projection:
                        issue_args.purpose = bootstrap.PURPOSE
                        issue_args.approval_ref = bootstrap_projection["approval_ref"]
                        issue_args._trusted_bootstrap_projection = bootstrap_projection
                    def before_issue() -> None:
                        # Persist immediately before the real provider mint, not
                        # before Vault or provider-identity preflight.
                        if timestamp(intent["expires_at"]) <= datetime.now(timezone.utc):
                            raise SourceIntentError("platform_source_intent_expired", "The approved source intent has expired.")
                        if inventory_reader is not None:
                            current_contract = identity.select_installation(
                                admitted_contract(), intent["repository"],
                            )
                            current_repository = identity.expected_repository(current_contract, intent["repository"])
                            if (current_repository != repository or current_contract.installation_id != contract.installation_id):
                                raise identity.IdentityError("canonical source admission changed before credential issuance")
                        state["pending"]["stage"] = "issuing"
                        state["pending"]["started_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
                        identity.write_json_atomic(path, state)
                    current = identity.deliver_locked(contract, issue_args, repository, directory, current, before_issue=before_issue)
                elif current is None:
                    raise identity.IdentityError("credential projection could not be recovered")
                outcome = "issued" if action == "agent-source.issue" else "renewed"
            else:
                outcome = "current"
            expiry = current["token_expires_at"]
            state["state"] = "issued"
        state["pending"] = None
        result = {
            "schema_version": 1, "artifact_type": "source-intent-credential-receipt",
            "command_id": command_id, "action": action, "outcome": outcome,
            "source_intent_digest": intent_digest, "source_intent_id": intent["intent_id"],
            "supersedes_intent_digest": intent["supersedes_intent_digest"],
            "subject": intent["subject"], "session_id": state["session_id"], **binding,
            "caller_id": caller_id, "operator_id": operator_id, "source_start_digest": intent["source_start_digest"],
            **credential_identity, "definition_digest": contract.contract_digest,
            "permissions": dict(contract.required_permissions),
            "token_expires_at": expiry, "authorization_expires_at": intent["expires_at"],
            "recorded_at": now.isoformat().replace("+00:00", "Z"), "secret_values_embedded": False,
        }
        if bootstrap_projection:
            result["purpose"] = bootstrap.PURPOSE
        result["receipt_digest"] = digest(result)
        state["operations"][command_id] = {"digest": operation_digest, "receipt": result}
        identity.write_json_atomic(path, state)
        return result
