"""Verify owner-approved dependency bytes and bind outputs to their build."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re

from agent_source_instance import digest
from console_project_runtime_snapshot import bounded_file, directory_fd, matches_digest
from console_project_runtime_sandbox import IMAGE
from console_project_runtime_setup import NODE_SCRIPTS


class ProjectArtifactError(ValueError):
    """A recipe input or result does not match verified owner evidence."""


def copy_verified_dependencies(cache_root: Path, destination: Path, *, recipe: str, image: str,
                               lock_digest: str, approved: dict, max_bytes: int) -> dict:
    """Copy a digest-approved offline npm cache into staging, outside the workload."""
    if (recipe not in NODE_SCRIPTS or not isinstance(image, str) or not IMAGE.fullmatch(image)
            or not matches_digest(lock_digest) or type(max_bytes) is not int or max_bytes < 1):
        raise ProjectArtifactError("A reviewed Node recipe, pinned image and exact package lock are required.")
    identity = digest({"recipe": recipe, "image": image, "lock_digest": lock_digest})
    if (not isinstance(approved, dict) or approved.keys() != {"identity", "digest", "bytes"}
            or approved["identity"] != identity or not matches_digest(approved["digest"])
            or type(approved["bytes"]) is not int or not 0 < approved["bytes"] <= max_bytes):
        raise ProjectArtifactError("No compatible dependencies have been approved for this lockfile and build image.")
    created = False
    try:
        with directory_fd(cache_root) as directory:
            with bounded_file(directory, approved["digest"][7:], approved["bytes"]) as (source, size):
                if size != approved["bytes"]:
                    raise ProjectArtifactError("The cached dependencies differ from the approved archive length.")
                verified = hashlib.sha256()
                remaining = size
                with destination.open("xb") as target:
                    created = True
                    while remaining:
                        chunk = source.read(min(remaining, 128 * 1024))
                        if not chunk:
                            raise ProjectArtifactError("The approved cache was incomplete during transfer.")
                        verified.update(chunk)
                        remaining -= len(chunk)
                        target.write(chunk)
                    if source.read(1) or f"sha256:{verified.hexdigest()}" != approved["digest"]:
                        raise ProjectArtifactError("The cached dependency content did not match its approved digest.")
        return dict(approved)
    except (OSError, ValueError) as error:
        if created:
            destination.unlink(missing_ok=True)
        if isinstance(error, ProjectArtifactError):
            raise
        raise ProjectArtifactError("The approved dependencies could not be verified and copied.") from None


def qualify_build(binding: dict, *, expected_uid: str, image: str, output_claim: str,
                  observed: dict, output_digest: str) -> dict:
    """Require an actual successful build from the exact source and sandbox."""
    expected = {"scope_digest": binding["scope_digest"], "operation_id": binding["operation_id"],
                "manifest_digest": binding["snapshot"]["manifest_digest"],
                "configuration_revision": binding["setup"]["configuration_revision"],
                "image": image, "uid": expected_uid, "output_claim": output_claim}
    if (not isinstance(observed, dict) or observed.get("phase") != "Succeeded"
            or any(observed.get(key) != value for key, value in expected.items())
            or not isinstance(expected_uid, str) or not expected_uid
            or not isinstance(image, str) or not IMAGE.fullmatch(image)
            or not isinstance(output_claim, str) or not re.fullmatch(r"build-[a-f0-9]{32}", output_claim)
            or not matches_digest(output_digest)):
        raise ProjectArtifactError("The current build did not produce an artifact for this exact operation, source and setup.")
    return {**expected, "artifact_digest": output_digest}
