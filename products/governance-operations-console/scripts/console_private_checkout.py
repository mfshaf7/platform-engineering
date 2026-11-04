"""Finite authenticated Git reads into installation-private managed source.

OOS retains checkout/request provenance. Platform derives every path and provider
URL and retains the reduced token. No command, destination or token is a field.
"""
from __future__ import annotations

import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any
from urllib.parse import quote

from agent_source_instance import InstanceSourceSnapshot, OPERATIONS, validated_snapshot, digest
import console_private_source as source

NAME = re.compile(r"[a-z0-9][a-z0-9._-]{0,185}")
BRANCH = re.compile(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,180}")


def validate_input(value: Any) -> dict:
    fields = {"schema_version", "owner_repo", "operation", "action", "branch", "expected_base", "authority_ref"}
    if (not isinstance(value, dict) or set(value) != fields or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or not isinstance(value["owner_repo"], str) or not NAME.fullmatch(value["owner_repo"])
            or not isinstance(value["operation"], str) or value["operation"] not in OPERATIONS
            or not isinstance(value["action"], str) or value["action"] not in {"clone", "fetch", "ref"}
            or not isinstance(value["branch"], str) or not BRANCH.fullmatch(value["branch"])
            or any(part in {"", ".", ".."} or part.endswith(".lock") or part.startswith(".") for part in value["branch"].split("/"))
            or ".." in value["branch"] or value["branch"].endswith(".")
            or value["action"] == "clone" and value["branch"] != "main"
            or value["expected_base"] is not None and (not isinstance(value["expected_base"], str) or not source.SHA.fullmatch(value["expected_base"]))
            or not isinstance(value["authority_ref"], dict) or set(value["authority_ref"]) != {"canonical_authority", "record_ref", "policy_ref"}):
        raise source.PrivateSourceError("Select the exact source owner, branch and bounded checkout action.")
    return value


def source_location(workspace_root: Path, snapshot: InstanceSourceSnapshot) -> Path:
    namespace = hashlib.sha256(snapshot.instance_id.encode()).hexdigest()[:32]
    return workspace_root / ".worktrees" / "instance-sources" / namespace / "repositories" / snapshot.owner_repo


def _directory(path: Path, *, create=False, private=True):
    if create:
        try: path.mkdir(mode=0o700)
        except FileExistsError: pass
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or path.is_symlink() or info.st_uid != os.geteuid()
            or private and stat.S_IMODE(info.st_mode) & 0o077):
        raise source.PrivateSourceError("The managed source directory is missing, linked or not private.")


def _run(args, *, env, cwd=None, execute=subprocess.run, deadline=None) -> str:
    try:
        remaining = 90 if deadline is None else min(90, deadline - time.monotonic())
        if remaining <= 0:
            raise source.PrivateSourceError("The authenticated checkout exceeded its complete read budget.")
        result = execute(["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "-c", "credential.helper=",
            "-c", "http.followRedirects=false", "-c", "submodule.recurse=false", "-c", "pack.threads=1", *args],
            cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=remaining, check=True)
        if len(result.stdout) > 65536:
            raise source.PrivateSourceError("Source checkout exceeded its output bound.")
        return result.stdout.decode("utf-8", errors="strict").strip()
    except (subprocess.SubprocessError, OSError, UnicodeError):
        raise source.PrivateSourceError("The exact authenticated Git read did not complete; preserve its source and retry.") from None


def checkout(value, *, workspace_root: Path, private_root: Path, snapshot_reader, args, client=None, execute=subprocess.run):
    value = validate_input(value)
    _directory(private_root, create=True)
    locks = private_root / "source-checkout-locks"; _directory(locks, create=True)
    namespace = value["authority_ref"].get("canonical_authority")
    key = hashlib.sha256(json.dumps([namespace, value["owner_repo"]], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    descriptor = os.open(locks / key, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise source.PrivateSourceError("The managed checkout lock is not private owner state.")
        try: fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise source.PrivateSourceError("The original checkout read is still running; retry it before starting another.") from None
        return _checkout_locked(value, workspace_root=workspace_root, private_root=private_root, snapshot_reader=snapshot_reader, args=args, client=client, execute=execute)
    finally:
        os.close(descriptor)


def _checkout_locked(value, *, workspace_root: Path, private_root: Path, snapshot_reader, args, client=None, execute=subprocess.run):
    value = validate_input(value)
    snapshot = snapshot_reader()
    if not isinstance(snapshot, InstanceSourceSnapshot):
        raise source.PrivateSourceError("Authenticated checkout requires current internal source admission.")
    validated_snapshot({"schema_version": 1, "canonical_authority": snapshot.source_authority.get("canonical_authority"), "source_authority": snapshot.source_authority},
        instance_id=snapshot.instance_id, owner=value["owner_repo"], operation=value["operation"], policy_ref=snapshot.policy_ref)
    if snapshot.owner_repo != value["owner_repo"] or snapshot.operation != value["operation"] or digest(source.authority_ref(snapshot)) != digest(value["authority_ref"]):
        raise source.PrivateSourceError("The source registration changed after checkout preparation.")
    if not workspace_root.is_absolute() or workspace_root.resolve() != workspace_root:
        raise source.PrivateSourceError("The accepted source workspace is unavailable.")
    _directory(workspace_root, private=False)
    target = source_location(workspace_root, snapshot)
    # Shared .worktrees keeps its existing mode. Every native descendant is
    # private and owner-created. Never chmod/adopt an existing public directory.
    for index, part in enumerate(target.relative_to(workspace_root).parts[:-1]):
        parent = workspace_root.joinpath(*target.relative_to(workspace_root).parts[:index + 1])
        _directory(parent, create=True, private=index > 0)
    _directory(target, create=True)
    _directory(private_root, create=True)
    if value["action"] == "clone" and any(target.iterdir()):
        raise source.PrivateSourceError("Clone may use only its originally absent empty destination; preserve existing source.")
    if value["action"] != "clone":
        _directory(target / ".git", private=False)
        for relative in (".git/config", ".git/HEAD"):
            info = (target / relative).lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid():
                raise source.PrivateSourceError("The selected checkout metadata is not regular owner source.")
        if (target / ".git/objects/info/alternates").exists():
            raise source.PrivateSourceError("The selected checkout borrows external Git objects.")
    binding = snapshot.source_authority["provider_repository"]
    selected = client
    if selected is None:
        base = source.identity.load_contract(args.contract)
        selected = source.InspectionClient(base.api_base_url, budget_seconds=160)
    deadline = time.monotonic() + 150
    with source.repository_read_token(snapshot, args, client=selected) as (provider, token):
        main, tree, visibility = source._current(provider, token.token, binding)
        # Existing provider service PrivateTmp makes this volatile across PC
        # restart. It must never be retained beside installation backup records.
        with tempfile.TemporaryDirectory(prefix="source-read-") as temporary:
            temporary = Path(temporary)
            secret = temporary / "credential"; secret.write_text(token.token); secret.chmod(0o600)
            askpass = temporary / "askpass"
            askpass.write_text(f"#!{sys.executable}\nimport pathlib,sys\nprint('x-access-token' if 'username' in sys.argv[1].lower() else pathlib.Path({str(secret)!r}).read_text())\n")
            askpass.chmod(0o700)
            env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(temporary), "XDG_CONFIG_HOME": str(temporary),
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
                "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": str(askpass), "GIT_ALLOW_PROTOCOL": "https",
                "GIT_NO_REPLACE_OBJECTS": "1", "GIT_GRAFT_FILE": "/dev/null", "GIT_LFS_SKIP_SMUDGE": "1"}
            git = lambda command, cwd=None: _run(command, env=env, cwd=cwd, execute=execute, deadline=deadline)
            url = f"https://github.com/{binding['full_name']}.git"
            if value["action"] != "clone":
                if (git(["rev-parse", "--show-toplevel"], target) != str(target)
                        or git(["remote", "get-url", "origin"], target) not in {url, f"git@github.com:{binding['full_name']}.git"}):
                    raise source.PrivateSourceError("The checkout no longer matches the exact admitted source.")
            remote = git(["ls-remote", "--heads", url, f"refs/heads/{value['branch']}"], target)
            remote_rows = remote.splitlines() if remote else []
            if len(remote_rows) > 1:
                raise source.PrivateSourceError("The exact source branch is ambiguous.")
            remote_commit = None
            if remote_rows:
                parts = remote_rows[0].split()
                if len(parts) != 2 or not source.SHA.fullmatch(parts[0]) or parts[1] != f"refs/heads/{value['branch']}":
                    raise source.PrivateSourceError("The exact source branch is invalid.")
                remote_commit = parts[0]
            if value["expected_base"] is not None and remote_commit != value["expected_base"]:
                raise source.PrivateSourceError("The selected source branch changed before checkout.")
            if value["branch"] == "main" and remote_commit != main:
                raise source.PrivateSourceError("The current provider main differs from its authenticated Git branch.")
            if value["action"] in {"clone", "fetch"}:
                if remote_commit is None:
                    raise source.PrivateSourceError("The selected source branch is absent.")
                if value["action"] == "clone":
                    git(["clone", "--template=", "--single-branch", "--branch", "main", "--", url, str(target)])
                    git(["remote", "set-url", "origin", f"git@github.com:{binding['full_name']}.git"], target)
                else:
                    git(["fetch", "--no-recurse-submodules", "--", url, f"+refs/heads/{value['branch']}:refs/remotes/origin/{value['branch']}"], target)
                if git(["rev-parse", f"refs/remotes/origin/{value['branch']}"], target) != remote_commit:
                    raise source.PrivateSourceError("The source branch moved while checkout was in progress.")
                if value["branch"] == "main" and git(["rev-parse", f"{remote_commit}^{{tree}}"], target) != tree:
                    raise source.PrivateSourceError("The fetched source tree differs from the provider commit.")
            if source._current(provider, token.token, binding) != (main, tree, visibility):
                raise source.PrivateSourceError("The provider source changed while checkout was in progress.")
            after = snapshot_reader()
            if not isinstance(after, InstanceSourceSnapshot) or digest(after.source_authority) != digest(snapshot.source_authority):
                raise source.PrivateSourceError("Source registration changed while checkout was in progress.")
            return {"schema_version": 1, "read_scope": "repository-checkout", "owner_repo": snapshot.owner_repo, "operation": snapshot.operation,
                "authority_ref": source.authority_ref(snapshot), "provider_repository": binding,
                "action": value["action"], "branch": value["branch"], "remote_commit": remote_commit,
                "workspace_relative_path": target.relative_to(workspace_root).as_posix(),
                "read_credential_issued": True, "read_credential_revoked": True}
