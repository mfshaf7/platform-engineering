"""Inspect admitted project source and retain reviewed Dev Integration setup."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Any

from agent_source_identity import write_json_atomic
from agent_source_instance import digest, invalid_constant, strict_object


PAIRED_NODE_RECIPE = "node-frontend-api"
NODE_SCRIPTS = {
    "node-frontend": ("build",),
    "node-api": ("start",),
    PAIRED_NODE_RECIPE: ("build", "start:frontend", "start"),
}
RECIPES = frozenset({"static", "no-runtime", *NODE_SCRIPTS})
REGULAR_MODES = {b"100644", b"100755"}
SCOPE_KEYS = {
    "installation_id", "project_custody_ref", "repository_id", "app_root",
    "dependency_paths", "environment_ref",
}
COMMIT = re.compile(r"[0-9a-f]{40}")
MAX_PACKAGE_BYTES = 256 * 1024
MAX_LOCK_BYTES = 8 * 1024 * 1024
MAX_SETUP_BYTES = 256 * 1024


class ProjectSetupError(ValueError):
    """A bounded refusal that does not change project state."""


def source_path(value: Any) -> str:
    if (not isinstance(value, str) or not value or len(value) > 1024
            or re.search(r"[\\:\x00-\x1f\x7f\ud800-\udfff]", value)
            or any(part in {"", ".", ".."} or part.lower() == ".git" or part.endswith((".", " "))
                   for part in value.split("/"))):
        raise ProjectSetupError("A project source path is outside the supported repository-relative form.")
    return value


def scope_key(scope: Any) -> str:
    if (not isinstance(scope, dict) or scope.keys() != SCOPE_KEYS
            or not all(isinstance(scope[key], str) and 0 < len(scope[key]) <= 256
                       and not re.search(r"[\x00-\x1f\x7f\ud800-\udfff]", scope[key])
                       for key in ("installation_id", "project_custody_ref", "environment_ref"))
            or type(scope["repository_id"]) is not int or not 0 < scope["repository_id"] <= 9007199254740991
            or not isinstance(scope["dependency_paths"], list) or len(scope["dependency_paths"]) > 64):
        raise ProjectSetupError("Current project custody and Dev Integration authority are required.")
    if scope["app_root"] != ".":
        source_path(scope["app_root"])
    dependencies = [source_path(item) for item in scope["dependency_paths"]]
    if len(set(dependencies)) != len(dependencies):
        raise ProjectSetupError("Admitted project dependencies must be unique.")
    identity = {key: scope[key] for key in ("installation_id", "project_custody_ref", "app_root", "environment_ref")}
    return digest(identity)[7:]


class CommittedSource:
    """Read named Git objects from an owner-selected repository and exact commit."""

    def __init__(self, repository: Path, commit: str) -> None:
        if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
            raise ProjectSetupError("An exact admitted Git commit is required for setup inspection.")
        try:
            self.repository = repository.resolve(strict=True)
        except OSError:
            raise ProjectSetupError("The admitted Git repository is unavailable.") from None
        self.commit = commit
        if self._git("rev-parse", "--is-bare-repository") != b"true\n":
            checkout = self._git("rev-parse", "--show-toplevel").decode().rstrip("\n")
            if checkout != str(self.repository):
                raise ProjectSetupError("The admitted source must identify the exact Git checkout.")
        if self._git("cat-file", "-t", commit) != b"commit\n":
            raise ProjectSetupError("The admitted source revision is not a Git commit.")

    def _git(self, *arguments: str) -> bytes:
        environment = {
            "PATH": os.defpath, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
            "GIT_ALLOW_PROTOCOL": "", "GIT_NO_LAZY_FETCH": "1", "GIT_TERMINAL_PROMPT": "0",
        }
        try:
            return subprocess.run(
                ["git", "--no-replace-objects", "--literal-pathspecs", *arguments],
                cwd=self.repository, env=environment, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=10, check=True,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            raise ProjectSetupError("The admitted Git source could not be read.") from None

    def _entry(self, name: str) -> tuple[bytes, str, bytes] | None:
        raw = self._git("ls-tree", "-lz", "--full-tree", self.commit, "--", source_path(name))
        if not raw:
            return None
        header, separator, path = raw.partition(b"\t")
        fields = header.split()
        if (not separator or path != name.encode() + b"\0" or len(fields) != 4
                or not re.fullmatch(rb"[0-9a-f]{40}", fields[2])):
            raise ProjectSetupError("The committed project path has unexpected Git metadata.")
        return fields[0], fields[2].decode("ascii"), fields[3]

    def require_path(self, name: str, *, directory: bool = False) -> None:
        entry = self._entry(name)
        allowed = {b"040000"} if directory else {b"040000", *REGULAR_MODES}
        if entry is None or entry[0] not in allowed:
            raise ProjectSetupError("The admitted app folder or dependency is missing or unsupported in this revision.")

    def require_file(self, name: str) -> None:
        entry = self._entry(name)
        if entry is None or entry[0] not in REGULAR_MODES:
            raise ProjectSetupError("The selected recipe requires a committed regular file at the app root.")

    def read_json(self, name: str, maximum: int) -> dict[str, Any]:
        entry = self._entry(name)
        if (entry is None or entry[0] not in REGULAR_MODES or not entry[2].isdigit()
                or int(entry[2]) > maximum):
            raise ProjectSetupError("The selected recipe requires a readable, bounded package manifest and lockfile.")
        content = self._git("cat-file", "blob", entry[1])
        header = f"blob {len(content)}\0".encode()
        if len(content) != int(entry[2]) or hashlib.sha1(header + content).hexdigest() != entry[1]:
            raise ProjectSetupError("The committed package file did not match its Git object.")
        try:
            value = json.loads(content.decode(), object_pairs_hook=strict_object, parse_constant=invalid_constant)
        except (ValueError, RecursionError):
            raise ProjectSetupError("The project package file is not valid JSON.") from None
        if not isinstance(value, dict):
            raise ProjectSetupError("The project package file must contain a JSON object.")
        return value


def inspect_setup(source: CommittedSource, scope: dict, recipe_id: str) -> dict:
    scope_key(scope)
    if not isinstance(recipe_id, str) or recipe_id not in RECIPES:
        raise ProjectSetupError("Choose a supported Dev Integration recipe.")
    root = scope["app_root"]
    if root != ".":
        source.require_path(root, directory=True)
    for dependency in scope["dependency_paths"]:
        source.require_path(dependency)
    prefix = "" if root == "." else f"{root}/"
    if recipe_id == "static":
        source.require_file(f"{prefix}index.html")
    if recipe_id in NODE_SCRIPTS:
        package = source.read_json(f"{prefix}package.json", MAX_PACKAGE_BYTES)
        lock = source.read_json(f"{prefix}package-lock.json", MAX_LOCK_BYTES)
        manager = package.get("packageManager")
        if manager is not None and (not isinstance(manager, str) or not manager.startswith("npm@")):
            raise ProjectSetupError("This Node recipe requires an npm lockfile.")
        if type(lock.get("lockfileVersion")) is not int or lock["lockfileVersion"] not in (2, 3):
            raise ProjectSetupError("Use an npm lockfile with lockfile version 2 or 3.")
        scripts = package.get("scripts")
        for script in NODE_SCRIPTS[recipe_id]:
            if not isinstance(scripts, dict) or not isinstance(scripts.get(script), str) or not scripts[script].strip():
                raise ProjectSetupError(f"The selected Node recipe needs a {script} script in package.json.")
    return {"base_commit": source.commit, "recipe_id": recipe_id}


class ProjectSetupStore:
    """Store setup inside the Platform OperationStore's private owner state."""

    def __init__(self, operations: Any) -> None:
        self.operations = operations
        self.directory = operations.root / "project-setups"

    def _read(self, key: str) -> dict | None:
        try:
            directory = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        except OSError:
            raise ProjectSetupError("The private project setup storage is unavailable.") from None
        try:
            if stat.S_IMODE(os.fstat(directory).st_mode) & 0o077:
                raise ProjectSetupError("The private project setup directory has unsafe permissions.")
            descriptor = os.open(f"{key}.json", os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > MAX_SETUP_BYTES:
                    raise ProjectSetupError("The retained project setup has unsafe file metadata.")
                content = stream.read(MAX_SETUP_BYTES + 1)
                if len(content) > MAX_SETUP_BYTES:
                    raise ProjectSetupError("The retained project setup exceeds its read limit.")
                record = json.loads(content, object_pairs_hook=strict_object, parse_constant=invalid_constant)
            if (not isinstance(record, dict) or type(record.get("schema_version")) is not int or record["schema_version"] != 1
                    or scope_key(record.get("scope")) != key or type(record.get("revision")) is not int
                    or record["revision"] < 1 or not isinstance(record.get("setup"), dict)
                    or record["setup"].get("configuration_revision") != f"project-setup:{key}:{record['revision']}"
                    or record["setup"].get("recipe_id") not in RECIPES
                    or not isinstance(record.get("inspection"), dict)
                    or record["inspection"].get("recipe_id") != record["setup"]["recipe_id"]
                    or not COMMIT.fullmatch(str(record["inspection"].get("base_commit", "")))):
                raise ProjectSetupError("The retained project setup is invalid.")
            return record
        except FileNotFoundError:
            return None
        except ProjectSetupError:
            raise
        except (OSError, TypeError, ValueError, RecursionError):
            raise ProjectSetupError("The retained project setup is unreadable.") from None
        finally:
            os.close(directory)

    def read(self, scope: dict) -> dict | None:
        record = self._read(scope_key(scope))
        if record is not None and record["scope"] != scope:
            raise ProjectSetupError("The retained setup needs review after the admitted source scope changed.")
        return record

    def save(self, scope: dict, *, requested_app_root: str, recipe_id: str,
             expected_revision: str | None, source: CommittedSource) -> dict:
        key = scope_key(scope)
        if requested_app_root != scope["app_root"]:
            raise ProjectSetupError("The selected app folder differs from the current source authorization.")
        with self.operations.lock(f"project-runtime-scope:{key}"):
            current = self._read(key)
            if (current["setup"]["configuration_revision"] if current else None) != expected_revision:
                raise ProjectSetupError("Project setup changed. Reload it before applying your changes.")
            inspection = inspect_setup(source, scope, recipe_id)
            if current and current["scope"] == scope and current["inspection"] == inspection:
                return current
            revision = current["revision"] + 1 if current else 1
            record = {
                "schema_version": 1,
                "scope": scope,
                "setup": {"recipe_id": recipe_id, "configuration_revision": f"project-setup:{key}:{revision}"},
                "revision": revision,
                "inspection": inspection,
            }
            write_json_atomic(self.directory / f"{key}.json", record)
            return record
