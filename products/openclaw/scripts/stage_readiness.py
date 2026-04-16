#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from gateway_contract import compute_source_bundle_ref
from gateway_environment import telegram_overlay_runtime_active, telegram_overlay_state


SUSPEND_SENTINEL = "suspend-sentinel-configmap.yaml"
READINESS_RELATIVE_PATH = Path("environments/stage/promotion-readiness.yaml")
STAGE_CANDIDATE_RELATIVE_PATH = Path("environments/stage/release-candidate.yaml")
VERIFICATION_RELATIVE_PATH = Path("environments/stage/verification.yaml")
VERSIONS_RELATIVE_PATH = Path("environments/stage/versions.yaml")
KUSTOMIZATION_RELATIVE_PATH = Path("environments/stage/argocd/kustomization.yaml")
VERIFICATION_CATALOG_RELATIVE_PATH = Path("products/openclaw/verification-catalog.yaml")
DEFAULT_REQUIRED_STAGE_COMPONENTS = ("gateway", "secrets", "version")
VALID_CHECK_STATUSES = {"passed", "failed", "not_applicable", "waived", "blocked"}
DEFAULT_STAGE_CANDIDATE_NOTE = (
    "No recorded stage candidate yet. Build and record a governed stage artifact before approval."
)
DEFAULT_STAGE_VERIFICATION_NOTE = (
    "No recorded stage verification yet. Rehearse the current candidate on stage before approval."
)
COMPONENT_RESOURCE_MAP = {
    "gateway": "openclaw-gateway-app.yaml",
    "secrets": "platform-secrets-app.yaml",
    "version": "platform-version-app.yaml",
    "observability": "observability-app.yaml",
    "dashboards": "platform-dashboards-app.yaml",
}
RESOURCE_COMPONENT_MAP = {resource: component for component, resource in COMPONENT_RESOURCE_MAP.items()}


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def readiness_path(repo_root: Path) -> Path:
    return repo_root / READINESS_RELATIVE_PATH


def stage_candidate_path(repo_root: Path) -> Path:
    return repo_root / STAGE_CANDIDATE_RELATIVE_PATH


def verification_path(repo_root: Path) -> Path:
    return repo_root / VERIFICATION_RELATIVE_PATH


def versions_path(repo_root: Path) -> Path:
    return repo_root / VERSIONS_RELATIVE_PATH


def kustomization_path(repo_root: Path) -> Path:
    return repo_root / KUSTOMIZATION_RELATIVE_PATH


def verification_catalog_path(repo_root: Path) -> Path:
    return repo_root / VERIFICATION_CATALOG_RELATIVE_PATH


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def load_resources(path: Path) -> list[str]:
    resources = []
    in_resources = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if stripped == "resources:":
            in_resources = True
            continue
        if in_resources and stripped.startswith("- "):
            resources.append(stripped[2:].strip())
            continue
        if in_resources and stripped:
            break
    return resources


def components_for_resources(resources: list[str]) -> set[str]:
    return {
        RESOURCE_COMPONENT_MAP[resource]
        for resource in resources
        if resource in RESOURCE_COMPONENT_MAP
    }


def current_stage_components(repo_root: Path) -> set[str]:
    resources = load_resources(kustomization_path(repo_root))
    if resources == [SUSPEND_SENTINEL]:
        return set()
    return components_for_resources(resources)


def load_verification_catalog(repo_root: Path) -> dict:
    data = load_yaml(verification_catalog_path(repo_root))
    checks = data.get("checks") or {}
    if not checks:
        raise SystemExit(
            f"verification catalog is missing checks at {verification_catalog_path(repo_root)}"
        )
    return data


def default_required_check_ids(catalog: dict) -> list[str]:
    checks = catalog.get("checks") or {}
    return sorted(
        check_id
        for check_id, payload in checks.items()
        if payload.get("defaultRequiredForPromotion") is True
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
            "unknown verification checks: "
            + ", ".join(unknown)
            + f" (catalog: {verification_catalog_path(repo_root)})"
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


def snapshot_stage_candidate(repo_root: Path) -> dict:
    versions = load_yaml(versions_path(repo_root))
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
            "runtimeActive": telegram_overlay_runtime_active("stage", overlay),
            "sourceCommit": overlay["source"].get("commit"),
            "qualifiedBaseImage": overlay.get("qualifiedBaseImage"),
            "image": {
                "repository": overlay["image"].get("repository"),
                "tag": overlay["image"].get("tag"),
                "digest": overlay["image"].get("digest"),
            },
        },
        "requiredChecks": [],
        "capabilities": [],
    }


def default_stage_candidate(
    status: str = "pending-build",
    note: str = DEFAULT_STAGE_CANDIDATE_NOTE,
) -> dict:
    return {
        "schemaVersion": 1,
        "product": "openclaw",
        "environment": "stage",
        "status": status,
        "recordedAt": None,
        "recordedPlatformEngineeringCommit": None,
        "note": note,
        "candidate": empty_candidate_snapshot(),
    }


def empty_verification_ref() -> dict:
    return {
        "path": str(VERIFICATION_RELATIVE_PATH),
        "status": None,
        "verifiedAt": None,
        "candidateSourceBundleRef": None,
    }


def candidate_ref_for(payload: dict | None) -> dict:
    candidate = (payload or {}).get("candidate") or {}
    image = candidate.get("image") or {}
    return {
        "path": str(STAGE_CANDIDATE_RELATIVE_PATH),
        "status": (payload or {}).get("status"),
        "sourceBundleRef": candidate.get("sourceBundleRef"),
        "imageDigest": image.get("digest"),
        "requiredChecks": list(candidate.get("requiredChecks") or []),
    }


def verification_ref_for(payload: dict | None) -> dict:
    candidate_ref = (payload or {}).get("candidateRef") or {}
    return {
        "path": str(VERIFICATION_RELATIVE_PATH),
        "status": (payload or {}).get("status"),
        "verifiedAt": (payload or {}).get("verifiedAt"),
        "candidateSourceBundleRef": candidate_ref.get("sourceBundleRef"),
    }


def load_stage_candidate(repo_root: Path) -> dict:
    path = stage_candidate_path(repo_root)
    if not path.exists():
        return default_stage_candidate()
    return load_yaml(path)


def default_stage_verification(
    *,
    candidate_ref: dict | None = None,
    status: str = "pending",
    note: str = DEFAULT_STAGE_VERIFICATION_NOTE,
) -> dict:
    return {
        "schemaVersion": 1,
        "product": "openclaw",
        "environment": "stage",
        "status": status,
        "verifiedAt": None,
        "verifiedBy": None,
        "evidenceRef": None,
        "note": note,
        "candidateRef": candidate_ref or candidate_ref_for(None),
        "checks": [],
    }


def default_readiness(
    *,
    candidate_ref: dict | None = None,
    verification_ref: dict | None = None,
    status: str = "inactive",
    note: str = "",
) -> dict:
    return {
        "status": status,
        "requiredComponents": list(DEFAULT_REQUIRED_STAGE_COMPONENTS),
        "approvedAt": None,
        "approvedBy": None,
        "note": note,
        "candidateRef": candidate_ref or candidate_ref_for(None),
        "verificationRef": verification_ref or empty_verification_ref(),
        "approvedCandidate": empty_candidate_snapshot(),
        "approvedVerification": default_stage_verification(candidate_ref=candidate_ref_for(None)),
    }


def load_stage_verification(repo_root: Path) -> dict:
    path = verification_path(repo_root)
    if not path.exists():
        return default_stage_verification(candidate_ref=candidate_ref_for(load_stage_candidate(repo_root)))
    return load_yaml(path)


def reset_stage_release_candidate(repo_root: Path, *, status: str, note: str) -> dict:
    data = default_stage_candidate(status=status, note=note)
    write_yaml(stage_candidate_path(repo_root), data)
    return data


def reset_stage_verification(repo_root: Path, *, status: str = "pending", note: str) -> dict:
    data = default_stage_verification(
        candidate_ref=candidate_ref_for(load_stage_candidate(repo_root)),
        status=status,
        note=note,
    )
    write_yaml(verification_path(repo_root), data)
    return data


def record_stage_release_candidate(
    repo_root: Path,
    *,
    note: str,
    required_checks: list[str] | None = None,
    capabilities: list[str] | None = None,
) -> dict:
    catalog = load_verification_catalog(repo_root)
    effective_required_checks = sorted(required_checks or default_required_check_ids(catalog))
    ensure_known_check_ids(repo_root, catalog, effective_required_checks)

    candidate = snapshot_stage_candidate(repo_root)
    candidate["requiredChecks"] = effective_required_checks
    candidate["capabilities"] = sorted(
        capabilities or capability_tags_for_checks(catalog, effective_required_checks)
    )

    data = default_stage_candidate(status="candidate", note=note)
    data["recordedAt"] = now_utc()
    data["recordedPlatformEngineeringCommit"] = candidate["sourceRepos"]["platformEngineering"]
    data["candidate"] = candidate
    write_yaml(stage_candidate_path(repo_root), data)
    return data


def required_components(data: dict) -> tuple[str, ...]:
    configured = tuple(data.get("requiredComponents") or DEFAULT_REQUIRED_STAGE_COMPONENTS)
    return configured or DEFAULT_REQUIRED_STAGE_COMPONENTS


def reset_stage_promotion_readiness(repo_root: Path, status: str, note: str) -> dict:
    data = default_readiness(
        candidate_ref=candidate_ref_for(load_stage_candidate(repo_root)),
        verification_ref=verification_ref_for(load_stage_verification(repo_root)),
        status=status,
        note=note,
    )
    existing = load_yaml(readiness_path(repo_root)) if readiness_path(repo_root).exists() else {}
    configured = existing.get("requiredComponents")
    if configured:
        data["requiredComponents"] = list(configured)
    write_yaml(readiness_path(repo_root), data)
    return data


def normalize_check_results(catalog: dict, raw_results: list[str]) -> list[dict]:
    items: list[str] = []
    for raw in raw_results:
        for chunk in raw.replace("\n", ",").split(","):
            stripped = chunk.strip()
            if stripped:
                items.append(stripped)

    if not items:
        raise SystemExit(
            "at least one verification result is required; pass --check-result id=status or --check-results 'id=status,...'"
        )

    checks: dict[str, str] = {}
    for item in items:
        if "=" not in item:
            raise SystemExit(
                f"invalid verification result {item!r}; expected check-id=status"
            )
        check_id, status = (part.strip() for part in item.split("=", 1))
        if not check_id or not status:
            raise SystemExit(
                f"invalid verification result {item!r}; expected check-id=status"
            )
        if check_id not in catalog["checks"]:
            raise SystemExit(
                f"unknown verification check {check_id!r}; define it in {verification_catalog_path(Path('.').resolve())}"
            )
        if status not in VALID_CHECK_STATUSES:
            raise SystemExit(
                f"invalid verification status {status!r} for {check_id}; expected one of {', '.join(sorted(VALID_CHECK_STATUSES))}"
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


def require_stage_candidate(repo_root: Path) -> dict:
    data = load_stage_candidate(repo_root)
    candidate = data.get("candidate") or {}
    image = candidate.get("image") or {}
    if data.get("status") != "candidate":
        raise SystemExit(
            f"stage release candidate is {data.get('status') or 'unset'}; build and record a governed stage artifact before verification or approval"
        )
    if not candidate.get("sourceBundleRef") or not image.get("repository") or not image.get("tag") or not image.get("digest"):
        raise SystemExit(
            f"stage release candidate at {stage_candidate_path(repo_root)} is incomplete; record a governed stage artifact before verification or approval"
        )
    if not candidate.get("requiredChecks"):
        raise SystemExit(
            f"stage release candidate at {stage_candidate_path(repo_root)} is missing requiredChecks; re-record the candidate with a valid verification scope"
        )
    return data


def require_promotable_stage_contract(repo_root: Path) -> None:
    versions = load_yaml(versions_path(repo_root))
    overlay = telegram_overlay_state(versions)
    if overlay["status"] == "pending-build":
        raise SystemExit(
            "stage Telegram overlay lane is pinned but not recorded; build and record the overlay artifact before approving or validating promotion readiness"
        )
    if overlay["status"] == "candidate" and overlay.get("qualifiedBaseImage") != versions["gateway"]["build"]["baseImage"]:
        raise SystemExit(
            "stage Telegram overlay lane is qualified for a different OpenClaw base image; re-pin or disable the overlay lane before approving or validating promotion readiness"
        )


def record_stage_verification(
    repo_root: Path,
    *,
    verified_by: str,
    evidence_ref: str,
    note: str,
    raw_results: list[str],
) -> dict:
    candidate_document = require_stage_candidate(repo_root)
    catalog = load_verification_catalog(repo_root)
    checks = normalize_check_results(catalog, raw_results)

    data = default_stage_verification(
        candidate_ref=candidate_ref_for(candidate_document),
        status="recorded",
        note=note,
    )
    data["verifiedAt"] = now_utc()
    data["verifiedBy"] = verified_by
    data["evidenceRef"] = evidence_ref
    data["checks"] = checks
    write_yaml(verification_path(repo_root), data)
    return data


def validate_stage_verification(repo_root: Path) -> dict:
    candidate_document = require_stage_candidate(repo_root)
    verification = load_stage_verification(repo_root)
    if verification.get("status") != "recorded":
        raise SystemExit(
            f"stage verification is {verification.get('status') or 'unset'}; record verification evidence before approval"
        )
    if verification.get("candidateRef") != candidate_ref_for(candidate_document):
        raise SystemExit(
            "stage verification is stale; it does not point at the current stage release candidate"
        )
    if not verification.get("verifiedAt") or not verification.get("verifiedBy") or not verification.get("evidenceRef"):
        raise SystemExit(
            "stage verification is incomplete; verifiedAt, verifiedBy, and evidenceRef are required"
        )

    catalog = load_verification_catalog(repo_root)
    required_checks = list(candidate_document["candidate"].get("requiredChecks") or [])
    results = verification_results_map(verification)
    missing = [check_id for check_id in required_checks if check_id not in results]
    if missing:
        raise SystemExit(
            "stage verification is incomplete; missing required check results: "
            + ", ".join(sorted(missing))
        )

    for check_id in required_checks:
        status = results[check_id]
        accepted = set(catalog["checks"][check_id].get("acceptedReadinessStatuses") or ["passed"])
        if status not in accepted:
            raise SystemExit(
                f"stage verification is not promotion-ready; check {check_id} is {status!r}, expected one of {', '.join(sorted(accepted))}"
            )

    return verification


def approve_stage_promotion_readiness(repo_root: Path, approved_by: str, note: str) -> dict:
    require_promotable_stage_contract(repo_root)
    existing = load_yaml(readiness_path(repo_root)) if readiness_path(repo_root).exists() else {}
    expected_components = set(required_components(existing))
    components = current_stage_components(repo_root)
    missing = sorted(expected_components - components)
    if missing:
        raise SystemExit(
            "stage is not promotion-ready; missing required active components: " + ", ".join(missing)
        )

    candidate_document = require_stage_candidate(repo_root)
    verification_document = validate_stage_verification(repo_root)
    data = {
        "status": "approved",
        "requiredComponents": list(required_components(existing)),
        "approvedAt": now_utc(),
        "approvedBy": approved_by,
        "note": note,
        "candidateRef": candidate_ref_for(candidate_document),
        "verificationRef": verification_ref_for(verification_document),
        "approvedCandidate": candidate_document["candidate"],
        "approvedVerification": verification_document,
    }
    write_yaml(readiness_path(repo_root), data)
    return data


def validate_stage_promotion_readiness(repo_root: Path) -> dict:
    require_promotable_stage_contract(repo_root)
    data = load_yaml(readiness_path(repo_root))
    status = data.get("status")
    if status != "approved":
        raise SystemExit(
            f"stage promotion readiness is {status or 'unset'}; approval is required before promoting to prod"
        )

    components = current_stage_components(repo_root)
    missing = sorted(set(required_components(data)) - components)
    if missing:
        raise SystemExit(
            "stage promotion readiness is stale; required active components missing: " + ", ".join(missing)
        )

    candidate_document = require_stage_candidate(repo_root)
    verification_document = validate_stage_verification(repo_root)
    if (data.get("candidateRef") or {}) != candidate_ref_for(candidate_document):
        raise SystemExit(
            "stage promotion readiness is stale; the approved candidate reference no longer matches the current stage release candidate"
        )
    if (data.get("verificationRef") or {}) != verification_ref_for(verification_document):
        raise SystemExit(
            "stage promotion readiness is stale; the approved verification reference no longer matches the current stage verification record"
        )
    if (data.get("approvedCandidate") or {}) != candidate_document["candidate"]:
        raise SystemExit(
            "stage promotion readiness is stale; the approved candidate snapshot no longer matches environments/stage/release-candidate.yaml"
        )
    if (data.get("approvedVerification") or {}) != verification_document:
        raise SystemExit(
            "stage promotion readiness is stale; the approved verification snapshot no longer matches environments/stage/verification.yaml"
        )
    return data


def print_status(repo_root: Path) -> None:
    readiness = load_yaml(readiness_path(repo_root)) if readiness_path(repo_root).exists() else default_readiness(
        candidate_ref=candidate_ref_for(load_stage_candidate(repo_root)),
        verification_ref=verification_ref_for(load_stage_verification(repo_root)),
        status="inactive",
        note="Stage suspended; explicit resume and approval are required before the next prod promotion.",
    )
    candidate_document = load_stage_candidate(repo_root)
    verification_document = load_stage_verification(repo_root)
    status = readiness.get("status", "unset")
    note = readiness.get("note") or "none"
    approved_by = readiness.get("approvedBy") or "none"
    approved_at = readiness.get("approvedAt") or "none"
    components = ",".join(sorted(current_stage_components(repo_root))) or "none"
    required = ",".join(required_components(readiness))
    candidate_ref = candidate_ref_for(candidate_document)
    verification_ref = verification_ref_for(verification_document)
    verification_results = verification_results_map(verification_document)
    checks_summary = ",".join(f"{check_id}:{status}" for check_id, status in sorted(verification_results.items())) or "none"
    print(
        f"status={status} active={components} required_components={required} "
        f"candidate_status={candidate_ref['status'] or 'none'} "
        f"candidate_bundle={candidate_ref['sourceBundleRef'] or 'none'} "
        f"candidate_digest={candidate_ref['imageDigest'] or 'none'} "
        f"required_checks={','.join(candidate_ref['requiredChecks']) or 'none'} "
        f"verification_status={verification_ref['status'] or 'none'} "
        f"verified_by={verification_document.get('verifiedBy') or 'none'} "
        f"verified_at={verification_ref['verifiedAt'] or 'none'} "
        f"evidence_ref={verification_document.get('evidenceRef') or 'none'} "
        f"checks={checks_summary} "
        f"approved_by={approved_by} approved_at={approved_at} note={note}"
    )
