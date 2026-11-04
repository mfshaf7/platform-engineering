"""Canonical installation source eligibility for the shared source issuer.

The validated record reference remains an internal instance authority. It is
never rewritten as Git inventory, and it grants no token or source effect.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any


NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,185}")
INSTANCE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")
OPERATIONS = {"bootstrap", "configure-verification", "ordinary-source"}


class InstanceSourceError(RuntimeError):
    """Source eligibility is unavailable, changed or outside its accepted scope."""


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def exact(value: Any, keys: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == keys


def hashed(value: Any) -> bool:
    return isinstance(value, str) and DIGEST.fullmatch(value) is not None


def policy_binding(value: Any) -> dict[str, Any]:
    if (not exact(value, {"repo", "revision", "contract_digest"}) or value["repo"] != "workspace-governance"
            or not isinstance(value["revision"], str) or not COMMIT.fullmatch(value["revision"]) or not hashed(value["contract_digest"])):
        raise InstanceSourceError("Source eligibility requires the current accepted Governance policy.")
    return dict(value)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON field")
        result[key] = value
    return result


def invalid_constant(_value):
    raise ValueError("non-finite JSON number")


@dataclass(frozen=True)
class InstanceSourceSnapshot:
    """Internal reader result; construction alone never authorizes a token."""

    instance_id: str
    owner_repo: str
    operation: str
    policy_ref: dict[str, Any]
    source_authority: dict[str, Any]


def validated_snapshot(value: Any, *, instance_id: str, owner: str, operation: str,
                       policy_ref: dict[str, Any]) -> InstanceSourceSnapshot | None:
    if not isinstance(instance_id, str) or not INSTANCE.fullmatch(instance_id) or not isinstance(owner, str) or not NAME.fullmatch(owner) or operation not in OPERATIONS:
        raise InstanceSourceError("Select one configured installation and canonical source owner.")
    policy_binding(policy_ref)
    authority = value.get("canonical_authority") if isinstance(value, dict) else None
    if isinstance(authority, dict) and authority.get("kind") == "legacy-git":
        if (not exact(value, {"schema_version", "canonical_authority", "record_id"}) or type(value["schema_version"]) is not int or value["schema_version"] != 1
                or not exact(authority, {"kind", "repo", "revision"}) or authority["repo"] != "workspace-governance"
                or authority["revision"] != policy_ref["revision"] or value["record_id"] != f"repo:{owner}"):
            raise InstanceSourceError("The legacy source proof changed its current Governance binding.")
        return None  # Only this positive proof selects the retained Git reader.
    expected_authority = {"kind": "internal-instance-record", "instance_id": instance_id, "record_id": f"repo:{owner}"}
    if (not exact(value, {"schema_version", "canonical_authority", "source_authority"}) or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or authority != expected_authority or not isinstance(value["source_authority"], dict)):
        raise InstanceSourceError("The source authority does not bind this installation and repository.")
    proof = value["source_authority"]
    required = {"schema_version", "owner_repo", "intake_entry_ref", "classification", "inventory_posture", "provider_repository", "owner_purpose",
                "source_bootstrap_eligible", "ordinary_source_eligible", "model_writes_allowed", "canonical_mutation", "runtime_activation",
                "canonical_authority", "record_ref", "policy_ref"}
    required |= {"validation_behavior"} if operation == "bootstrap" else {"inventory_entry_ref", "verification_setup_eligible"}
    if (not exact(proof, required) or type(proof["schema_version"]) is not int or proof["schema_version"] != 1 or proof["owner_repo"] != owner
            or proof["canonical_authority"] != expected_authority or proof["policy_ref"] != policy_ref
            or any(proof[key] is not False for key in ("model_writes_allowed", "canonical_mutation", "runtime_activation"))):
        raise InstanceSourceError("The source proof changed its policy, namespace or effect boundary.")
    reference = proof["record_ref"]
    if not exact(reference, {"version", "digest"}) or type(reference["version"]) is not int or reference["version"] < 1 or not hashed(reference["digest"]):
        raise InstanceSourceError("The source proof has no exact current record version.")
    entry = proof["intake_entry_ref"] if operation == "bootstrap" else proof["inventory_entry_ref"]
    if entry != {"id": f"repo:{owner}", **reference}:
        raise InstanceSourceError("Source eligibility does not cover the exact current record.")
    if operation == "bootstrap":
        if (proof["classification"] not in {"proposed", "admitted"} or proof["inventory_posture"] is not None
                or proof["source_bootstrap_eligible"] is not True or proof["ordinary_source_eligible"] is not False
                or not isinstance(proof["validation_behavior"], dict)
                or proof["validation_behavior"].get("posture") != "covered-by-owner-repo"
                or proof["validation_behavior"].get("wgcf_graph_role") != "product-runtime-source"):
            raise InstanceSourceError("Bootstrap requires current source-only Intake eligibility.")
    elif (proof["classification"] != "active" or proof["inventory_posture"] != "active" or proof["intake_entry_ref"] is not None
          or proof["source_bootstrap_eligible"] is not False or proof["ordinary_source_eligible"] is not True or proof["verification_setup_eligible"] is not True):
        raise InstanceSourceError("Source operation requires current active Inventory eligibility.")
    binding = proof["provider_repository"]
    if (not exact(binding, {"provider", "provider_repository_id", "full_name"}) or binding["provider"] != "github"
            or not isinstance(binding["provider_repository_id"], str) or not re.fullmatch(r"[1-9][0-9]*", binding["provider_repository_id"])
            or not isinstance(binding["full_name"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*", binding["full_name"])
            or not isinstance(proof["owner_purpose"], str) or not proof["owner_purpose"].strip()):
        raise InstanceSourceError("Source eligibility has no exact provider identity and purpose.")
    try:
        if len(proof["owner_purpose"].encode("utf-8", errors="strict")) > 8192:
            raise InstanceSourceError("Source purpose exceeds its owner metadata bound.")
    except UnicodeError:
        raise InstanceSourceError("Source purpose is not valid UTF-8.") from None
    return InstanceSourceSnapshot(instance_id, owner, operation, json.loads(json.dumps(policy_ref)), json.loads(json.dumps(proof)))


def contract_from_snapshot(contract, snapshot: InstanceSourceSnapshot, *, subject: dict[str, Any] | None = None):
    """Bind an already authenticated current proof to the existing source App.

    Platform selects the reader and its fixed installation. This function still
    validates every internal field; a constructed dataclass is not a grant.
    Account/installation selection and provider token checks remain with the
    existing issuer, after this read-only registration eligibility decision.
    """
    import agent_source_identity as identity
    try:
        current = validated_snapshot({"schema_version": 1,
            "canonical_authority": snapshot.source_authority.get("canonical_authority"),
            "source_authority": snapshot.source_authority}, instance_id=snapshot.instance_id,
            owner=snapshot.owner_repo, operation=snapshot.operation, policy_ref=snapshot.policy_ref)
    except (InstanceSourceError, AttributeError, TypeError):
        raise identity.IdentityError("current internal source eligibility is invalid") from None
    if current is None:
        raise identity.IdentityError("internal source eligibility cannot borrow legacy authority")
    proof = current.source_authority
    if subject is None:
        if current.operation != "ordinary-source":
            raise identity.IdentityError("ordinary source requires current active internal Inventory")
    else:
        import agent_source_bootstrap as bootstrap
        bootstrap.validate_subject(subject)
        operation = "configure-verification" if subject.get("operation") == "configure-verification" else "bootstrap"
        field = "inventory_entry_ref" if operation == "configure-verification" else "intake_entry_ref"
        if (current.operation != operation or subject["owner_repo"] != current.owner_repo
                or subject[field] != proof[field]):
            raise identity.IdentityError("owner setup does not bind its exact current internal record")
    binding = proof["provider_repository"]
    repository = identity.Repository(binding["full_name"], int(binding["provider_repository_id"]))
    if any(existing.provider_repository_id == repository.provider_repository_id or existing.full_name.casefold() == repository.full_name.casefold()
           for existing in contract.repositories):
        raise identity.IdentityError("internal registration cannot borrow an existing legacy provider identity")
    permissions = dict(contract.required_permissions)
    if subject is not None and subject["workflow_write"]:
        permissions["workflows"] = "write"  # Existing exact finite-plan approval remains mandatory.
    return identity.replace(contract, repositories=(repository,), required_permissions=permissions,
        repository_inventory_ref={"kind": "internal-instance-record", "instance_id": current.instance_id,
            "record_id": proof["canonical_authority"]["record_id"], "record_ref": dict(proof["record_ref"]),
            "policy_ref": dict(current.policy_ref), "operation": current.operation})

