#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from gateway_environment import dump_yaml, write_yaml
from prod_lifecycle import (
    load_prod_lifecycle,
    now_utc,
    prod_state_requires_incident_ref,
    prod_lifecycle_path,
    prod_verification_inactive_note,
    prod_verification_status_for_state,
    prod_verification_path,
    sync_prod_lifecycle,
)
from prod_verification import reset_prod_verification


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "state",
        choices=("live", "traffic-stopped", "suspended", "quarantined", "status"),
        help="Desired OpenClaw prod lifecycle state",
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[3],
        type=Path,
        help="platform-engineering repository root",
    )
    parser.add_argument("--changed-by", default="", help="operator or actor responsible for the lifecycle change")
    parser.add_argument("--reason", default="", help="short reason for the lifecycle change")
    parser.add_argument("--incident-ref", default="", help="optional incident or ticket reference")
    parser.add_argument("--note", default="", help="optional human note recorded with the lifecycle change")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = args.repo_root
    lifecycle_path = prod_lifecycle_path(repo_root)
    current = load_prod_lifecycle(repo_root)

    if args.state == "status":
        print(
            f"state={current.get('state') or 'unset'} "
            f"changed_by={current.get('changedBy') or 'none'} "
            f"changed_at={current.get('changedAt') or 'none'} "
            f"reason={current.get('reason') or 'none'} "
            f"incident_ref={current.get('incidentRef') or 'none'} "
            f"note={current.get('note') or 'none'}"
        )
        return 0

    if not args.changed_by.strip():
        raise SystemExit("--changed-by is required for prod lifecycle changes")
    if not args.reason.strip():
        raise SystemExit("--reason is required for prod lifecycle changes")
    if prod_state_requires_incident_ref(args.state) and not args.incident_ref.strip():
        raise SystemExit(f"--incident-ref is required when prod lifecycle state is {args.state!r}")

    note = args.note.strip()
    if not note:
        if args.state == "suspended":
            note = "Prod OpenClaw suspended through the governed emergency lifecycle control."
        elif args.state == "traffic-stopped":
            note = (
                "Prod OpenClaw gateway traffic is intentionally stopped through the "
                "governed lifecycle control while support surfaces remain available."
            )
        elif args.state == "quarantined":
            note = (
                "Prod OpenClaw quarantined through the governed incident lifecycle control; "
                "resume requires explicit incident follow-up and fresh prod verification."
            )
        else:
            note = "Prod OpenClaw returned to the live governed lifecycle state."

    previous_state = current.get("state") or "live"
    requested_changed_by = args.changed_by.strip()
    requested_reason = args.reason.strip()
    requested_incident_ref = args.incident_ref.strip() or None
    desired = dict(current)
    desired["state"] = args.state
    metadata_changed = (
        previous_state != args.state
        or (current.get("changedBy") or "") != requested_changed_by
        or (current.get("reason") or "") != requested_reason
        or current.get("incidentRef") != requested_incident_ref
        or (current.get("note") or "") != note
    )
    desired["changedAt"] = now_utc() if metadata_changed else current.get("changedAt")
    desired["changedBy"] = requested_changed_by
    desired["reason"] = requested_reason
    desired["incidentRef"] = requested_incident_ref
    desired["note"] = note

    changed_paths: list[Path] = []
    previous_text = lifecycle_path.read_text(encoding="utf-8") if lifecycle_path.exists() else ""

    rendered = dump_yaml(desired)
    if previous_text != rendered:
        write_yaml(lifecycle_path, desired)
        changed_paths.append(lifecycle_path)

    _, lifecycle_changed = sync_prod_lifecycle(repo_root)
    changed_paths.extend(path for path in lifecycle_changed if path not in changed_paths)

    verification = None
    if previous_state != args.state:
        verification_status = prod_verification_status_for_state(args.state)
        verification_note = (
            "Prod lifecycle returned to live; reconcile the current prod contract and record fresh prod smoke/UAT before treating prod as complete."
            if args.state == "live"
            else prod_verification_inactive_note(args.state)
        )
        verification_path = prod_verification_path(repo_root)
        previous_verification = verification_path.read_text(encoding="utf-8") if verification_path.exists() else ""
        verification = reset_prod_verification(repo_root, status=verification_status, note=verification_note)
        current_verification = verification_path.read_text(encoding="utf-8")
        if previous_verification != current_verification:
            changed_paths.append(verification_path)

    if not changed_paths:
        print(
            f"Prod OpenClaw already {args.state}"
        )
        return 0

    changed_labels = ", ".join(str(path.relative_to(repo_root)) for path in changed_paths)
    verification_status = verification["status"] if verification is not None else "unchanged"
    print(
        f"Prod OpenClaw state={args.state} "
        f"prod_verification={verification_status} "
        f"changed={changed_labels}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
