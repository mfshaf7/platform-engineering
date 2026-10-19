"""Separate proposed-owner purpose for the existing authenticated source issuer.

This does not admit an owner, authorize model writes, select an installation,
execute scaffold files, or expose a CLI mint override. OOS binds the reviewed
finite plan; Platform independently checks current canonical proposed Intake.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import yaml
import agent_source_identity as identity

PURPOSE = "trusted-owner-bootstrap"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
PATHS = frozenset({"AGENTS.md", "README.md", "Makefile", ".gitignore", "scripts/validate_owner.py",
    "tests/test_owner_bootstrap.py", "contracts/delivery-art-work-session/evidence-profile.json",
    "contracts/delivery-art-work-session/evidence-profile.schema.json", "contracts/delivery-art-work-session/source-bootstrap.json",
    ".github/workflows/validate.yaml"})
PROJECTION_FIELDS = frozenset({"purpose", "approval_ref", "bootstrap_plan_digest", "bootstrap_template_digest", "workflow_write"})


def digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def validate_subject(subject: Any) -> None:
    fields = {"kind", "owner_repo", "intake_entry_ref", "custody_receipt_digest", "template_digest", "plan_digest",
              "decision_ref", "workflow_write", "workflow_approval_ref", "allowed_paths"}
    if not isinstance(subject, dict) or set(subject) != fields or subject.get("kind") != "repository-bootstrap":
        raise identity.IdentityError("bootstrap requires its exact repository subject, not a Delivery or Prototype alias")
    owner = subject["owner_repo"]
    reference = subject["intake_entry_ref"]
    if not isinstance(owner, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", owner):
        raise identity.IdentityError("bootstrap owner identity is invalid")
    if (not isinstance(reference, dict) or set(reference) != {"id", "version", "digest"}
            or reference["id"] != f"repo:{owner}" or type(reference["version"]) is not int or reference["version"] < 1
            or not isinstance(reference["digest"], str) or not DIGEST.fullmatch(reference["digest"])):
        raise identity.IdentityError("bootstrap requires the exact current proposed Intake entry")
    for key in ("custody_receipt_digest", "template_digest", "plan_digest"):
        if not isinstance(subject[key], str) or not DIGEST.fullmatch(subject[key]):
            raise identity.IdentityError("bootstrap source plan and provenance digests are invalid")
    decision = subject["decision_ref"]
    if not isinstance(decision, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:/._#-]{2,255}", decision):
        raise identity.IdentityError("bootstrap requires its explicit accountable operator decision")
    paths = subject["allowed_paths"]
    if (not isinstance(paths, list) or not paths or any(not isinstance(path, str) or path not in PATHS for path in paths)
            or len(paths) != len(set(paths)) or paths != sorted(paths)):
        raise identity.IdentityError("bootstrap permits only a sorted unique subset of trusted owner-control files")
    workflow = subject["workflow_write"]
    if type(workflow) is not bool or workflow != (".github/workflows/validate.yaml" in paths):
        raise identity.IdentityError("bootstrap workflow permission must match the actual finite source writes")
    approval = subject["workflow_approval_ref"]
    if ((not workflow and approval is not None) or
            (workflow and (not isinstance(approval, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:/._#-]{2,255}", approval)))):
        raise identity.IdentityError("bootstrap workflow write requires separate operator permission approval")


def projection(subject: dict[str, Any]) -> dict[str, Any]:
    validate_subject(subject)
    return {"purpose": PURPOSE, "approval_ref": subject["decision_ref"], "bootstrap_plan_digest": subject["plan_digest"],
            "bootstrap_template_digest": subject["template_digest"], "workflow_write": subject["workflow_write"]}


def validate_projection(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) != PROJECTION_FIELDS or value.get("purpose") != PURPOSE:
        raise identity.IdentityError("bootstrap credential projection has invalid purpose fields")
    if (not isinstance(value["approval_ref"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9:/._#-]{2,255}", value["approval_ref"])
            or type(value["workflow_write"]) is not bool
            or any(not isinstance(value[key], str) or not DIGEST.fullmatch(value[key]) for key in ("bootstrap_plan_digest", "bootstrap_template_digest"))):
        raise identity.IdentityError("bootstrap credential projection binding is invalid")
    return dict(value)


def contract_from_snapshot(contract: identity.Contract, snapshot: identity.RepositoryInventorySnapshot, intent: dict[str, Any]) -> identity.Contract:
    subject = intent["subject"]
    validate_subject(subject)
    # Reuse the existing canonical schema/uniqueness/legacy protections; this
    # result alone still cannot grant ordinary source for the proposed owner.
    checked = identity.contract_from_record_snapshot(contract, snapshot)
    inventory, intake = yaml.safe_load(snapshot.inventory), yaml.safe_load(snapshot.intake)
    owner = subject["owner_repo"]
    if owner in inventory.get("repos", {}) or owner in inventory.get("retired_repos", {}):
        raise identity.IdentityError("bootstrap cannot replace current or retired Inventory authority")
    entry = intake.get("repos", {}).get(owner, {})
    record = entry.get("record", {})
    behavior = entry.get("validation_behavior", {})
    binding = entry.get("provider_repository", {})
    if (entry.get("status") != "proposed" or entry.get("requires_security_bindings") is not False
            or entry.get("security_review_subject", False) is not False
            or behavior.get("posture") != "covered-by-owner-repo" or behavior.get("wgcf_graph_role") != "product-runtime-source"
            or subject["intake_entry_ref"] != {"id": record.get("id"), "version": record.get("version"), "digest": digest(entry)}
            or record.get("id") != f"repo:{owner}"):
        raise identity.IdentityError("bootstrap requires current proposed source-only Intake with exact entry version/digest")
    if (set(binding) != {"provider", "provider_repository_id", "full_name"} or binding.get("provider") != "github"
            or binding.get("full_name") != intent["repository"] or str(binding.get("provider_repository_id")) != str(intent["repository_id"])):
        raise identity.IdentityError("bootstrap provider identity differs from the exact proposed owner")
    for name, other in intake.get("repos", {}).items():
        other_binding = other.get("provider_repository", {})
        if name != owner and (other_binding.get("provider_repository_id") == binding["provider_repository_id"]
                or str(other_binding.get("full_name", "")).casefold() == binding["full_name"].casefold()):
            raise identity.IdentityError("bootstrap provider identity is shared by another proposed owner")
    repository = identity.Repository(binding["full_name"], int(binding["provider_repository_id"]))
    if any(item.full_name.casefold() == repository.full_name.casefold() or item.provider_repository_id == repository.provider_repository_id for item in checked.repositories):
        raise identity.IdentityError("bootstrap cannot borrow an existing admitted provider identity")
    return identity.replace(checked, repositories=(repository,), required_permissions={**checked.required_permissions,
        **({"workflows": "write"} if subject["workflow_write"] else {})})
