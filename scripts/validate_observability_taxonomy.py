#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml


POLICY_PATH = Path("docs/components/observability/validation-policy.yaml")


def load_yaml_mapping(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected a YAML mapping")
    return data


def resolve_relative_path(base: Path, raw_path: str) -> Path:
    return (base / raw_path).resolve()


def resolve_model_value(model: dict[str, Any], dotted_path: str) -> Any:
    current: Any = model
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise SystemExit(f"model path {dotted_path!r} is missing at {part!r}")
        current = current[part]
    return current


def iter_rule_files(repo_root: Path, patterns: list[str]) -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in patterns:
        for path in sorted(repo_root.glob(pattern)):
            if not path.is_file():
                continue
            if path in seen:
                continue
            seen.add(path)
            files.append(path)
    return files


def infer_lane_from_path(path: Path) -> str | None:
    for part in path.parts:
        if part == "prod":
            return "prod"
        if part == "stage":
            return "stage"
    return None


def validate_expected_mapping(
    errors: list[str],
    rel_path: str,
    context: str,
    mapping: dict[str, Any],
    expected: dict[str, Any],
) -> None:
    for key, value in expected.items():
        actual = mapping.get(key)
        if actual != value:
            errors.append(f"{rel_path}: {context} expected {key}={value!r}, found {actual!r}")


def validate_component(
    errors: list[str],
    rel_path: str,
    context: str,
    labels: dict[str, Any],
    allowed_components: list[str],
) -> None:
    component = labels.get("component")
    if not isinstance(component, str) or not component:
        errors.append(f"{rel_path}: {context} missing component label")
        return
    if component not in allowed_components:
        errors.append(
            f"{rel_path}: {context} component {component!r} is not allowed; "
            f"expected one of {', '.join(allowed_components)}"
        )


def collect_prometheus_rules(document: dict[str, Any], rel_path: str) -> list[tuple[str, dict[str, Any]]]:
    groups = document.get("groups")
    if not isinstance(groups, list):
        raise SystemExit(f"{rel_path}: expected top-level groups list")
    collected: list[tuple[str, dict[str, Any]]] = []
    for group_index, group in enumerate(groups):
        rules = group.get("rules")
        if not isinstance(rules, list):
            raise SystemExit(f"{rel_path}: groups[{group_index}].rules must be a list")
        for rule_index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                raise SystemExit(f"{rel_path}: groups[{group_index}].rules[{rule_index}] must be a mapping")
            rule_name = str(rule.get("record") or rule.get("alert") or f"rule-{rule_index}")
            collected.append((rule_name, rule))
    return collected


def collect_embedded_prometheus_rules(document: dict[str, Any], rel_path: str) -> list[tuple[str, dict[str, Any]]]:
    values_text = (
        document.get("spec", {})
        .get("source", {})
        .get("helm", {})
        .get("values")
    )
    if not isinstance(values_text, str) or not values_text.strip():
        raise SystemExit(f"{rel_path}: spec.source.helm.values must be a YAML string")
    try:
        values = yaml.safe_load(values_text) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f"{rel_path}: invalid embedded helm values YAML: {exc}") from exc
    groups = (
        values.get("additionalPrometheusRulesMap", {})
        .get("platform-baseline", {})
        .get("groups")
    )
    if not isinstance(groups, list):
        raise SystemExit(
            f"{rel_path}: embedded values missing additionalPrometheusRulesMap.platform-baseline.groups"
        )
    collected: list[tuple[str, dict[str, Any]]] = []
    for group_index, group in enumerate(groups):
        rules = group.get("rules")
        if not isinstance(rules, list):
            raise SystemExit(
                f"{rel_path}: embedded group {group_index} rules must be a list"
            )
        for rule_index, rule in enumerate(rules):
            if not isinstance(rule, dict):
                raise SystemExit(
                    f"{rel_path}: embedded rule {group_index}/{rule_index} must be a mapping"
                )
            rule_name = str(rule.get("record") or rule.get("alert") or f"rule-{rule_index}")
            collected.append((rule_name, rule))
    return collected


def validate_prometheus_rule_collection(
    errors: list[str],
    rel_path: str,
    rules: list[tuple[str, dict[str, Any]]],
    expected_labels: dict[str, Any],
    allowed_components: list[str],
    expected_lane: str | None,
) -> None:
    for rule_name, rule in rules:
        labels = rule.get("labels")
        context = f"{rule_name} labels"
        if not isinstance(labels, dict):
            errors.append(f"{rel_path}: {context} missing")
            continue
        validate_expected_mapping(errors, rel_path, context, labels, expected_labels)
        validate_component(errors, rel_path, context, labels, allowed_components)
        if expected_lane is not None:
            actual_lane = labels.get("lane")
            if actual_lane != expected_lane:
                errors.append(
                    f"{rel_path}: {context} expected lane={expected_lane!r}, found {actual_lane!r}"
                )


def validate_dashboard_tags(
    errors: list[str],
    rel_path: str,
    dashboard: dict[str, Any],
    required_tags: list[str],
) -> None:
    tags = dashboard.get("tags")
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        errors.append(f"{rel_path}: dashboard tags must be a list of strings")
        return
    missing = [tag for tag in required_tags if tag not in tags]
    if missing:
        errors.append(f"{rel_path}: dashboard is missing required tags: {', '.join(missing)}")


def validate_rule(
    repo_root: Path,
    model: dict[str, Any],
    policy_root: Path,
    rule: dict[str, Any],
    errors: list[str],
) -> int:
    rule_id = rule.get("id")
    kind = rule.get("kind")
    patterns = rule.get("paths", [])
    if not isinstance(rule_id, str) or not rule_id:
        raise SystemExit("observability validation policy rule missing id")
    if not isinstance(kind, str) or not kind:
        raise SystemExit(f"{POLICY_PATH}: rule {rule_id!r} missing kind")
    if not isinstance(patterns, list) or not all(isinstance(pattern, str) for pattern in patterns):
        raise SystemExit(f"{POLICY_PATH}: rule {rule_id!r} paths must be a list of strings")

    files = iter_rule_files(repo_root, patterns)
    if not files:
        errors.append(f"{POLICY_PATH}: rule {rule_id!r} matched no files")
        return 0

    scanned = 0
    for path in files:
        rel_path = path.relative_to(repo_root).as_posix()
        scanned += 1
        if kind == "prometheus-rule-groups":
            expected_labels = rule.get("expected_labels", {})
            allowed_components = resolve_model_value(model, rule["allowed_components_from_model"])
            document = load_yaml_mapping(path)
            rules = collect_prometheus_rules(document, rel_path)
            validate_prometheus_rule_collection(
                errors,
                rel_path,
                rules,
                expected_labels,
                list(allowed_components),
                expected_lane=None,
            )
            continue

        if kind == "argo-embedded-prometheus-rules":
            expected_labels = rule.get("expected_labels", {})
            allowed_components = resolve_model_value(model, rule["allowed_components_from_model"])
            document = load_yaml_mapping(path)
            rules = collect_embedded_prometheus_rules(document, rel_path)
            expected_lane = None
            if rule.get("expect_lane_from_path"):
                expected_lane = infer_lane_from_path(path)
                if expected_lane is None:
                    errors.append(f"{rel_path}: could not infer lane from path")
                    continue
            validate_prometheus_rule_collection(
                errors,
                rel_path,
                rules,
                expected_labels,
                list(allowed_components),
                expected_lane=expected_lane,
            )
            continue

        if kind == "grafana-dashboard-json":
            dashboard = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(dashboard, dict):
                errors.append(f"{rel_path}: dashboard JSON must be an object")
                continue
            validate_dashboard_tags(errors, rel_path, dashboard, list(rule.get("required_tags", [])))
            continue

        if kind == "grafana-dashboard-configmap":
            document = load_yaml_mapping(path)
            data = document.get("data")
            if not isinstance(data, dict):
                errors.append(f"{rel_path}: ConfigMap data is required")
                continue
            data_key = rule.get("data_key")
            dashboard_raw = data.get(data_key)
            if not isinstance(dashboard_raw, str) or not dashboard_raw.strip():
                errors.append(f"{rel_path}: missing ConfigMap data key {data_key!r}")
                continue
            dashboard = json.loads(dashboard_raw)
            if not isinstance(dashboard, dict):
                errors.append(f"{rel_path}: embedded dashboard JSON must be an object")
                continue
            validate_dashboard_tags(errors, rel_path, dashboard, list(rule.get("required_tags", [])))
            continue

        if kind == "yaml-fields":
            document = load_yaml_mapping(path)
            expected_fields = rule.get("expected_fields", {})
            if not isinstance(expected_fields, dict):
                raise SystemExit(f"{POLICY_PATH}: rule {rule_id!r} expected_fields must be a mapping")
            validate_expected_mapping(errors, rel_path, "metadata", document, expected_fields)
            continue

        if kind == "product-overlay-catalog":
            document = load_yaml_mapping(path)
            product = document.get("product")
            overlay_type = document.get("overlay_type")
            owner_repo = document.get("owner_repo")
            allowed_products = resolve_model_value(model, rule["allowed_products_from_model"])
            if overlay_type != "product-overlay":
                errors.append(f"{rel_path}: overlay_type must be 'product-overlay', found {overlay_type!r}")
            if product not in allowed_products:
                errors.append(
                    f"{rel_path}: product {product!r} is not allowed; expected one of {', '.join(allowed_products)}"
                )
            expected_owner_repo = rule.get("expected_owner_repo")
            if owner_repo != expected_owner_repo:
                errors.append(f"{rel_path}: owner_repo must be {expected_owner_repo!r}, found {owner_repo!r}")
            model_ref = document.get("model_ref")
            if not isinstance(model_ref, str) or not model_ref:
                errors.append(f"{rel_path}: model_ref is required")
            else:
                resolved_model_ref = resolve_relative_path(path.parent, model_ref)
                if resolved_model_ref != resolve_relative_path(policy_root, "model.yaml"):
                    errors.append(
                        f"{rel_path}: model_ref must resolve to docs/components/observability/model.yaml"
                    )
            shared_roots = [str(root) for root in rule.get("shared_product_asset_roots", [])]
            if not shared_roots:
                shared_roots = []
            for asset in document.get("owned_assets", []) or []:
                if not isinstance(asset, dict):
                    errors.append(f"{rel_path}: owned_assets entries must be mappings")
                    continue
                raw_asset_path = asset.get("path")
                if not isinstance(raw_asset_path, str) or not raw_asset_path:
                    errors.append(f"{rel_path}: owned_assets path is required")
                    continue
                resolved_asset = (repo_root / raw_asset_path).resolve()
                if not resolved_asset.exists():
                    errors.append(f"{rel_path}: owned asset {raw_asset_path!r} does not exist")
                for shared_root in rule.get("shared_roots", []):
                    if raw_asset_path.startswith(f"{shared_root}/") or raw_asset_path == shared_root:
                        errors.append(
                            f"{rel_path}: owned asset {raw_asset_path!r} must not live under shared root {shared_root!r}"
                        )
            continue

        raise SystemExit(f"{POLICY_PATH}: unsupported rule kind {kind!r}")

    return scanned


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the platform observability baseline and overlay taxonomy."
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="platform-engineering repository root",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    policy_path = repo_root / POLICY_PATH
    if not policy_path.exists():
        raise SystemExit(f"{policy_path}: missing observability validation policy")
    policy = load_yaml_mapping(policy_path)

    if policy.get("schema_version") != 1:
        raise SystemExit(f"{policy_path}: schema_version must be 1")

    model_ref = policy.get("model_ref")
    if not isinstance(model_ref, str) or not model_ref:
        raise SystemExit(f"{policy_path}: model_ref is required")

    policy_root = policy_path.parent
    model_path = resolve_relative_path(policy_root, model_ref)
    if not model_path.exists():
        raise SystemExit(f"{policy_path}: model_ref {model_ref!r} does not resolve to an existing file")
    model = load_yaml_mapping(model_path)

    rules = policy.get("rules", [])
    if not isinstance(rules, list) or not rules:
        raise SystemExit(f"{policy_path}: rules must be a non-empty list")

    errors: list[str] = []
    scanned_files = 0

    for rule in rules:
        if not isinstance(rule, dict):
            raise SystemExit(f"{policy_path}: rules must contain mappings")
        if rule.get("kind") == "product-overlay-catalog":
            rule = dict(rule)
            rule["shared_roots"] = list(policy.get("shared_product_asset_roots", []))
        scanned_files += validate_rule(repo_root, model, policy_root, rule, errors)

    if errors:
        raise SystemExit("\n".join(errors))

    print(
        "platform-engineering observability taxonomy valid: "
        f"scanned_files={scanned_files} "
        f"rules={len(rules)} "
        f"model={model.get('model_name')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
