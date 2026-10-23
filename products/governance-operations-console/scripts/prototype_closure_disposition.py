"""Observe managed incubation absence for an exact committed graduation.

Inputs select an existing event, never a host path, command or disposition.
The existing Platform provider authenticates OOS and records the existing proof.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import socket
import subprocess
import sys
from typing import Any

from jsonschema import Draft202012Validator
import yaml

import console_record_authority as authority


class DispositionError(ValueError):
    pass


def require(value: Any, message: str) -> None:
    if not value:
        raise DispositionError(message)


def document(root: Path, revision: str, path: str) -> str:
    size = authority.git(root, "cat-file", "-s", f"{revision}:{path}")
    require(size.isdigit() and int(size) <= 262144, "Canonical disposition source exceeds its bound.")
    return authority.git(root, "show", f"{revision}:{path}", preserve_output=True)


def absent(policy: dict[str, Any], lookup: Any) -> dict[str, str]:
    require(isinstance(lookup, dict) and set(lookup) == {
        "prototype_id", "merged_source_revision", "source_event_ref",
    }, "Disposition lookup must bind exactly one committed graduation.")
    slug, merged, event_id = (lookup[key] for key in
        ("prototype_id", "merged_source_revision", "source_event_ref"))
    require(isinstance(slug, str) and len(slug) <= 128 and re.fullmatch(r"[a-z0-9][a-z0-9._-]*", slug),
        "Prototype identity is invalid.")
    require(isinstance(merged, str) and re.fullmatch(r"[0-9a-f]{40}", merged),
        "Merged Studio revision is invalid.")
    require(isinstance(event_id, str), "Graduation event identity is invalid.")
    match = re.fullmatch(rf"prototype-closure:{re.escape(slug)}:([0-9]{{4,}})", event_id)
    require(match is not None and len(event_id) <= 256, "Graduation event identity is invalid.")
    require(policy.get("record_authority", {}).get("enabled") is True,
        "Current canonical record authority is required.")
    reviewed = policy["security"]["reviewed_revisions"]["workspace-prototype-studio"]
    state_root = Path(policy["runtime_state_root"])
    cache = state_root / "record-authority"
    root = cache / "workspace-prototype-studio"
    before = authority.snapshot_status(cache, "workspace-prototype-studio", reviewed)
    revision = before["record_revision"]
    authority.git(root, "merge-base", "--is-ancestor", merged, revision)
    event_path = f"records/prototype-closure/{slug}/history/{match[1]}.json"
    event_source = document(root, merged, event_path)
    require(document(root, revision, event_path) == event_source,
        "The current canonical graduation event changed.")
    event = json.loads(event_source)
    schema = json.loads(document(root, reviewed,
        "contracts/prototype-closure/prototype-closure-history-event.schema.json"))
    Draft202012Validator(schema).validate(event)
    require(event["event_id"] == event_id and event["prototype_id"] == slug and
        event["event_type"] == "source-graduated" and event["observed_lifecycle"] == "graduated" and
        event["observed_source_custody"] in {"dedicated-owner-repo", "shared-owner-repo"},
        "The exact event does not prove source graduation.")
    require(isinstance(event["expected_source_revision"], str) and
        re.fullmatch(r"[0-9a-f]{40}", event["expected_source_revision"]) and
        event["expected_source_revision"] != merged, "Graduation source did not advance safely.")
    authority.git(root, "merge-base", "--is-ancestor", event["expected_source_revision"], merged)
    # An arbitrary later descendant is not the event's actual source merge.
    parents = authority.git(root, "rev-list", "--parents", "-n", "1", merged).split()[1:]
    require(bool(parents), "Graduation must follow its accepted source.")
    canonical = authority.git(root, "rev-list", "--first-parent", f"{parents[0]}..{revision}").splitlines()
    require(merged in canonical, "The supplied revision is not the canonical main merge.")
    entries = authority.git(root, "ls-tree", parents[0], "--", event_path)
    require(not entries, "The supplied revision did not introduce this graduation event.")
    registry = yaml.safe_load(document(root, revision, "prototypes.yaml"))
    items = [item for item in registry.get("prototypes", []) if item.get("id") == slug]
    ref = f"record://prototype-closure/{slug}/history/{event_id}"
    require(len(items) == 1 and items[0].get("lifecycle") == "graduated" and
        items[0].get("source_custody") == event["observed_source_custody"] and
        items[0].get("closure_event_ref") == ref and items[0].get("graduation_ref") == ref,
        "Current canonical source custody does not bind this graduation.")

    preview_root = state_root / "prototype-preview"
    require(not preview_root.is_symlink(), "Managed Preview state root is unsafe.")
    paths = list((root / "records/prototype-preview-profiles").glob("*.yaml"))
    require(len(paths) <= 256, "Managed Preview inventory exceeds its bound.")
    profiles = []
    for path in paths:
        require(path.is_file() and not path.is_symlink() and path.stat().st_size <= 131072,
            "Managed Preview profile is unsafe.")
        profile = yaml.safe_load(path.read_text())
        require(isinstance(profile, dict), "Managed Preview profile is invalid.")
        if profile.get("prototype_id") == f"prototype:{slug}":
            profiles.append((path, profile))
    require(len(profiles) <= 1, "Managed Preview ownership is ambiguous.")
    # An undeclared retained process must not be mistaken for no runtime.
    states = list(preview_root.glob("*/state.json"))
    require(len(states) <= 256, "Managed Preview state inventory exceeds its bound.")
    for path in states:
        require(path.is_file() and not path.is_symlink() and not path.parent.is_symlink() and
            path.stat().st_size <= 131072, "Managed Preview state is unsafe.")
        value = json.loads(path.read_text())
        require(isinstance(value, dict), "Managed Preview state is invalid.")
        require(value.get("prototype_id") != f"prototype:{slug}",
            "Managed Preview retains process state; inspect or stop it through its owner.")
    for path, profile in profiles:
        command = [sys.executable, str(root / "scripts/prototype_preview.py"),
            "--repo-root", str(root), "--state-root", str(preview_root),
            "status", "--profile", str(path)]
        result = subprocess.run(command, capture_output=True, timeout=10, check=True, text=True)
        require(len(result.stdout.encode()) <= 131072, "Native Preview status exceeds its bound.")
        observed = json.loads(result.stdout)
        require(observed.get("prototype_id") == f"prototype:{slug}" and
            observed.get("source_revision") == revision and observed.get("runtime_state") == "stopped" and
            observed.get("endpoint") is None and observed.get("instance_id") is None,
            "Native Preview does not prove stopped incubation.")
        runtime = profile.get("runtime", {})
        require(runtime.get("bind_host") == "127.0.0.1" and
            type(runtime.get("port")) is int and 1024 <= runtime["port"] <= 65535,
            "Native Preview endpoint is not admitted loopback.")
        # Stopped metadata alone cannot hide an orphan or unrelated listener.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            try:
                probe.bind(("127.0.0.1", runtime["port"]))
            except OSError:
                raise DispositionError("The managed Preview endpoint is occupied.") from None
    after = authority.snapshot_status(cache, "workspace-prototype-studio", reviewed)
    require(after["record_revision"] == revision, "Canonical Studio source changed during disposition.")
    return {"prototype_id": slug, "merged_source_revision": merged, "disposition": "absent"}
