#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml

TOKEN_RE = re.compile(r"__[A-Z0-9_]+__")
DNS_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def image_ref(entry: dict) -> str:
    return f"{entry['repository']}:{entry['tag']}@{entry['digest']}"


def image_tag(entry: dict) -> str:
    return f"{entry['tag']}@{entry['digest']}"


def render_template(source: Path, destination: Path, tokens: dict[str, str]) -> None:
    text = source.read_text(encoding="utf-8")
    for key, value in tokens.items():
        text = text.replace(f"__{key}__", value)
    unresolved = sorted(set(TOKEN_RE.findall(text)))
    if unresolved:
        raise ValueError(f"{source}: unresolved template tokens: {', '.join(unresolved)}")
    list(yaml.safe_load_all(text))
    destination.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Temporal dev-integration runtime.")
    parser.add_argument("--profile-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--namespace", required=True)
    parser.add_argument("--oos-kubernetes-namespace", required=True)
    parser.add_argument("--wgcf-kubernetes-namespace", required=True)
    parser.add_argument("--operator-scope", required=True)
    parser.add_argument("--temporal-namespace", required=True)
    args = parser.parse_args()

    profile_root = args.profile_root.resolve()
    runtime_root = profile_root / "runtime"
    boundary = load_yaml(runtime_root / "boundary-contract.yaml")
    temporal_namespace_max_length = boundary["runtime"][
        "temporal_namespace_max_length"
    ]

    for label, value in (
        ("Kubernetes namespace", args.namespace),
        ("OOS Kubernetes namespace", args.oos_kubernetes_namespace),
        ("WGCF Kubernetes namespace", args.wgcf_kubernetes_namespace),
        ("operator scope", args.operator_scope),
        ("Temporal namespace", args.temporal_namespace),
    ):
        if DNS_LABEL_RE.fullmatch(value) is None:
            raise ValueError(f"{label} is not a DNS label")
    if len(args.temporal_namespace) > temporal_namespace_max_length:
        raise ValueError(
            "Temporal namespace exceeds the "
            f"{temporal_namespace_max_length}-character chart-generated "
            "container-name budget"
        )

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    lock = load_yaml(runtime_root / "artifact-lock.yaml")
    images = lock["images"]

    tokens = {
        "KUBERNETES_NAMESPACE": args.namespace,
        "OOS_KUBERNETES_NAMESPACE": args.oos_kubernetes_namespace,
        "WGCF_KUBERNETES_NAMESPACE": args.wgcf_kubernetes_namespace,
        "OPERATOR": args.operator_scope,
        "POSTGRESQL_IMAGE": image_ref(images["postgresql"]),
        "TEMPORAL_NAMESPACE": args.temporal_namespace,
        "TEMPORAL_SERVER_REPOSITORY": images["temporal_server"]["repository"],
        "TEMPORAL_SERVER_TAG": image_tag(images["temporal_server"]),
        "TEMPORAL_ADMIN_REPOSITORY": images["temporal_admin_tools"]["repository"],
        "TEMPORAL_ADMIN_TAG": image_tag(images["temporal_admin_tools"]),
        "TEMPORAL_UI_REPOSITORY": images["temporal_ui"]["repository"],
        "TEMPORAL_UI_TAG": image_tag(images["temporal_ui"]),
    }

    for name in ("postgresql.yaml", "network-boundaries.yaml", "temporal-values.yaml"):
        render_template(
            runtime_root / f"{name}.tpl",
            output_dir / name,
            tokens,
        )

    print(f"Rendered Temporal runtime into {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
