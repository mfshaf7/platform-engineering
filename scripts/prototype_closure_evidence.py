#!/usr/bin/env python3
"""Record bounded Platform-owned Prototype Closure runtime evidence."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from typing import Any


DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
PROTOTYPE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
REF = re.compile(r"^[a-z][a-z0-9+.-]*://[A-Za-z0-9][A-Za-z0-9._~:/%+=-]*$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
OWNER_FIELDS = {
    "runtime_disposition_plan_ref",
    "runtime_disposition_proof_ref",
}


class EvidenceError(ValueError):
    pass


def canonical_digest(value: dict[str, Any]) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise EvidenceError("evidence file must not be a symlink")
    try:
        info = path.stat()
    except OSError:
        raise EvidenceError("evidence file is unavailable") from None
    if (
        not stat.S_ISREG(info.st_mode)
        or stat.S_IMODE(info.st_mode) & 0o077
        or info.st_size > 262144
    ):
        raise EvidenceError("evidence file is not a bounded 0600 regular file")
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        raise EvidenceError("evidence file is invalid") from None
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "records"}
        or value["schema_version"] != 1
        or not isinstance(value["records"], list)
        or len(value["records"]) > 256
    ):
        raise EvidenceError("evidence file has an unsupported shape")
    return value


def _bound_record(content: dict[str, Any]) -> dict[str, Any]:
    digest = canonical_digest(content)
    return {
        **content,
        "ref": f"platform://prototype-closure/evidence/{digest[7:]}",
        "digest": digest,
    }


def _write(path: Path, value: dict[str, Any]) -> None:
    source = json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    if len(source.encode()) > 262144:
        raise EvidenceError("evidence file would exceed its size limit")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".prototype-closure-evidence-",
        dir=path.parent,
        text=True,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            stream.write(source)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def record(path: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_descriptor = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        os.fchmod(lock_descriptor, 0o600)
        fcntl.flock(lock_descriptor, fcntl.LOCK_EX)
        value = _load(path)
        selector = (
            candidate["field"],
            candidate["prototype_id"],
            candidate.get("source_revision"),
            candidate.get("merged_source_revision"),
        )
        retained = [
            entry
            for entry in value["records"]
            if (
                entry.get("field"),
                entry.get("prototype_id"),
                entry.get("source_revision"),
                entry.get("merged_source_revision"),
            )
            != selector
        ]
        retained.append(candidate)
        if len(retained) > 256:
            raise EvidenceError("evidence record limit reached")
        _write(path, {"schema_version": 1, "records": retained})
        return candidate
    finally:
        os.close(lock_descriptor)


def owner_evidence(args: argparse.Namespace) -> dict[str, Any]:
    if args.field not in OWNER_FIELDS:
        raise EvidenceError("owner evidence field is unsupported")
    if not PROTOTYPE_ID.fullmatch(args.prototype_id):
        raise EvidenceError("prototype id is invalid")
    if not REF.fullmatch(args.subject_ref) or not REVISION.fullmatch(args.source_revision):
        raise EvidenceError("owner evidence binding is invalid")
    if args.source_packet_ref is not None and not REF.fullmatch(args.source_packet_ref):
        raise EvidenceError("source packet reference is invalid")
    return _bound_record(
        {
            "field": args.field,
            "owner_ref": "platform-engineering",
            "state": "accepted",
            "subject_ref": args.subject_ref,
            "source_revision": args.source_revision,
            "source_packet_ref": args.source_packet_ref,
            "prototype_id": args.prototype_id,
        }
    )


def post_merge_disposition(args: argparse.Namespace) -> dict[str, Any]:
    if not PROTOTYPE_ID.fullmatch(args.prototype_id):
        raise EvidenceError("prototype id is invalid")
    if not REVISION.fullmatch(args.merged_source_revision):
        raise EvidenceError("merged source revision is invalid")
    return _bound_record(
        {
            "field": "post_merge_runtime_disposition",
            "owner_ref": "platform-engineering",
            "state": "accepted",
            "disposition": args.disposition,
            "prototype_id": args.prototype_id,
            "merged_source_revision": args.merged_source_revision,
        }
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    root.add_argument("--evidence-file", type=Path, required=True)
    commands = root.add_subparsers(dest="command", required=True)
    owner = commands.add_parser("record-owner-evidence")
    owner.add_argument("--field", choices=sorted(OWNER_FIELDS), required=True)
    owner.add_argument("--prototype-id", required=True)
    owner.add_argument("--subject-ref", required=True)
    owner.add_argument("--source-revision", required=True)
    owner.add_argument("--source-packet-ref")
    owner.set_defaults(builder=owner_evidence)
    disposition = commands.add_parser("record-post-merge-disposition")
    disposition.add_argument("--prototype-id", required=True)
    disposition.add_argument("--merged-source-revision", required=True)
    disposition.add_argument("--disposition", choices=["revoked", "absent"], required=True)
    disposition.set_defaults(builder=post_merge_disposition)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        result = record(args.evidence_file, args.builder(args))
    except (EvidenceError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, sort_keys=True))
        return 1
    print(json.dumps({"ok": True, "record": result}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
