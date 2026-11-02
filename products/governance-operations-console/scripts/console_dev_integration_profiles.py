"""Bounded committed-owner profile reads. No commands or admission effects."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from typing import Any

import yaml

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_BYTES = 262_144
LANES = {"prototype-devint", "integration-devint", "governed-devint"}
LIFECYCLES = {"proposed", "build-admitted", "active", "suspended", "retired"}


class ProfileReadError(ValueError):
    pass


def _text(value: Any, maximum: int = 4096) -> str | None:
    return value if isinstance(value, str) and value.strip() and len(value) <= maximum else None


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > 128:
        return []
    return list(dict.fromkeys(item for item in value if _text(item, 1024)))


def _git(repo: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                            check=False, timeout=10)
    if result.returncode:
        raise ProfileReadError("Committed profile owner source is unavailable.")
    return result.stdout


def committed_document(workspace: Path, owner: str, relative: str) -> tuple[dict, str]:
    if not SLUG.fullmatch(owner) or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ProfileReadError("Profile source must be an owner-relative regular Git file.")
    repo = workspace / owner
    revision = _git(repo, "rev-parse", "HEAD").decode().strip()
    listing = _git(repo, "ls-tree", "-l", revision, "--", relative).decode().split()
    if len(listing) < 5 or listing[0] not in {"100644", "100755"} or listing[1] != "blob":
        raise ProfileReadError("Profile source must be a committed regular file.")
    if not listing[3].isdigit() or int(listing[3]) > MAX_BYTES:
        raise ProfileReadError("Profile source exceeds its bounded read size.")
    raw = _git(repo, "show", f"{revision}:{relative}")
    value = yaml.safe_load(raw)
    if not isinstance(value, dict):
        raise ProfileReadError("Profile source must be a mapping.")
    return value, revision


def _private_document(path: Path, root: Path) -> dict | None:
    try:
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            return None
        if not path.is_file() or path.stat().st_size > MAX_BYTES:
            return None
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, yaml.YAMLError):
        return None


def _runtime_observation(policy: dict, profile_id: str, observed: datetime) -> dict:
    unknown = {"state": "unknown", "observed_at": None, "source_ref": None}
    if profile_id != policy["platform_operation_provider"]["profile_id"]:
        return unknown
    root = Path(policy["runtime_state_root"])
    marker = _private_document(root / "core-online.json", root)
    if not marker or marker.get("security_decision_digest") != policy.get("security", {}).get("decision_digest"):
        return unknown
    try:
        if marker.get("boot_id") != Path("/proc/sys/kernel/random/boot_id").read_text().strip():
            return unknown
        receipt_path = Path(marker["core_receipt"])
        if not receipt_path.resolve().is_relative_to((root / "receipts").resolve()):
            return unknown
        receipt = _private_document(receipt_path, root)
        if not receipt or receipt.get("artifact_type") != "governance-console-complete-runtime-receipt":
            return unknown
        if receipt.get("security", {}).get("decision_digest") != marker["security_decision_digest"]:
            return unknown
        claims = {key: value for key, value in receipt.items() if key != "content_digest"}
        digest = "sha256:" + hashlib.sha256(json.dumps(claims, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        if receipt.get("content_digest") != digest:
            return unknown
        timestamp = datetime.fromisoformat(receipt["recorded_at"].replace("Z", "+00:00"))
        age = (observed - timestamp).total_seconds()
        return {"state": "running" if 0 <= age <= 120 and receipt.get("proof", {}).get("core_online") is True else "unknown",
                "observed_at": receipt["recorded_at"],
                "source_ref": f"platform-observation://profiles/{profile_id}/core-online"}
    except (KeyError, OSError, TypeError, ValueError):
        return unknown


def read_profiles(policy: dict, *, query: dict | None = None, reader=committed_document,
                  observed: datetime | None = None) -> dict:
    """Read only registered committed owner files; caller never supplies a host path."""
    observed = observed or datetime.now(timezone.utc)
    query = query or {}
    if set(query) - {"limit", "offset", "q", "owner", "lifecycle", "lane", "profile_id"}:
        raise ProfileReadError("Unsupported profile query.")
    try:
        limit, offset = int(query.get("limit", 20)), int(query.get("offset", 0))
    except (TypeError, ValueError):
        raise ProfileReadError("Profile pagination must use bounded integers.") from None
    if not 1 <= limit <= 25 or not 0 <= offset <= 10000:
        raise ProfileReadError("Profile pagination is outside its allowed range.")
    if any(not isinstance(value, str) or len(value) > 200 for key, value in query.items() if key not in {"limit", "offset"}):
        raise ProfileReadError("Profile filters exceed their allowed size.")
    workspace = Path(policy["workspace_root"])
    registry, revision = reader(workspace, "workspace-governance", "contracts/developer-integration-profiles.yaml")
    inventory, inventory_revision = reader(workspace, "workspace-governance", "contracts/repos.yaml")
    if revision != inventory_revision:
        raise ProfileReadError("Profile registry changed during the owner read; refresh it.")
    entries = registry.get("profiles")
    owners = inventory.get("repos")
    if not isinstance(entries, dict) or len(entries) > 10000 or not isinstance(owners, dict):
        raise ProfileReadError("Canonical profile registry is invalid.")
    owner_repos = sorted(key for key, item in owners.items()
                         if SLUG.fullmatch(key) and isinstance(item, dict) and item.get("lifecycle") == "active")
    selected = []
    for profile_id, entry in sorted(entries.items()):
        if not SLUG.fullmatch(profile_id) or not isinstance(entry, dict):
            raise ProfileReadError("Canonical profile identity is invalid.")
        if query.get("profile_id") and profile_id != query["profile_id"]:
            continue
        if any(query.get(key) and query[key] != entry.get(field)
               for key, field in (("owner", "owner_repo"), ("lifecycle", "lifecycle"), ("lane", "lane_class"))):
            continue
        haystack = " ".join(str(entry.get(key, "")) for key in ("summary", "purpose", "owner_repo"))
        if query.get("q", "").casefold() not in f"{profile_id} {haystack}".casefold():
            continue
        selected.append((profile_id, entry))
    profiles = []
    versions = {}
    for profile_id, entry in selected[offset:offset + limit]:
        owner = entry.get("owner_repo")
        if owner not in owners or entry.get("lifecycle") not in LIFECYCLES or entry.get("lane_class") not in LANES:
            raise ProfileReadError("Profile registry ownership or lifecycle is invalid.")
        definition, owner_revision = {}, None
        gaps = []
        try:
            relative = entry.get("profile_path")
            if not isinstance(relative, str):
                raise ProfileReadError("Profile source path is not recorded.")
            definition, owner_revision = reader(workspace, owner, relative)
            if definition.get("profile_id") != profile_id:
                raise ProfileReadError("Profile owner identity does not match the registry.")
        except (ProfileReadError, OSError, yaml.YAMLError):
            definition = {}
            gaps.append("Owner profile definition is unavailable.")
        versions[owner] = owner_revision
        runtime = definition.get("runtime") or {}
        admission = entry.get("admission") or {}
        handoff = definition.get("stage_handoff") or entry.get("stage_handoff") or {}
        writes = definition.get("expected_writes")
        if not isinstance(writes, dict):
            writes = None
            gaps.append("Expected-write contract is not recorded as structured owner data.")
        persistence = definition.get("persistence")
        if runtime.get("state_model") == "persistent" and not isinstance(persistence, dict):
            persistence = None
            gaps.append("Detailed persistence contract is not recorded as structured owner data.")
        refs = [ref for ref in [admission.get("platform_acceptance_ref")] if _text(ref)]
        refs += [f"repo://{item['repo']}/{item['path']}" for item in admission.get("security_review_refs", [])
                 if isinstance(item, dict) and _text(item.get("repo"), 128) and _text(item.get("path"))]
        checks = _strings(handoff.get("required_checks"))
        state_root = workspace / ".dev-integration" / profile_id / policy["platform_operation_provider"]["operator_id"].removeprefix("operator:")
        # These are presence references, never a readiness conclusion or raw file content.
        reports = {key: f"devint://profiles/{profile_id}/{filename}" if _private_document(state_root / filename, workspace / ".dev-integration") else None
                   for key, filename in (("session_manifest_ref", "current-session.yaml"), ("promotion_report_ref", "promotion-report.yaml"))}
        profiles.append({
            "profile_id": profile_id, "owner_repo": owner, "lifecycle": entry["lifecycle"],
            "lane_class": entry["lane_class"], "purpose": _text(entry.get("purpose")) or _text(entry.get("summary")),
            "participating_repos": _strings(entry.get("source_repos")),
            "dependencies": _strings(entry.get("shared_dependencies")),
            "request_record_ref": _text((entry.get("request_record") or {}).get("ref")),
            "runtime": {"platform": _text(runtime.get("platform")), "state_model": runtime.get("state_model") if runtime.get("state_model") in {"persistent", "disposable"} else None,
                        "observation": _runtime_observation(policy, profile_id, observed)},
            "expected_writes": {"classification": writes.get("classification"), "targets": _strings(writes.get("targets"))} if writes else None,
            "persistence": {key: _text(persistence.get(key)) for key in ("justification", "retained_data_scope", "suspend_resume_semantics", "storage_size_or_class", "reset_semantics", "cutover_plan")} if isinstance(persistence, dict) else None,
            "security_owner": _text(entry.get("security_owner")), "security_triggers": None,
            "admission_refs": refs,
            "source": {"ref": f"repo://{owner}/{entry.get('profile_path', '')}", "registry_revision": revision, "owner_revision": owner_revision},
            "stage_handoff": {"owner_repo": _text(handoff.get("owner_repo")), "governed_surface": _text(handoff.get("governed_surface")),
                              "required_checks": [{"id": hashlib.sha256(label.encode()).hexdigest()[:16], "label": label} for label in checks],
                              "result": "unknown", "check_results": [], "smoke_summary_ref": None, **reports},
            "gaps": gaps,
        })
    return {"schema_version": 1, "source_version": f"registry:{revision}", "observed_at": observed.isoformat(),
            "owner_versions": versions, "profiles": profiles,
            "request_options": {"owner_repos": owner_repos, "lane_classes": sorted(LANES),
                                "runtime_platforms": ["local-k3s"], "state_models": ["disposable", "persistent"]},
            "page": {"offset": offset, "limit": limit, "total": len(selected),
                     "next_offset": offset + limit if offset + limit < len(selected) else None}}
