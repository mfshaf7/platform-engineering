#!/usr/bin/env python3
import argparse
from pathlib import Path
import re
from typing import Any

import yaml


POLICY_PATH = Path("environments/shared/single-host-scaling-policy.yaml")
TARGET_KEYS = {"replicas", "replicaCount", "minReplicas"}
YAML_GLOBS = (
    "environments/**/*.yml",
    "environments/**/*.yaml",
    "products/**/*.yml",
    "products/**/*.yaml",
    "charts/**/*.yml",
    "charts/**/*.yaml",
)
LITERAL_SCALE_RE = re.compile(r"^\s*(replicas|replicaCount|minReplicas):\s*([2-9]\d*)\s*$")
EMBEDDED_HELM_VALUES_SUFFIX = ".helm.values"


def load_policy(policy_path: Path) -> dict[str, Any]:
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    if not isinstance(policy, dict):
        raise SystemExit(f"{policy_path}: policy file must be a YAML mapping")

    default_max = policy.get("default_max_replicas")
    if not isinstance(default_max, int) or default_max < 1:
        raise SystemExit(f"{policy_path}: default_max_replicas must be an integer >= 1")

    exemptions = policy.get("exemptions", [])
    if not isinstance(exemptions, list):
        raise SystemExit(f"{policy_path}: exemptions must be a list")

    for index, exemption in enumerate(exemptions):
        if not isinstance(exemption, dict):
            raise SystemExit(f"{policy_path}: exemption #{index + 1} must be a mapping")
        if not isinstance(exemption.get("file"), str) or not exemption["file"]:
            raise SystemExit(f"{policy_path}: exemption #{index + 1} is missing file")
        if not isinstance(exemption.get("yaml_path"), str) or not exemption["yaml_path"]:
            raise SystemExit(f"{policy_path}: exemption #{index + 1} is missing yaml_path")
        max_replicas = exemption.get("max_replicas")
        if not isinstance(max_replicas, int) or max_replicas < default_max:
            raise SystemExit(
                f"{policy_path}: exemption #{index + 1} max_replicas must be an integer >= default_max_replicas"
            )
        if not isinstance(exemption.get("reason"), str) or not exemption["reason"].strip():
            raise SystemExit(f"{policy_path}: exemption #{index + 1} is missing reason")

    return policy


def parse_replica_value(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def is_exempt(policy: dict[str, Any], rel_path: str, yaml_path: str, value: int) -> bool:
    for exemption in policy.get("exemptions", []):
        if exemption["file"] != rel_path:
            continue
        if exemption["yaml_path"] != yaml_path:
            continue
        if value <= exemption["max_replicas"]:
            return True
    return False


def parse_embedded_yaml(value: Any) -> Any | None:
    if not isinstance(value, str):
        return None
    try:
        documents = [document for document in yaml.safe_load_all(value) if document is not None]
    except yaml.YAMLError:
        return None
    if not documents:
        return None
    if len(documents) == 1 and isinstance(documents[0], (dict, list)):
        return documents[0]
    if all(isinstance(document, (dict, list)) for document in documents):
        return documents
    return None


def walk_yaml(
    errors: list[str],
    policy: dict[str, Any],
    rel_path: str,
    node: Any,
    node_path: str = "",
) -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            key_path = f"{node_path}.{key}" if node_path else str(key)
            if key in TARGET_KEYS:
                replica_value = parse_replica_value(value)
                if replica_value is not None and replica_value > policy["default_max_replicas"]:
                    if not is_exempt(policy, rel_path, key_path, replica_value):
                        errors.append(
                            f"{rel_path}: {key_path}={replica_value} exceeds default_max_replicas="
                            f"{policy['default_max_replicas']}"
                        )
            if key_path.endswith(EMBEDDED_HELM_VALUES_SUFFIX):
                embedded_yaml = parse_embedded_yaml(value)
                if embedded_yaml is not None:
                    walk_yaml(errors, policy, rel_path, embedded_yaml, key_path)
                    continue
            walk_yaml(errors, policy, rel_path, value, key_path)
        return

    if isinstance(node, list):
        for index, item in enumerate(node):
            child_path = f"{node_path}[{index}]" if node_path else f"[{index}]"
            walk_yaml(errors, policy, rel_path, item, child_path)


def validate_literal_template_scaling(errors: list[str], rel_path: str, text: str) -> None:
    for line_number, line in enumerate(text.splitlines(), start=1):
        match = LITERAL_SCALE_RE.match(line)
        if not match:
            continue
        key = match.group(1)
        value = int(match.group(2))
        errors.append(
            f"{rel_path}:{line_number}: hardcoded {key}={value} exceeds the single-host scaling default; "
            "use a values contract at 1 or add an explicit policy exemption"
        )


def iter_target_files(repo_root: Path) -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for pattern in YAML_GLOBS:
        for path in sorted(repo_root.glob(pattern)):
            if not path.is_file():
                continue
            if path in seen:
                continue
            seen.add(path)
            files.append(path)
    return files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that platform-managed runtime scaling stays single-instance by default."
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
        raise SystemExit(f"{policy_path}: missing single-host scaling policy file")

    policy = load_policy(policy_path)
    errors: list[str] = []
    scanned_files = 0

    for path in iter_target_files(repo_root):
        rel_path = path.relative_to(repo_root).as_posix()
        text = path.read_text(encoding="utf-8")
        scanned_files += 1

        try:
            documents = list(yaml.safe_load_all(text))
        except yaml.YAMLError:
            if "templates" in path.parts:
                validate_literal_template_scaling(errors, rel_path, text)
                continue
            raise SystemExit(f"{rel_path}: invalid YAML")

        for document in documents:
            if document is None:
                continue
            walk_yaml(errors, policy, rel_path, document)

    if errors:
        raise SystemExit("\n".join(errors))

    print(
        "platform-engineering single-host scaling valid: "
        f"scanned_files={scanned_files} "
        f"default_max_replicas={policy['default_max_replicas']} "
        f"exemptions={len(policy.get('exemptions', []))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
