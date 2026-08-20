#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


PROJECTION_RELATIVE_PATH = Path("products/openproject/delivery-art-blocker-workflow.json")
SOURCE_LOCK_RELATIVE_PATH = Path(
    "products/openproject/delivery-art-blocker-workflow-source-lock.json"
)


def read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def validate_projection(
    repo_root: Path, oos_repo_root: Path | None = None
) -> list[str]:
    projection_path = repo_root / PROJECTION_RELATIVE_PATH
    source_lock_path = repo_root / SOURCE_LOCK_RELATIVE_PATH
    errors: list[str] = []
    for path in (projection_path, source_lock_path):
        if not path.exists():
            errors.append(f"{path}: blocker-workflow projection artifact is missing")
    if errors:
        return errors

    try:
        projection = read_json(projection_path)
        source_lock = read_json(source_lock_path)
    except json.JSONDecodeError as exc:
        return [f"OpenProject blocker-workflow projection JSON is invalid: {exc}"]

    if source_lock.get("schema_version") != 1:
        errors.append(f"{source_lock_path}: schema_version must be 1")
    if source_lock.get("projection_id") != "platform-openproject-delivery-art-blocker-workflow":
        errors.append(f"{source_lock_path}: projection_id is invalid")

    required_vocabulary = source_lock.get("required_action_vocabulary")
    if not isinstance(required_vocabulary, dict):
        errors.append(f"{source_lock_path}: required_action_vocabulary must be an object")
        return errors
    for field in ("allowed_actions", "default_action", "recommendation_action_aliases"):
        if projection.get(field) != required_vocabulary.get(field):
            errors.append(
                f"{projection_path}: {field} does not match the locked OOS action vocabulary"
            )

    source = source_lock.get("source")
    projected = source_lock.get("projection")
    if not isinstance(source, dict) or not isinstance(projected, dict):
        errors.append(f"{source_lock_path}: source and projection must be objects")
        return errors
    if source.get("owner_repo") != "operator-orchestration-service":
        errors.append(f"{source_lock_path}: OOS must remain blocker-workflow source authority")
    if projected.get("owner_repo") != "platform-engineering":
        errors.append(f"{source_lock_path}: Platform must own only the local projection")
    if projected.get("path") != PROJECTION_RELATIVE_PATH.as_posix():
        errors.append(f"{source_lock_path}: projection path is invalid")

    projection_content = projection_path.read_bytes()
    projection_digest = sha256_bytes(projection_content)
    if projected.get("sha256") != projection_digest:
        errors.append(f"{projection_path}: content does not match its locked projection digest")
    if source.get("sha256") != projection_digest:
        errors.append(f"{projection_path}: content does not match the locked OOS source digest")

    if oos_repo_root is None:
        return errors
    source_commit = str(source.get("git_commit", ""))
    source_path = str(source.get("path", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        errors.append(f"{source_lock_path}: source.git_commit must be a full Git commit")
        return errors
    completed = subprocess.run(
        ["git", "-C", str(oos_repo_root), "show", f"{source_commit}:{source_path}"],
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        errors.append(
            f"{source_lock_path}: unable to resolve locked OOS source {source_commit}:{source_path}"
        )
        return errors
    if sha256_bytes(completed.stdout) != source.get("sha256"):
        errors.append(f"{source_lock_path}: locked OOS source content digest is stale")
    if completed.stdout != projection_content:
        errors.append(f"{projection_path}: projection differs from the locked OOS source content")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Platform's blocker-workflow projection against its locked OOS source."
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[3],
        type=Path,
        help="platform-engineering repository root",
    )
    parser.add_argument(
        "--oos-repo-root",
        type=Path,
        help="optional OOS checkout for exact source-commit parity proof",
    )
    args = parser.parse_args()
    errors = validate_projection(
        args.repo_root.resolve(),
        args.oos_repo_root.resolve() if args.oos_repo_root else None,
    )
    if errors:
        raise SystemExit("\n".join(errors))
    print("OpenProject blocker-workflow projection valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
