#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


CATALOG_DIR = Path(__file__).resolve().parent
CONTRACT_PATH = CATALOG_DIR / "catalog-control-contract.json"
EXTENSION_PATH = CATALOG_DIR / "openproject_delivery_catalog_control.rb"
LOADER_PATH = CATALOG_DIR / "additional_environment.rb"

EXPECTED_ITEM_IDS = {
    "catalog-target-pi",
    "catalog-pi-planning-date",
    "catalog-iteration",
    "catalog-initiative-family",
    "catalog-lineage-role",
    "catalog-delivery-team",
    "catalog-owner-repo",
    "catalog-principal-lookup",
    "catalog-pi-objective-type",
    "catalog-blocker-disposition",
    "catalog-family-map-groups",
    "catalog-action-matrix",
    "catalog-evidence-kind",
    "catalog-receipt-category",
}
REQUIRED_ITEM_FIELDS = {
    "catalog_item_id",
    "group_id",
    "label",
    "description",
    "value_key",
    "source_authority",
    "backend_route",
    "owner_route",
    "create_authority",
    "console_capability",
    "gap_status",
    "lifecycle_state",
    "next_action_label",
    "next_action_detail",
    "evidence_refs",
    "source",
}
SOURCE_REQUIREMENTS = {
    "versions": {"usage_field"},
    "version-dates": {"parent_item_id"},
    "custom-options": {"field"},
    "registry": {"usage_field"},
    "principals": set(),
    "static": {"values"},
}
MUTABLE_SOURCE_KINDS = {"versions", "custom-options", "registry"}


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_contract(contract: dict[str, object], catalog_dir: Path = CATALOG_DIR) -> list[str]:
    errors: list[str] = []
    if contract.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if contract.get("contract_id") != "platform.openproject.delivery-catalog-control.v1":
        errors.append("contract_id must identify the bounded OpenProject Catalog control contract")
    if contract.get("project_identifier") != "workspace-delivery-art":
        errors.append("project_identifier must target Workspace Delivery ART")

    groups = contract.get("groups")
    items = contract.get("items")
    if not isinstance(groups, list) or not groups:
        errors.append("groups must be a non-empty list")
        groups = []
    if not isinstance(items, list) or not items:
        errors.append("items must be a non-empty list")
        items = []

    group_ids = [str(group.get("group_id")) for group in groups if isinstance(group, dict)]
    if len(group_ids) != len(set(group_ids)):
        errors.append("group_id values must be unique")

    item_ids: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            errors.append("every item must be an object")
            continue
        item_id = str(item.get("catalog_item_id"))
        item_ids.append(item_id)
        missing = sorted(REQUIRED_ITEM_FIELDS - item.keys())
        if missing:
            errors.append(f"{item_id}: missing fields: {', '.join(missing)}")
            continue
        if item["group_id"] not in group_ids:
            errors.append(f"{item_id}: unknown group_id {item['group_id']}")
        source = item["source"]
        if not isinstance(source, dict):
            errors.append(f"{item_id}: source must be an object")
            continue
        source_kind = source.get("kind")
        if source_kind not in SOURCE_REQUIREMENTS:
            errors.append(f"{item_id}: unsupported source kind {source_kind}")
            continue
        source_missing = sorted(SOURCE_REQUIREMENTS[source_kind] - source.keys())
        if source_missing:
            errors.append(f"{item_id}: source missing: {', '.join(source_missing)}")

        capability = item["console_capability"]
        expected_route = f"/v1/delivery-catalog/{item_id}/mutations"
        if capability == "request":
            if source_kind not in MUTABLE_SOURCE_KINDS:
                errors.append(f"{item_id}: request capability uses read-only source {source_kind}")
            if item["backend_route"] != expected_route:
                errors.append(f"{item_id}: request capability must use {expected_route}")
        elif capability in {"read_only", "owner_routed"}:
            if item["backend_route"] != "/v1/delivery-catalog/projection":
                errors.append(f"{item_id}: non-mutable capability must use the projection route")
        else:
            errors.append(f"{item_id}: unsupported console_capability {capability}")

        if not isinstance(item["evidence_refs"], list) or not item["evidence_refs"]:
            errors.append(f"{item_id}: evidence_refs must be a non-empty list")

    if len(item_ids) != len(set(item_ids)):
        errors.append("catalog_item_id values must be unique")
    actual_item_ids = set(item_ids)
    if actual_item_ids != EXPECTED_ITEM_IDS:
        missing = sorted(EXPECTED_ITEM_IDS - actual_item_ids)
        extra = sorted(actual_item_ids - EXPECTED_ITEM_IDS)
        errors.append(f"Catalog vocabulary mismatch; missing={missing}, extra={extra}")

    for path in (EXTENSION_PATH, LOADER_PATH):
        candidate = catalog_dir / path.name
        if not candidate.exists():
            errors.append(f"missing runtime file {candidate.name}")

    extension = (catalog_dir / EXTENSION_PATH.name).read_text(encoding="utf-8")
    required_extension_markers = {
        "/v1/delivery-catalog/projection",
        "OPENPROJECT_CATALOG_CONTROL_SHARED_SECRET",
        "ActiveSupport::SecurityUtils.secure_compare",
        "source_revision_stale",
        "idempotency_key",
        "readback_complete",
    }
    for marker in sorted(required_extension_markers):
        if marker not in extension:
            errors.append(f"runtime extension is missing control marker {marker}")

    loader = (catalog_dir / LOADER_PATH.name).read_text(encoding="utf-8")
    for marker in (
        "OPENPROJECT_CATALOG_CONTROL_EXTENSION_PATH",
        "OpenprojectDeliveryCatalogControl.register_setting!",
        "OpenprojectDeliveryCatalogControl::Middleware",
    ):
        if marker not in loader:
            errors.append(f"additional_environment loader is missing {marker}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the bounded OpenProject Catalog control contract.")
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    args = parser.parse_args()
    contract = load_contract(args.contract)
    errors = validate_contract(contract, args.contract.resolve().parent)
    if errors:
        raise SystemExit("\n".join(errors))
    print("OpenProject Catalog control contract valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
