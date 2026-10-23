"""Maintain the existing Console composition's private canonical-data clones.

No primary checkout is pulled or rewritten. Non-data source remains exactly
reviewed; consumers require a short-lived, atomically published checkpoint.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import io
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import tempfile
import tarfile
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from repository_provider_identity import IdentityError, observe_public_repository_main


OWNERS = {"workspace-governance", "workspace-prototype-studio"}
TRUSTED_REF = "refs/remotes/origin/main"
CANDIDATE_REF = "refs/console-record-authority/candidate"
CHECKPOINT = "console-record-authority.json"
COMMIT = re.compile(r"[0-9a-f]{40}")
WG_DATA = {f"contracts/{name}.yaml" for name in (
    "repos", "products", "components", "intake-register", "workspace-inventory-history",
)} | {"product-publication/manifest.json"}
WG_REGISTRATION_COMPANIONS = {
    *(f"workspace-root/{name}.md" for name in ("AGENTS", "README", "ARCHITECTURE")),
    "contracts/context-behavior.yaml", "contracts/raw-context-retirement.yaml",
    "generated/system-map.yaml", "generated/resolved-owner-map.json",
    "generated/resolved-dependency-graph.json", "generated/stale-content-rules.json",
    "generated/governance-engine-boundary-map.json", "generated/console-operational-capabilities.json",
}
REGISTRATION_VALIDATOR = "scripts/workspace_repo_registration.py"
INTAKE_OWNER_MARKER = "console-intake-owner-source.json"
INTAKE_SOURCE_MOUNTPOINTS = OWNERS | {"governance-operations-console"}


class RecordAuthorityError(RuntimeError):
    """A current approved data snapshot cannot be established."""


def public_owner_main(binding: dict[str, Any]) -> str:
    """Reuse Platform's fixed-host anonymous observer, never a source token."""
    try:
        return observe_public_repository_main(binding)
    except IdentityError:
        raise RecordAuthorityError("public owner observation is unavailable") from None


def _write_owner_attribution(root: Path, value: dict[str, Any]) -> None:
    with tempfile.NamedTemporaryFile(mode="w", dir=root / ".git", prefix="owner-attribution-", delete=False) as stream:
        json.dump(value, stream, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
        pending = Path(stream.name)
    pending.chmod(0o644)
    os.replace(pending, root / ".git" / INTAKE_OWNER_MARKER)


def _current_owner_observation(root: Path, name: str, head: str, binding: dict[str, Any]) -> dict[str, Any] | None:
    """Reuse only the existing short-lived observation, never renew its age.

    Repeated unchanged timer ticks must not burn anonymous provider quota or
    turn one provider response into permanently current source authority.
    """
    marker = root / ".git" / INTAKE_OWNER_MARKER
    try:
        if (root.is_symlink() or (root / ".git").is_symlink() or marker.is_symlink()
            or not marker.is_file() or marker.stat().st_size > 4096):
            return None
        value = json.loads(marker.read_bytes())
        now = datetime.now(timezone.utc)
        observed, expires = datetime.fromisoformat(value["observed_at"]), datetime.fromisoformat(value["valid_until"])
        if (set(value) == {"schema_version", "owner_repo", "head", "provider_repository", "observed_at", "valid_until"}
            and type(value["schema_version"]) is int and value["schema_version"] == 1
            and value["owner_repo"] == name and value["head"] == head and value["provider_repository"] == binding
            and observed.tzinfo is not None and expires.tzinfo is not None
            and observed <= now + timedelta(seconds=30) and expires > now + timedelta(seconds=30)
            and timedelta(0) < expires - observed <= timedelta(minutes=5)):
            return {key: value[key] for key in ("schema_version", "observed_at", "valid_until")}
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def require_bounded_owner_tree(root: Path, revision: str) -> None:
    entries = git(root, "ls-tree", "-rl", "--full-tree", revision).splitlines()
    sizes = [line.split("\t", 1)[0].split() for line in entries]
    if (len(entries) > 8192 or any(len(row) != 4 or row[1] != "blob"
            or row[0] not in {"100644", "100755"} or not row[3].isdigit()
            or int(row[3]) > 4 * 1024 * 1024 for row in sizes)
        or sum(int(row[3]) for row in sizes) > 32 * 1024 * 1024):
        raise RecordAuthorityError("owner source exceeds its regular-file or size bound")


def refresh_intake_owner_sources(cache_root: Path, workspace_root: Path, reviewed: str) -> dict[str, Any]:
    """Project committed owner source, never execute it.

    The fixed WG checkpoint authorizes the selection, not application execution.
    Only generated clones are retired; real owner checkouts are never modified.
    """
    state = snapshot_status(cache_root, "workspace-governance", reviewed)
    visible_root = cache_root.parent / "intake-owner-sources"
    if visible_root.is_symlink():
        raise RecordAuthorityError("physical owner source projection root is unsafe")
    visible_root.mkdir(mode=0o755, exist_ok=True)
    if not visible_root.is_dir() or visible_root.stat().st_uid != os.geteuid():
        raise RecordAuthorityError("physical owner source projection root is unsafe")
    visible_root.chmod(0o755)
    authority = cache_root / "workspace-governance"
    revision = state["record_revision"]
    inventory = yaml.safe_load(git(authority, "show", f"{revision}:contracts/repos.yaml"))
    intake = yaml.safe_load(git(authority, "show", f"{revision}:contracts/intake-register.yaml"))
    products = yaml.safe_load(git(authority, "show", f"{revision}:contracts/products.yaml"))
    selected = {name: record for name, record in inventory["repos"].items()
                if record.get("lifecycle") == "active"}
    selected.update({name: record for name, record in intake["repos"].items()
                     if record.get("status") in {"proposed", "admitted"}})
    selected = {name: record for name, record in selected.items()
                if record.get("requires_security_bindings") is False
                and record.get("provider_repository")
                and record.get("validation_behavior", {}).get("posture") == "covered-by-owner-repo"
                and record.get("validation_behavior", {}).get("wgcf_graph_role") == "product-runtime-source"}
    if len(selected) > 64:
        raise RecordAuthorityError("physical owner source projection exceeds its bound")
    projected, unavailable, publication_unavailable = {}, [], []
    for name, record in sorted(selected.items()):
        binding = record["provider_repository"]
        full_name = binding.get("full_name", "")
        if (not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", name)
            or name in INTAKE_SOURCE_MOUNTPOINTS
            or binding.get("provider") != "github"
            or not re.fullmatch(r"[1-9][0-9]*", str(binding.get("provider_repository_id", "")))
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*", full_name)):
            raise RecordAuthorityError("physical owner source selection is invalid")
        source = workspace_root / name
        try:
            if (source.is_symlink() or source.resolve().parent != workspace_root.resolve()
                or not source.is_dir() or (source / ".git").is_symlink()
                or not (source / ".git").is_dir()
                or any((source / path).is_symlink() or not (source / path).is_file()
                       for path in ("AGENTS.md", "README.md", ".git/config", ".git/HEAD"))):
                raise RecordAuthorityError("owner controls are not present")
            head = git(source, "rev-parse", "HEAD")
            remote = git(source, "remote", "get-url", "origin")
            if (not COMMIT.fullmatch(head) or head != git(source, "rev-parse", TRUSTED_REF)
                or git(source, "symbolic-ref", "--short", "HEAD") != "main"
                or git(source, "rev-parse", "--show-toplevel") != str(source.resolve())
                or git(source, "status", "--porcelain", "--untracked-files=all")
                or remote not in {f"https://github.com/{full_name}.git", f"git@github.com:{full_name}.git"}
                or (source / ".git/objects/info/alternates").exists()):
                raise RecordAuthorityError("owner source binding is not current")
            require_bounded_owner_tree(source, head)
            projected[name] = {"head": head, "provider_repository": binding}
            if (name in inventory["repos"] and record.get("posture") == "active"
                and any(product.get("posture") == "active" and name in product.get("source_owners", [])
                        for product in products.get("products", {}).values())):
                try:
                    target = visible_root / name
                    observed_head = head
                    if target.is_dir() and not target.is_symlink():
                        try:
                            observed_head = git(target, "rev-parse", "HEAD")
                            git(target, "merge-base", "--is-ancestor", head, observed_head)
                        except RecordAuthorityError:
                            observed_head = head
                    current_observation = _current_owner_observation(target, name, observed_head, binding)
                    if current_observation is None:
                        observed_head = public_owner_main(binding)
                        if not COMMIT.fullmatch(observed_head):
                            raise RecordAuthorityError("public owner revision is invalid")
                        observed = datetime.now(timezone.utc)
                        current_observation = dict(schema_version=1, observed_at=observed.isoformat(),
                            valid_until=(observed + timedelta(minutes=5)).isoformat())
                    projected[name].update(head=observed_head, **current_observation)
                except RecordAuthorityError:
                    # Keep physical-presence projection but remove Publication
                    # freshness immediately; unavailable remote is not custody.
                    publication_unavailable.append(name)
        except RecordAuthorityError:
            unavailable.append(name)

    def retire(target: Path) -> None:
        marker = target / ".git" / INTAKE_OWNER_MARKER
        if (target.is_symlink() or marker.is_symlink() or not marker.is_file()
            or git(target, "status", "--porcelain", "--untracked-files=all", "--ignored=matching")):
            raise RecordAuthorityError("unattributed or dirty owner snapshot is preserved")
        attribution = json.loads(marker.read_text(encoding="utf-8"))
        if attribution.get("owner_repo") != target.name or attribution.get("head") != git(target, "rev-parse", "HEAD"):
            raise RecordAuthorityError("owner snapshot attribution is invalid")
        retired = cache_root.parent / "retired-intake-owner-sources"
        retired.mkdir(mode=0o700, exist_ok=True)
        if retired.is_symlink():
            raise RecordAuthorityError("retired owner snapshot root is unsafe")
        destination = retired / f"{target.name}-{time_token()}"
        target.rename(destination)

    # OCI cannot create nested bind targets inside a read-only parent mount.
    # Reserve only the existing reviewed source mountpoints; these empty
    # directories are not owner snapshots or evidence of repository presence.
    for name in sorted(INTAKE_SOURCE_MOUNTPOINTS):
        target = visible_root / name
        if target.is_symlink() or (target.exists() and (
            not target.is_dir() or target.stat().st_uid != os.geteuid()
            or any(target.iterdir())
        )):
            raise RecordAuthorityError("non-empty or unsafe reviewed source mountpoint is preserved")
    for name in sorted(INTAKE_SOURCE_MOUNTPOINTS):
        target = visible_root / name
        target.mkdir(mode=0o755, exist_ok=True)
        target.chmod(0o755)
    for target in visible_root.iterdir():
        if target.name in INTAKE_SOURCE_MOUNTPOINTS:
            continue
        if target.name not in projected and not (target / ".git" / INTAKE_OWNER_MARKER).is_file():
            raise RecordAuthorityError("unattributed source projection content is preserved")
        if target.name not in projected and (target / ".git" / INTAKE_OWNER_MARKER).exists():
            retire(target)
    for name, observation in projected.items():
        target, source = visible_root / name, workspace_root / name
        marker = target / ".git" / INTAKE_OWNER_MARKER
        if target.exists():
            if target.is_symlink() or (target / ".git").is_symlink() or not marker.is_file() or marker.is_symlink():
                raise RecordAuthorityError("unattributed owner snapshot is preserved")
            previous = json.loads(marker.read_text(encoding="utf-8"))
            if ({key: previous.get(key) for key in ("owner_repo", "head", "provider_repository")} ==
                {"owner_repo": name, "head": observation["head"], "provider_repository": observation["provider_repository"]}
                and git(target, "rev-parse", "HEAD") == observation["head"]
                and git(target, "remote", "get-url", "origin") == f"https://github.com/{observation['provider_repository']['full_name']}.git"
                and not git(target, "status", "--porcelain", "--untracked-files=all", "--ignored=matching")):
                if previous != {"owner_repo": name, **observation}:
                    _write_owner_attribution(target, {"owner_repo": name, **observation})
                continue
            retire(target)
        with tempfile.TemporaryDirectory(prefix="intake-owner-", dir=cache_root.parent) as temporary:
            staged = Path(temporary) / name
            git(cache_root, "clone", "--local", "--no-hardlinks", "--no-checkout", "--single-branch", "--branch", "main", "--", str(source), str(staged))
            git(staged, "remote", "set-url", "origin", f"https://github.com/{observation['provider_repository']['full_name']}.git")
            local_head = git(source, "rev-parse", "HEAD")
            if observation["head"] != local_head:
                try:
                    # Only the generated, credential-free source clone changes.
                    # Observe the same canonical main and require forward history.
                    git(staged, "fetch", "--no-tags", "origin", "+refs/heads/main:refs/remotes/origin/main")
                    if git(staged, "rev-parse", TRUSTED_REF) != observation["head"]:
                        raise RecordAuthorityError("canonical owner changed during source observation")
                    git(staged, "merge-base", "--is-ancestor", local_head, observation["head"])
                    require_bounded_owner_tree(staged, observation["head"])
                except RecordAuthorityError:
                    # Presence remains valid, but stale or rewritten public source
                    # cannot retain a Publication freshness attestation.
                    observation.clear()
                    observation.update(head=local_head, provider_repository=selected[name]["provider_repository"])
                    git(staged, "update-ref", TRUSTED_REF, local_head)
                    if name not in publication_unavailable:
                        publication_unavailable.append(name)
            git(staged, "checkout", "--detach", observation["head"])
            if git(staged, "rev-parse", "HEAD") != observation["head"] or git(staged, "status", "--porcelain"):
                raise RecordAuthorityError("committed owner snapshot readback differs")
            _write_owner_attribution(staged, {"owner_repo": name, **observation})
            staged.rename(target)
    if snapshot_status(cache_root, "workspace-governance", reviewed)["record_revision"] != revision:
        raise RecordAuthorityError("physical owner selection changed during refresh")
    return {"owners": projected, "unavailable": unavailable, "publication_unavailable": publication_unavailable,
            "authority_revision": revision}


def time_token() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def git(root: Path, *args: str, timeout: int = 45, preserve_output: bool = False) -> str:
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
        return result.stdout if preserve_output else result.stdout.rstrip("\n")
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


def _registration_companion_path(value: str) -> bool:
    # These are NOT generally data paths. They are admitted only when the
    # reviewed owner's semantic projector proves their complete exact delta.
    return value in WG_REGISTRATION_COMPANIONS or bool(
        re.fullmatch(r"contracts/repo-rules/[a-z0-9][a-z0-9._-]*\.yaml", value))


def _validate_registration_companions(root: Path, reviewed: str, candidate: str) -> None:
    with tempfile.TemporaryDirectory(prefix="record-registration-") as directory:
        snapshots = [Path(directory) / name for name in ("reviewed", "candidate")]
        for revision, target in zip((reviewed, candidate), snapshots):
            entries = git(root, "ls-tree", "-rl", "--full-tree", revision).splitlines()
            sizes = [line.split("\t", 1)[0].split() for line in entries]
            if (len(entries) > 8192 or any(len(row) != 4 or row[1] != "blob"
                    or row[0] not in {"100644", "100755"} or not row[3].isdigit()
                    or int(row[3]) > 4 * 1024 * 1024 for row in sizes)
                or sum(int(row[3]) for row in sizes) > 32 * 1024 * 1024):
                raise RecordAuthorityError("registration snapshot exceeds its regular-file or size bound")
            target.mkdir()
            environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
            environment.update({"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1",
                "GIT_GRAFT_FILE": os.devnull, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"})
            result = subprocess.run(["git", "-c", f"core.hooksPath={os.devnull}", "-C", str(root),
                "archive", "--format=tar", revision], env=environment, capture_output=True, timeout=45, check=True)
            if len(result.stdout) > 40 * 1024 * 1024:
                raise RecordAuthorityError("registration snapshot exceeds its bound")
            with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
                if any(not item.isfile() and not item.isdir() for item in archive.getmembers()):
                    raise RecordAuthorityError("registration snapshot contains a non-regular source entry")
                archive.extractall(target, filter="data")
        # Only code from the attested REVIEWED snapshot is imported. All code
        # paths were frozen before this call; the candidate supplies data only.
        result = subprocess.run(["python3", "-c",
            "import pathlib,sys; sys.path.insert(0,sys.argv[1]); "
            "from workspace_repo_registration import validate_registration_companions; "
            "validate_registration_companions(pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]))",
            str(snapshots[0] / "scripts"), *(str(value) for value in snapshots)],
            env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, timeout=60)
        if result.returncode:
            raise RecordAuthorityError("registration changes incomplete companions, protected instructions or existing control policy")
        result = subprocess.run(["python3", str(snapshots[0] / "scripts/validate_contracts.py"),
            "--repo-root", str(snapshots[1])],
            env={"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"},
            capture_output=True, timeout=60)
        if result.returncode:
            raise RecordAuthorityError("registration candidate fails the complete reviewed owner contract model")


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
        allowed = data_path(owner, name) or (owner == "workspace-governance" and _registration_companion_path(name))
        if (len(modes) != 5 or not allowed
            or modes[0] not in {":000000", ":100644"}
            or modes[1] not in {"000000", "100644"}
            or modes[4] not in {"A", "M", "D"}):
            raise RecordAuthorityError("canonical update changes reviewed code, schema, policy or file mode")
        changed.append(name)
    if len(changed) > 4096:
        raise RecordAuthorityError("canonical record change exceeds the path bound")
    if owner == "workspace-governance":
        companions = any(_registration_companion_path(name) for name in changed)
        inventory_changed = any(name in {"contracts/repos.yaml", "contracts/products.yaml", "contracts/components.yaml"} for name in changed)
        reviewed_projector = bool(git(root, "ls-tree", reviewed, "--", REGISTRATION_VALIDATOR))
        if companions and not reviewed_projector:
            raise RecordAuthorityError("registration companions require reviewed owner control code")
        if companions or (inventory_changed and reviewed_projector):
            try:
                _validate_registration_companions(root, reviewed, candidate)
            except (OSError, subprocess.SubprocessError, tarfile.TarError, UnicodeError):
                raise RecordAuthorityError("registration companion verification is unavailable") from None
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


def read_repository_admission(cache_root: Path, reviewed: str) -> dict[str, Any]:
    """Read immutable admission data and reviewed schemas from the existing clone.

    No fetch, refresh or caller-selected source. A concurrent refresh may cause
    a safe retry, but cannot mix schema, inventory and Intake revisions.
    """
    owner = "workspace-governance"
    before = snapshot_status(cache_root, owner, reviewed)
    root = cache_root / owner
    revision = before["record_revision"]
    paths = ("contracts/repos.yaml", "contracts/intake-register.yaml")
    sources = {path: git(root, "show", f"{revision}:{path}", preserve_output=True).encode() for path in paths}
    schemas = {name: json.loads(git(root, "show", f"{reviewed}:contracts/schemas/{name}.schema.json"))
        for name in ("repos", "intake-register")}
    after = snapshot_status(cache_root, owner, reviewed)
    if after["record_revision"] != revision:
        raise RecordAuthorityError("canonical admission changed during source credential preparation; retry readback")
    return {"revision": revision, "reviewed_revision": reviewed,
        "inventory": sources[paths[0]], "intake": sources[paths[1]],
        "inventory_schema": schemas["repos"], "intake_schema": schemas["intake-register"]}
