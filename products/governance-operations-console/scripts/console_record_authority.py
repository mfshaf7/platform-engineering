"""Maintain the existing Console composition's private canonical-data clones.

No primary checkout is pulled or rewritten. Non-data source remains exactly
reviewed; consumers require a short-lived, atomically published checkpoint.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
from typing import Any


OWNERS = {"workspace-governance", "workspace-prototype-studio"}
TRUSTED_REF = "refs/remotes/origin/main"
CANDIDATE_REF = "refs/console-record-authority/candidate"
CHECKPOINT = "console-record-authority.json"
COMMIT = re.compile(r"[0-9a-f]{40}")
WG_DATA = {f"contracts/{name}.yaml" for name in (
    "repos", "products", "components", "intake-register", "workspace-inventory-history",
)} | {"product-publication/manifest.json"}


class RecordAuthorityError(RuntimeError):
    """A current approved data snapshot cannot be established."""


def git(root: Path, *args: str, timeout: int = 45) -> str:
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0",
        "GIT_NO_REPLACE_OBJECTS": "1", "GIT_GRAFT_FILE": os.devnull,
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
    try:
        result = subprocess.run(["git", "-c", f"core.hooksPath={os.devnull}",
            "-C", str(root), *args], env=env, capture_output=True, timeout=timeout,
            check=True, encoding="utf-8", umask=0o022)
        if len(result.stdout.encode()) > 4 * 1024 * 1024:
            raise RecordAuthorityError("record refresh Git output exceeded its bound")
        return result.stdout.rstrip("\n")
    except (OSError, subprocess.SubprocessError, UnicodeError):
        # Do not project Git arguments, endpoints or credential diagnostics.
        raise RecordAuthorityError("canonical record Git operation failed") from None


def data_path(owner: str, value: str) -> bool:
    path = PurePosixPath(value)
    if (not re.fullmatch(r"[A-Za-z0-9._/-]{1,512}", value) or "//" in value
        or path.is_absolute() or any(part in {"..", ".git", ".gitattributes", ".gitmodules"} for part in path.parts)):
        return False
    if owner == "workspace-governance":
        return value in WG_DATA or (
            value.startswith(("reviews/improvement-candidates/", "reviews/after-action/"))
            and path.suffix == ".yaml"
        ) or (value.startswith("docs/records/change-records/") and path.suffix == ".md")
    if owner != "workspace-prototype-studio":
        return False
    if value == "prototypes.yaml":
        return True
    if value.startswith("prototypes/") and len(path.parts) >= 3:
        return True  # Incubation application source is data to this control plane.
    if value.startswith("fixtures/prototypes/") and len(path.parts) >= 4:
        return True  # Landing's Prototype-local synthetic fixtures, not control code.
    return (
        value.startswith(("records/", "docs/prototypes/"))
        and path.suffix in {".json", ".yaml", ".yml", ".md"}
    )


def admit_record_delta(root: Path, owner: str, reviewed: str, candidate: str,
                       previous: str | None = None) -> list[str]:
    if owner not in OWNERS or not COMMIT.fullmatch(reviewed) or not COMMIT.fullmatch(candidate):
        raise RecordAuthorityError("canonical record owner or source identity is invalid")
    git(root, "merge-base", "--is-ancestor", reviewed, candidate)
    if previous:
        if not COMMIT.fullmatch(previous):
            raise RecordAuthorityError("prior canonical record identity is invalid")
        git(root, "merge-base", "--is-ancestor", previous, candidate)
    if int(git(root, "rev-list", "--count", f"{reviewed}..{candidate}")) > 2048:
        raise RecordAuthorityError("record-only advancement exceeds the reviewed history bound")
    entries = git(root, "diff", "--raw", "-z", "--no-renames", reviewed, candidate).split("\0")
    changed: list[str] = []
    for index in range(0, len(entries) - 1, 2):
        header, name = entries[index:index + 2]
        modes = header.split()
        if (len(modes) != 5 or not data_path(owner, name)
            or modes[0] not in {":000000", ":100644"}
            or modes[1] not in {"000000", "100644"}
            or modes[4] not in {"A", "M", "D"}):
            raise RecordAuthorityError("canonical update changes reviewed code, schema, policy or file mode")
        changed.append(name)
    if len(changed) > 4096:
        raise RecordAuthorityError("canonical record change exceeds the path bound")
    return changed


def _private_directory(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid():
        raise RecordAuthorityError("record cache directory is unsafe")
    root.chmod(0o700)


def provider_remote(source: Path, owner: str) -> str:
    remote = git(source, "remote", "get-url", "origin")
    if remote not in {f"git@github.com:mfshaf7/{owner}.git",
                      f"git@github.com:mfshaf7/{owner}",
                      f"https://github.com/mfshaf7/{owner}.git",
                      f"https://github.com/mfshaf7/{owner}"}:
        raise RecordAuthorityError("record source does not identify the fixed canonical provider")
    return remote


def invalidate_snapshot(cache_root: Path, owner: str) -> None:
    if owner not in OWNERS:
        return
    root = cache_root / owner
    if (not cache_root.is_symlink() and not root.is_symlink()
        and not (root / ".git").is_symlink() and (root / ".git").is_dir()
        and root.stat().st_uid == os.geteuid()
        and (root / ".git").stat().st_uid == os.geteuid()):
        (root / ".git" / CHECKPOINT).unlink(missing_ok=True)


def refresh_snapshot(cache_root: Path, source: Path, owner: str, reviewed: str,
                     *, now: datetime | None = None, remote_for_test: Path | None = None,
                     before_change=None) -> dict[str, Any]:
    if owner not in OWNERS:
        raise RecordAuthorityError("canonical record owner is invalid")
    try:
        return _refresh_snapshot(cache_root, source, owner, reviewed,
            now=now, remote_for_test=remote_for_test, before_change=before_change)
    except (RecordAuthorityError, OSError, ValueError, TypeError, KeyError):
        # Failed observation must still fail closed, even when the last
        # successful checkpoint had not expired yet.
        invalidate_snapshot(cache_root, owner)
        raise


def _refresh_snapshot(cache_root: Path, source: Path, owner: str, reviewed: str,
                     *, now: datetime | None = None, remote_for_test: Path | None = None,
                     before_change=None) -> dict[str, Any]:
    """Refresh one fixed owner. remote_for_test is native-Git test injection only."""
    if owner not in OWNERS or not COMMIT.fullmatch(reviewed):
        raise RecordAuthorityError("record source owner or reviewed baseline is invalid")
    _private_directory(cache_root)
    root = cache_root / owner
    remote = str(remote_for_test) if remote_for_test is not None else None
    if not root.exists():
        remote = remote or provider_remote(source, owner)
        with tempfile.TemporaryDirectory(prefix="record-clone-", dir=cache_root) as directory:
            clone = Path(directory) / owner
            git(cache_root, "clone", "--no-hardlinks", "--no-checkout", str(source), str(clone))
            git(clone, "remote", "set-url", "origin", remote)
            git(clone, "checkout", "--detach", reviewed)
            os.replace(clone, root)
    if (root.is_symlink() or not root.is_dir() or (root / ".git").is_symlink()
        or not (root / ".git").is_dir() or root.stat().st_uid != os.geteuid()
        or (root / ".git").stat().st_uid != os.geteuid()):
        raise RecordAuthorityError("record cache is not a regular private clone")
    checkpoint = root / ".git" / CHECKPOINT
    previous = git(root, "rev-parse", "HEAD")
    if checkpoint.exists() or checkpoint.is_symlink():
        try:
            info = checkpoint.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_size > 2048:
                raise ValueError()
            value = json.loads(checkpoint.read_text())
            if value["owner_repo"] != owner or value["record_revision"] != previous:
                raise ValueError()
            if value["reviewed_revision"] != reviewed:
                if before_change:
                    before_change()
                checkpoint.unlink(missing_ok=True)  # A different source set cannot borrow freshness.
        except (OSError, ValueError, TypeError, KeyError):
            raise RecordAuthorityError("retained record checkpoint is malformed or from another source set") from None
    remote = remote or provider_remote(source, owner)
    if git(root, "remote", "get-url", "origin") != remote:
        raise RecordAuthorityError("record cache provider identity changed")
    if git(root, "status", "--porcelain", "--untracked-files=normal"):
        raise RecordAuthorityError("record cache contains unproven local work; preserve and inspect it")
    # Only this private candidate ref advances before admission; live trusted
    # main and all primary checkouts remain untouched on rejection.
    git(root, "fetch", "--no-tags", "origin", f"+refs/heads/main:{CANDIDATE_REF}")
    candidate = git(root, "rev-parse", f"{CANDIDATE_REF}^{{commit}}")
    changed = admit_record_delta(root, owner, reviewed, candidate, previous)
    if candidate != previous or git(root, "rev-parse", TRUSTED_REF) != candidate:
        if before_change:
            before_change()
        checkpoint.unlink(missing_ok=True)
        git(root, "checkout", "--detach", candidate)
        git(root, "update-ref", TRUSTED_REF, candidate)
    observed = now or datetime.now(timezone.utc)
    value = dict(schema_version=1, owner_repo=owner, trusted_ref=TRUSTED_REF,
        reviewed_revision=reviewed, record_revision=candidate,
        observed_at=observed.isoformat(), valid_until=(observed + timedelta(minutes=5)).isoformat())
    with tempfile.NamedTemporaryFile(mode="w", dir=root / ".git", prefix="record-checkpoint-", delete=False) as stream:
        json.dump(value, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
        pending = Path(stream.name)
    # The containing host cache is private; the bind-mounted clone is read-only
    # to OOS/WGCF's distinct non-root runtime users.
    pending.chmod(0o644)
    os.replace(pending, checkpoint)
    return {"owner_repo": owner, "reviewed_revision": reviewed,
        "record_revision": candidate, "changed_path_count": len(changed),
        "valid_until": value["valid_until"]}


def snapshot_status(cache_root: Path, owner: str, reviewed: str,
                    *, now: datetime | None = None) -> dict[str, Any]:
    root = cache_root / owner
    try:
        file = root / ".git" / CHECKPOINT
        info = file.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > 2048:
            raise ValueError()
        value = json.loads(file.read_bytes())
        observed = datetime.fromisoformat(value["observed_at"])
        expires = datetime.fromisoformat(value["valid_until"])
        current = now or datetime.now(timezone.utc)
        if (type(value["schema_version"]) is not int or value["schema_version"] != 1 or value["owner_repo"] != owner
            or value["reviewed_revision"] != reviewed or value["trusted_ref"] != TRUSTED_REF
            or observed.tzinfo is None or expires.tzinfo is None
            or observed > current + timedelta(seconds=30) or expires <= current
            or expires <= observed or expires - observed > timedelta(minutes=10)
            or git(root, "rev-parse", "HEAD") != value["record_revision"]
            or git(root, "rev-parse", TRUSTED_REF) != value["record_revision"]
            or git(root, "status", "--porcelain", "--untracked-files=normal")):
            raise ValueError()
        admit_record_delta(root, owner, reviewed, value["record_revision"])
        return {"owner_repo": owner, "reviewed_revision": reviewed,
            "record_revision": value["record_revision"], "valid_until": value["valid_until"]}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        raise RecordAuthorityError("current Platform canonical record snapshot is unavailable") from None
