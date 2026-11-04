"""Finite control-file inspection through the existing protected Platform API.

The Source App stays in Platform custody. Full installation verification precedes
a reduced one-repository read token. Only trusted owner controls are returned to
the OOS preparation service; no generic operation journal or model receives them.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import time
from contextlib import contextmanager
from typing import Any, Callable

import agent_source_identity as identity
from agent_source_bootstrap import PATHS
from agent_source_instance import InstanceSourceSnapshot, validated_snapshot, digest

SHA = re.compile(r"[0-9a-f]{40}")
MAX_FILE_BYTES = 65536
MAX_RESULT_BYTES = 524288


class PrivateSourceError(RuntimeError):
    """No private file bytes or credentials may appear in this exception."""


def authority_ref(snapshot: InstanceSourceSnapshot) -> dict[str, Any]:
    proof = snapshot.source_authority
    return {"canonical_authority": proof["canonical_authority"], "record_ref": proof["record_ref"], "policy_ref": proof["policy_ref"]}


@contextmanager
def repository_read_token(snapshot: InstanceSourceSnapshot, args, *, client=None):
    """Existing Source App custody, reduced for one finite read operation."""
    binding = snapshot.source_authority["provider_repository"]
    base = identity.select_installation(identity.load_contract(args.contract), binding["full_name"])
    repository = identity.Repository(binding["full_name"], int(binding["provider_repository_id"]))
    base = identity.replace(base, repositories=(repository,))
    selected = client or InspectionClient(base.api_base_url)
    token = None
    try:
        with identity.private_key_file(base, vault_command=args.vault_command, sandbox=args.sandbox,
                sandbox_private_key=getattr(args, "private_key_file", None), timeout_seconds=10) as key:
            jwt = identity.verify_provider_identity(base, selected, key)
            token, _ = identity.issue_repository_token(identity.replace(base, required_permissions={"metadata": "read", "contents": "read"}), selected, jwt, repository)
        yield selected, token
    except identity.IdentityError:
        raise PrivateSourceError("The protected source connection could not complete its read operation.") from None
    finally:
        if token is not None:
            try:
                selected.revoke_token(token.token)
            except Exception:
                raise PrivateSourceError("The read credential could not be confirmed revoked; completion was withheld.") from None


def validate_input(value: Any) -> dict[str, Any]:
    if (not isinstance(value, dict) or set(value) != {"schema_version", "owner_repo", "operation", "paths", "authority_ref"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or not isinstance(value["owner_repo"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,185}", value["owner_repo"])
            or not isinstance(value["operation"], str) or value["operation"] not in {"bootstrap", "configure-verification"}
            or not isinstance(value["paths"], list) or not value["paths"] or len(value["paths"]) > len(PATHS)
            or any(not isinstance(path, str) or path not in PATHS for path in value["paths"])
            or value["paths"] != sorted(set(value["paths"]))
            or not isinstance(value["authority_ref"], dict) or set(value["authority_ref"]) != {"canonical_authority", "record_ref", "policy_ref"}):
        raise PrivateSourceError("Select the exact current owner and finite trusted control files.")
    return value


class InspectionClient(identity.ProviderClient):
    """Bound the complete provider read while preserving a final revoke attempt."""
    def __init__(self, base_url: str, *, sandbox: bool = False, clock: Callable[[], float] = time.monotonic, budget_seconds: int = 45):
        super().__init__(base_url, sandbox=sandbox, request_timeout=10)
        self._clock, self._deadline, self._revoking = clock, clock() + budget_seconds, False

    def call(self, method, path, *, bearer, body=None):
        remaining = self._deadline - self._clock()
        if not self._revoking and remaining <= 0:
            raise PrivateSourceError("Source inspection exceeded its bounded read time.")
        self.request_timeout = 10 if self._revoking else min(10, remaining)
        return super().call(method, path, bearer=bearer, body=body)

    def revoke_token(self, installation_token):
        self._revoking = True
        try:
            return super().revoke_token(installation_token)
        finally:
            self._revoking = False


def _current(client, token: str, binding: dict[str, str]) -> tuple[str, str, str]:
    repository = client.call("GET", f"/repositories/{binding['provider_repository_id']}", bearer=token)
    if (not isinstance(repository, dict) or type(repository.get("id")) is not int or str(repository["id"]) != binding["provider_repository_id"]
            or repository.get("full_name") != binding["full_name"] or repository.get("visibility") not in {"public", "private", "internal"}
            or repository.get("private") is not (repository["visibility"] != "public") or repository.get("archived") is not False
            or repository.get("disabled") is True or repository.get("default_branch") != "main"):
        raise PrivateSourceError("The selected source identity or qualified main branch changed.")
    commit = client.call("GET", f"/repos/{binding['full_name']}/commits/main", bearer=token)
    tree = commit.get("commit", {}).get("tree", {}) if isinstance(commit, dict) else {}
    if not isinstance(commit, dict) or not SHA.fullmatch(str(commit.get("sha", ""))) or not SHA.fullmatch(str(tree.get("sha", ""))):
        raise PrivateSourceError("The provider did not return an exact current commit and tree.")
    return commit["sha"], tree["sha"], repository["visibility"]


def _files(client, token: str, binding: dict[str, str], tree_sha: str, paths: list[str]) -> dict[str, str | None]:
    tree = client.call("GET", f"/repos/{binding['full_name']}/git/trees/{tree_sha}?recursive=1", bearer=token)
    if (not isinstance(tree, dict) or tree.get("sha") != tree_sha or tree.get("truncated") is not False or not isinstance(tree.get("tree"), list)
            or len(tree["tree"]) > 8192 or len(json.dumps(tree, ensure_ascii=False).encode()) > 1048576):
        raise PrivateSourceError("The complete bounded source tree is unavailable.")
    entries = {}
    for entry in tree["tree"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or entry["path"] in entries:
            raise PrivateSourceError("The source tree contains ambiguous paths.")
        entries[entry["path"]] = entry
    observed = {}
    for path in paths:
        entry = entries.get(path)
        parts = path.split("/")
        for index in range(1, len(parts)):
            parent = entries.get("/".join(parts[:index]))
            if parent is not None and (parent.get("type") != "tree" or parent.get("mode") != "040000") or entry is not None and parent is None:
                raise PrivateSourceError("A source control parent is not a regular Git directory.")
        if entry is None:
            observed[path] = None
            continue
        size = entry.get("size")
        if (entry.get("type") != "blob" or entry.get("mode") != "100644" or not SHA.fullmatch(str(entry.get("sha", "")))
                or type(size) is not int or not 0 <= size <= MAX_FILE_BYTES):
            raise PrivateSourceError("Source controls must be bounded regular UTF-8 files.")
        blob = client.call("GET", f"/repos/{binding['full_name']}/git/blobs/{entry['sha']}", bearer=token)
        if (not isinstance(blob, dict) or blob.get("sha") != entry["sha"] or blob.get("encoding") != "base64" or blob.get("size") != size
                or not isinstance(blob.get("content"), str) or len(blob["content"]) > 131072):
            raise PrivateSourceError("The provider blob does not match the committed source tree.")
        try:
            raw = base64.b64decode(blob["content"].replace("\n", "").replace("\r", ""), validate=True)
            if len(raw) != size or hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() != entry["sha"]:
                raise PrivateSourceError("Source bytes do not match their Git content identity.")
            observed[path] = raw.decode("utf-8", errors="strict")
        except (ValueError, UnicodeError):
            raise PrivateSourceError("Source controls contain invalid encoding.") from None
    return observed


def inspect_owner_controls(value: Any, *, snapshot_reader: Callable[[], InstanceSourceSnapshot | None], args,
                           client: InspectionClient | None = None) -> dict[str, Any]:
    value = validate_input(value)
    snapshot = snapshot_reader()
    if not isinstance(snapshot, InstanceSourceSnapshot):
        raise PrivateSourceError("Private inspection requires its actual internal source authority.")
    checked = validated_snapshot({"schema_version": 1, "canonical_authority": snapshot.source_authority.get("canonical_authority"),
        "source_authority": snapshot.source_authority}, instance_id=snapshot.instance_id, owner=value["owner_repo"], operation=value["operation"], policy_ref=snapshot.policy_ref)
    if checked is None or snapshot.owner_repo != value["owner_repo"] or snapshot.operation != value["operation"] or digest(authority_ref(snapshot)) != digest(value["authority_ref"]):
        raise PrivateSourceError("Current source authority changed after preparation.")
    binding = snapshot.source_authority["provider_repository"]
    with repository_read_token(snapshot, args, client=client) as (selected_client, token):
        commit, tree, visibility = _current(selected_client, token.token, binding)
        observed = _files(selected_client, token.token, binding, tree, value["paths"])
        if _current(selected_client, token.token, binding) != (commit, tree, visibility):
            raise PrivateSourceError("The selected source main changed during inspection.")
        after = snapshot_reader()
        if (not isinstance(after, InstanceSourceSnapshot) or after.instance_id != snapshot.instance_id or after.owner_repo != snapshot.owner_repo or after.operation != snapshot.operation
                or digest(authority_ref(after)) != digest(authority_ref(snapshot)) or digest(after.source_authority) != digest(snapshot.source_authority)):
            raise PrivateSourceError("Current source authority changed during inspection.")
        result = {"schema_version": 1, "read_scope": "trusted-owner-controls", "owner_repo": value["owner_repo"], "operation": value["operation"],
            "read_credential_issued": True, "read_credential_revoked": True,
            "authority_ref": authority_ref(snapshot), "provider_repository": binding, "fetched_base": commit,
            "observed_files": observed, "visibility": visibility, "default_branch": "main"}
        if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_RESULT_BYTES:
            raise PrivateSourceError("Source inspection exceeds its complete response bound.")
        return result
