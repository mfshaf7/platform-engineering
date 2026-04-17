#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from gateway_contract import compute_source_bundle_ref
from gateway_environment import load_yaml, telegram_overlay_runtime_active, telegram_overlay_state, write_yaml
from prod_lifecycle import current_prod_state


PROD_VERIFICATION_RELATIVE_PATH = Path("environments/prod/verification.yaml")
PROD_VERSIONS_RELATIVE_PATH = Path("environments/prod/versions.yaml")
PROD_VERIFICATION_CATALOG_RELATIVE_PATH = Path("products/openclaw/prod-verification-catalog.yaml")
VALID_CHECK_STATUSES = {"passed", "failed", "not_applicable", "waived", "blocked"}
DEFAULT_PROD_VERIFICATION_NOTE = (
    "No recorded prod smoke verification yet. Record post-promotion prod smoke after "
    "Argo reconciles the current prod candidate."
)


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def prod_verification_path(repo_root: Path) -> Path:
    return repo_root / PROD_VERIFICATION_RELATIVE_PATH


def prod_versions_path(repo_root: Path) -> Path:
    return repo_root / PROD_VERSIONS_RELATIVE_PATH


def prod_verification_catalog_path(repo_root: Path) -> Path:
    return repo_root / PROD_VERIFICATION_CATALOG_RELATIVE_PATH


def load_prod_verification_catalog(repo_root: Path) -> dict:
    data = load_yaml(prod_verification_catalog_path(repo_root))
    checks = data.get("checks") or {}
    if not checks:
        raise SystemExit(
            f"prod verification catalog is missing checks at {prod_verification_catalog_path(repo_root)}"
        )
    return data


def default_required_check_ids(catalog: dict) -> list[str]:
    checks = catalog.get("checks") or {}
    return sorted(
        check_id
        for check_id, payload in checks.items()
        if payload.get("defaultRequiredAfterPromotion") is True
    )


def capability_tags_for_checks(catalog: dict, check_ids: list[str]) -> list[str]:
    tags: set[str] = set()
    for check_id in check_ids:
        payload = catalog["checks"].get(check_id) or {}
        tags.update(payload.get("capabilityTags") or [])
    return sorted(tags)


def ensure_known_check_ids(repo_root: Path, catalog: dict, check_ids: list[str]) -> None:
    unknown = sorted(set(check_ids) - set((catalog.get("checks") or {}).keys()))
    if unknown:
        raise SystemExit(
            "unknown prod verification checks: "
            + ", ".join(unknown)
            + f" (catalog: {prod_verification_catalog_path(repo_root)})"
        )


def empty_candidate_snapshot() -> dict:
    return {
        "sourceBundleRef": None,
        "image": {
            "repository": None,
            "tag": None,
            "digest": None,
        },
        "build": {
            "baseImage": None,
            "dockerfile": None,
            "platforms": [],
        },
        "sourceRepos": {
            "telegramEnhanced": None,
            "hostBridge": None,
            "runtimeDistribution": None,
            "platformEngineering": None,
        },
        "telegramOverlay": {
            "status": "inactive",
            "runtimeActive": False,
            "sourceCommit": None,
            "qualifiedBaseImage": None,
            "image": {
                "repository": None,
                "tag": None,
                "digest": None,
            },
        },
        "requiredChecks": [],
        "capabilities": [],
    }


def snapshot_prod_candidate(repo_root: Path, *, required_checks: list[str] | None = None) -> dict:
    catalog = load_prod_verification_catalog(repo_root)
    effective_required_checks = sorted(required_checks or default_required_check_ids(catalog))
    ensure_known_check_ids(repo_root, catalog, effective_required_checks)

    versions = load_yaml(prod_versions_path(repo_root))
    source = versions["sourceRepos"]
    image = versions["gateway"]["image"]
    overlay = telegram_overlay_state(versions)
    return {
        "sourceBundleRef": compute_source_bundle_ref(versions),
        "image": {
            "repository": image["repository"],
            "tag": image["tag"],
            "digest": image["digest"],
        },
        "build": {
            "baseImage": versions["gateway"]["build"]["baseImage"],
            "dockerfile": versions["gateway"]["build"]["dockerfile"],
            "platforms": list(versions["gateway"]["publish"]["platforms"]),
        },
        "sourceRepos": {
            "telegramEnhanced": source["telegramEnhanced"]["commit"],
            "hostBridge": source["hostBridge"]["commit"],
            "runtimeDistribution": source["runtimeDistribution"]["commit"],
            "platformEngineering": source["platformEngineering"]["commit"],
        },
        "telegramOverlay": {
            "status": overlay["status"],
            "runtimeActive": telegram_overlay_runtime_active("prod", overlay),
            "sourceCommit": overlay["source"].get("commit"),
            "qualifiedBaseImage": overlay.get("qualifiedBaseImage"),
            "image": {
                "repository": overlay["image"].get("repository"),
                "tag": overlay["image"].get("tag"),
                "digest": overlay["image"].get("digest"),
            },
        },
        "requiredChecks": effective_required_checks,
        "capabilities": capability_tags_for_checks(catalog, effective_required_checks),
    }


def candidate_ref_for(candidate: dict | None) -> dict:
    payload = candidate or {}
    image = payload.get("image") or {}
    return {
        "path": str(PROD_VERSIONS_RELATIVE_PATH),
        "sourceBundleRef": payload.get("sourceBundleRef"),
        "imageDigest": image.get("digest"),
        "requiredChecks": list(payload.get("requiredChecks") or []),
    }


def default_prod_verification(
    *,
    candidate: dict | None = None,
    status: str = "pending",
    note: str = DEFAULT_PROD_VERIFICATION_NOTE,
) -> dict:
    candidate_snapshot = candidate or empty_candidate_snapshot()
    return {
        "schemaVersion": 1,
        "product": "openclaw",
        "environment": "prod",
        "status": status,
        "verifiedAt": None,
        "verifiedBy": None,
        "evidenceRef": None,
        "note": note,
        "candidateRef": candidate_ref_for(candidate_snapshot),
        "candidate": candidate_snapshot,
        "checks": [],
    }


def load_prod_verification(repo_root: Path) -> dict:
    path = prod_verification_path(repo_root)
    if not path.exists():
        status = "inactive" if current_prod_state(repo_root) != "live" else "pending"
        note = (
            "Prod OpenClaw is suspended; prod smoke verification remains inactive until the governed lifecycle returns to live."
            if status == "inactive"
            else DEFAULT_PROD_VERIFICATION_NOTE
        )
        return default_prod_verification(candidate=snapshot_prod_candidate(repo_root), status=status, note=note)
    return load_yaml(path)


def reset_prod_verification(repo_root: Path, *, status: str = "pending", note: str) -> dict:
    candidate = snapshot_prod_candidate(repo_root)
    data = default_prod_verification(candidate=candidate, status=status, note=note)
    write_yaml(prod_verification_path(repo_root), data)
    return data


def normalize_check_results(repo_root: Path, catalog: dict, raw_results: list[str]) -> list[dict]:
    items: list[str] = []
    for raw in raw_results:
        for chunk in raw.replace("\n", ",").split(","):
            stripped = chunk.strip()
            if stripped:
                items.append(stripped)

    if not items:
        raise SystemExit(
            "at least one prod verification result is required; pass --check-result id=status or "
            "--check-results 'id=status,...'"
        )

    checks: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(f"invalid prod verification result {item!r}; expected check-id=status")
        check_id, status = (part.strip() for part in item.split("=", 1))
        if not check_id or not status:
            raise SystemExit(f"invalid prod verification result {item!r}; expected check-id=status")
        if check_id not in catalog["checks"]:
            raise SystemExit(
                f"unknown prod verification check {check_id!r}; define it in {prod_verification_catalog_path(repo_root)}"
            )
        if status not in VALID_CHECK_STATUSES:
            raise SystemExit(
                f"invalid prod verification status {status!r} for {check_id}; expected one of "
                + ", ".join(sorted(VALID_CHECK_STATUSES))
            )
        checks[check_id] = status

    return [{"id": check_id, "status": checks[check_id]} for check_id in sorted(checks)]


def verification_results_map(data: dict) -> dict[str, str]:
    results: dict[str, str] = {}
    for entry in data.get("checks") or []:
        check_id = entry.get("id")
        status = entry.get("status")
        if check_id and status:
            results[check_id] = status
    return results


def require_prod_candidate(repo_root: Path) -> dict:
    candidate = snapshot_prod_candidate(repo_root)
    image = candidate.get("image") or {}
    source = candidate.get("sourceRepos") or {}
    if (
        not candidate.get("sourceBundleRef")
        or not image.get("repository")
        or not image.get("tag")
        or not image.get("digest")
    ):
        raise SystemExit(
            f"prod contract at {prod_versions_path(repo_root)} is incomplete; record a governed prod candidate "
            "before post-promotion verification"
        )
    missing_sources = sorted(key for key, value in source.items() if not value)
    if missing_sources:
        raise SystemExit(
            "prod contract is missing required source SHAs for post-promotion verification: "
            + ", ".join(missing_sources)
        )
    if not candidate.get("requiredChecks"):
        raise SystemExit(
            f"prod verification catalog at {prod_verification_catalog_path(repo_root)} resolved to no required checks"
        )
    return candidate


def record_prod_verification(
    repo_root: Path,
    *,
    verified_by: str,
    evidence_ref: str,
    note: str,
    raw_results: list[str],
) -> dict:
    if current_prod_state(repo_root) != "live":
        raise SystemExit(
            "prod OpenClaw is suspended; return the governed prod lifecycle to live before recording prod smoke/UAT evidence"
        )
    catalog = load_prod_verification_catalog(repo_root)
    candidate = require_prod_candidate(repo_root)
    checks = normalize_check_results(repo_root, catalog, raw_results)

    data = default_prod_verification(candidate=candidate, status="recorded", note=note)
    data["verifiedAt"] = now_utc()
    data["verifiedBy"] = verified_by
    data["evidenceRef"] = evidence_ref
    data["checks"] = checks
    write_yaml(prod_verification_path(repo_root), data)
    return data


def validate_prod_verification(repo_root: Path) -> dict:
    if current_prod_state(repo_root) != "live":
        raise SystemExit(
            "prod OpenClaw is suspended; prod verification is inactive until the governed prod lifecycle returns to live"
        )
    verification = load_prod_verification(repo_root)
    candidate = require_prod_candidate(repo_root)
    if verification.get("status") != "recorded":
        raise SystemExit(
            f"prod verification is {verification.get('status') or 'unset'}; record post-promotion prod smoke evidence"
        )
    if (verification.get("candidateRef") or {}) != candidate_ref_for(candidate):
        raise SystemExit("prod verification is stale; it does not point at the current prod contract")
    if (verification.get("candidate") or {}) != candidate:
        raise SystemExit("prod verification is stale; the candidate snapshot no longer matches environments/prod/versions.yaml")
    if not verification.get("verifiedAt") or not verification.get("verifiedBy") or not verification.get("evidenceRef"):
        raise SystemExit(
            "prod verification is incomplete; verifiedAt, verifiedBy, and evidenceRef are required"
        )

    catalog = load_prod_verification_catalog(repo_root)
    required_checks = list(candidate.get("requiredChecks") or [])
    results = verification_results_map(verification)
    missing = [check_id for check_id in required_checks if check_id not in results]
    if missing:
        raise SystemExit(
            "prod verification is incomplete; missing required check results: "
            + ", ".join(sorted(missing))
        )

    for check_id in required_checks:
        status = results[check_id]
        accepted = set(catalog["checks"][check_id].get("acceptedCompletionStatuses") or ["passed"])
        if status not in accepted:
            raise SystemExit(
                f"prod verification is not complete; check {check_id} is {status!r}, expected one of "
                + ", ".join(sorted(accepted))
            )

    return verification


def print_status(repo_root: Path) -> None:
    verification = load_prod_verification(repo_root)
    candidate = require_prod_candidate(repo_root)
    results = verification_results_map(verification)
    checks_summary = ",".join(f"{check_id}:{status}" for check_id, status in sorted(results.items())) or "none"
    print(
        f"lifecycle_state={current_prod_state(repo_root)} "
        f"status={verification.get('status') or 'unset'} "
        f"candidate_bundle={candidate.get('sourceBundleRef') or 'none'} "
        f"candidate_digest={(candidate.get('image') or {}).get('digest') or 'none'} "
        f"required_checks={','.join(candidate.get('requiredChecks') or []) or 'none'} "
        f"verified_by={verification.get('verifiedBy') or 'none'} "
        f"verified_at={verification.get('verifiedAt') or 'none'} "
        f"evidence_ref={verification.get('evidenceRef') or 'none'} "
        f"checks={checks_summary} "
        f"note={verification.get('note') or 'none'}"
    )
