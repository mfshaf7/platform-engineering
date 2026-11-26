"""Verify OOS's exact saved source before staging it in a project volume."""

from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import tempfile
import unicodedata

from agent_source_instance import digest, invalid_constant, strict_object
from console_project_runtime_setup import COMMIT, RECIPES, ProjectSetupError, scope_key, source_path


SHA256 = re.compile(r"sha256:[0-9a-f]{64}")
FILE_MODES = {"100644": 0o644, "100755": 0o755}
MANIFEST_FIELDS = {"schema_version", "scope", "source", "setup", "command_id", "total_bytes", "files"}
FILE_FIELDS = {"path", "type", "mode", "size", "blob_digest"}


class ProjectSnapshotError(ValueError):
    """Isolation staging could not prove the exact acknowledged source."""


def matches_digest(value) -> bool:
    return isinstance(value, str) and SHA256.fullmatch(value) is not None


@contextmanager
def directory_fd(name: str | Path, *, parent: int | None = None):
    descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    try:
        yield descriptor
    finally:
        os.close(descriptor)


@contextmanager
def bounded_file(directory: int, name: str, maximum: int):
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or not 0 <= info.st_size <= maximum:
            raise ProjectSnapshotError("The private source snapshot contains an unsupported or oversized file.")
        yield stream, info.st_size


def contains(root: str, name: str) -> bool:
    return root == "." or name == root or name.startswith(f"{root}/")


def portable_name(value: str) -> str:
    return unicodedata.normalize("NFC", unicodedata.normalize("NFC", value).upper())


def validate_binding(binding: dict) -> str:
    scope = binding["scope"]
    scope_identity = f"sha256:{scope_key(scope)}"
    source, setup, reference = (binding[key] for key in ("source", "setup", "snapshot"))
    if not all(isinstance(value, dict) for value in (source, setup, reference)):
        raise ProjectSnapshotError("Saved source, setup, and snapshot references are required.")
    committed_keys = {"kind", "base_commit", "session_id"}
    saved_keys = committed_keys | {"revision", "change_set_digest"}
    if (not isinstance(binding["command_id"], str) or not binding["command_id"]
            or binding["scope_digest"] != scope_identity
            or not isinstance(source.get("session_id"), str) or not source["session_id"]
            or not isinstance(source.get("base_commit"), str) or not COMMIT.fullmatch(source["base_commit"])
            or (source.get("kind") == "committed" and source.keys() != committed_keys)
            or (source.get("kind") == "saved-draft" and (source.keys() != saved_keys
                or not isinstance(source["revision"], str) or not source["revision"]
                or not matches_digest(source["change_set_digest"])))
            or source.get("kind") not in ("committed", "saved-draft")
            or setup.keys() != {"recipe_id", "configuration_revision"}
            or not isinstance(setup["recipe_id"], str) or setup["recipe_id"] not in RECIPES
            or not isinstance(setup["configuration_revision"], str) or not setup["configuration_revision"]
            or reference.keys() != {"snapshot_id", "manifest_digest"}
            or not matches_digest(reference["manifest_digest"])):
        raise ProjectSnapshotError("The saved source does not have a complete authorized binding.")
    content_id = reference["manifest_digest"][7:]
    if reference["snapshot_id"] != f"project-source:{content_id}":
        raise ProjectSnapshotError("The source snapshot reference and manifest identity differ.")
    return content_id


def read_manifest(directory: int, binding: dict, *, max_manifest_bytes: int,
                  max_files: int, max_bytes: int) -> list[dict]:
    with bounded_file(directory, "manifest.json", max_manifest_bytes) as (stream, size):
        raw = stream.read(max_manifest_bytes + 1)
    if len(raw) != size:
        raise ProjectSnapshotError("The source manifest changed while it was being read.")
    manifest = json.loads(raw.decode(), object_pairs_hook=strict_object, parse_constant=invalid_constant)
    if (not isinstance(manifest, dict) or manifest.keys() != MANIFEST_FIELDS
            or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1
            or any(manifest[key] != binding[key] for key in ("scope", "source", "setup", "command_id"))
            or digest(manifest) != binding["snapshot"]["manifest_digest"]
            or not isinstance(manifest["files"], list) or len(manifest["files"]) > max_files
            or type(manifest["total_bytes"]) is not int or not 0 <= manifest["total_bytes"] <= max_bytes):
        raise ProjectSnapshotError("The source manifest differs from the acknowledged command or exceeds its limits.")
    scope = manifest["scope"]
    previous = {}
    files = set()
    byte_count = 0
    for entry in manifest["files"]:
        if (not isinstance(entry, dict) or entry.keys() != FILE_FIELDS or entry["type"] != "file"
                or not isinstance(entry["mode"], str) or entry["mode"] not in FILE_MODES
                or type(entry["size"]) is not int or entry["size"] < 0 or not matches_digest(entry["blob_digest"])):
            raise ProjectSnapshotError("The source manifest contains invalid file metadata.")
        name = source_path(entry["path"])
        if name in files or not any(contains(root, name) for root in [scope["app_root"], *scope["dependency_paths"]]):
            raise ProjectSnapshotError("The source snapshot contains duplicate paths or paths outside the admitted source.")
        parts = name.split("/")
        for index in range(1, len(parts) + 1):
            component = "/".join(parts[:index])
            identity = portable_name(component)
            if previous.setdefault(identity, component) != component:
                raise ProjectSnapshotError("The source snapshot contains paths that collide in the project volume.")
        files.add(name)
        byte_count += entry["size"]
        if byte_count > max_bytes:
            raise ProjectSnapshotError("The source snapshot exceeds the recipe's byte limit.")
    if byte_count != manifest["total_bytes"]:
        raise ProjectSnapshotError("The source manifest's byte count does not match its files.")
    if any(parent in files for name in files for parent in _parent_names(name)):
        raise ProjectSnapshotError("A source path conflicts with a source directory.")
    if not all(any(contains(dependency, name) for name in files) for dependency in scope["dependency_paths"]):
        raise ProjectSnapshotError("An admitted workspace dependency is absent from the source snapshot.")
    return manifest["files"]


def _parent_names(name: str):
    while "/" in name:
        name, _ = name.rsplit("/", 1)
        yield name


def copy_blob(blob_directory: int, entry: dict, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    expected_size, identity = entry["size"], entry["blob_digest"]
    with bounded_file(blob_directory, identity[7:], expected_size) as (source, original_size):
        if original_size != expected_size:
            raise ProjectSnapshotError("A source blob differs from the file declared in the manifest.")
        observed = hashlib.sha256()
        remaining = expected_size
        with destination.open("xb") as target:
            while remaining:
                data = source.read(min(remaining, 128 * 1024))
                if not data:
                    raise ProjectSnapshotError("A source blob ended before its declared length.")
                remaining -= len(data)
                observed.update(data)
                target.write(data)
            if source.read(1) or f"sha256:{observed.hexdigest()}" != identity:
                raise ProjectSnapshotError("A source blob failed the declared content digest.")
            target.flush()
            os.fchmod(target.fileno(), FILE_MODES[entry["mode"]])
            os.fsync(target.fileno())


def stage_project_snapshot(snapshot_root: Path, staging_root: Path, binding: dict, *,
                           max_manifest_bytes: int, max_files: int, max_bytes: int) -> Path:
    """Return a fresh verified directory. Roots and limits come from Platform custody."""
    if not all(type(value) is int and value > 0 for value in (max_manifest_bytes, max_files, max_bytes)):
        raise ProjectSnapshotError("Reviewed file and byte limits are required for source staging.")
    staged = None
    try:
        content_id = validate_binding(binding)
        with directory_fd(snapshot_root) as root, directory_fd(content_id, parent=root) as directory:
            manifest = read_manifest(directory, binding, max_manifest_bytes=max_manifest_bytes,
                                     max_files=max_files, max_bytes=max_bytes)
            with directory_fd("blobs", parent=directory) as blobs:
                staged = Path(tempfile.mkdtemp(prefix="project-source-", dir=staging_root))
                for entry in manifest:
                    copy_blob(blobs, entry, staged / entry["path"])
        for directory, _, _ in os.walk(staged, topdown=False):
            with directory_fd(directory) as descriptor:
                os.fsync(descriptor)
        with directory_fd(staging_root) as descriptor:
            os.fsync(descriptor)
        return staged
    except (OSError, KeyError, TypeError, ValueError, RecursionError) as error:
        if staged is not None:
            shutil.rmtree(staged)
        if isinstance(error, ProjectSnapshotError):
            raise
        if isinstance(error, ProjectSetupError):
            raise ProjectSnapshotError(str(error)) from None
        raise ProjectSnapshotError("The exact private source snapshot could not be verified and staged.") from None
