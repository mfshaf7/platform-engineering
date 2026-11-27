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
from agent_source_instance import InstanceSourceSnapshot, validated_snapshot, digest, strict_object, invalid_constant
from repository_provider_identity import ProviderHttpError

SHA = re.compile(r"[0-9a-f]{40}")
MAX_FILE_BYTES = 65536
MAX_RESULT_BYTES = 524288


class PrivateSourceError(RuntimeError):
    """No private file bytes or credentials may appear in this exception."""


def authority_ref(snapshot: InstanceSourceSnapshot) -> dict[str, Any]:
    proof = snapshot.source_authority
    return {"canonical_authority": proof["canonical_authority"], "record_ref": proof["record_ref"], "policy_ref": proof["policy_ref"]}


@contextmanager
def repository_read_token(binding: dict[str, str], args, *, client=None):
    """Existing Source App custody, reduced for one finite read operation."""
    base = identity.load_contract(args.contract)
    repository = identity.Repository(binding["full_name"], int(binding["provider_repository_id"]))
    selected = client or InspectionClient(base.api_base_url)
    try:
        with identity.repository_read_token(base, repository, args, client=selected) as lease:
            yield lease
    except ProviderHttpError as error:
        if error.retry_at:
            raise
        raise PrivateSourceError("The protected source connection could not complete its read operation.") from None
    except identity.RepositoryReadRevocationError as error:
        raise PrivateSourceError(str(error)) from None
    except identity.RepositoryReadConnectionError:
        raise
    except identity.IdentityError:
        raise PrivateSourceError("The protected source connection could not complete its read operation.") from None


def validate_input(value: Any) -> dict[str, Any]:
    if (not isinstance(value, dict) or set(value) != {"schema_version", "owner_repo", "operation", "paths", "authority_ref"}
            or type(value["schema_version"]) is not int or value["schema_version"] != 1
            or not isinstance(value["owner_repo"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,185}", value["owner_repo"])
            or not isinstance(value["operation"], str) or value["operation"] not in {"bootstrap", "configure-verification"}
            or not isinstance(value["paths"], list) or not value["paths"] or len(value["paths"]) > len(PATHS)
            or any(not isinstance(path, str) or path not in PATHS for path in value["paths"])
            or value["paths"] != sorted(set(value["paths"]))
            or not isinstance(value["authority_ref"], dict)):
        raise PrivateSourceError("Select the exact current owner and finite trusted control files.")
    reference = value["authority_ref"]
    canonical = reference.get("canonical_authority")
    if not isinstance(canonical, dict):
        raise PrivateSourceError("Current source authority is required.")
    if canonical.get("kind") == "legacy-git":
        if (set(reference) != {"canonical_authority", "provider_repository"} or
                set(canonical) != {"kind", "repo", "revision"} or canonical["repo"] != "workspace-governance"
                or not SHA.fullmatch(str(canonical["revision"]))):
            raise PrivateSourceError("A current retained source record is required.")
    elif set(reference) != {"canonical_authority", "record_ref", "policy_ref"}:
        raise PrivateSourceError("Current internal source authority is required.")
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
    prefix = f"/repos/{binding['full_name']}/git"
    directories = {}

    def read_directory(sha: str):
        if sha not in directories:
            tree = client.call("GET", f"{prefix}/trees/{sha}", bearer=token)
            if (not isinstance(tree, dict) or tree.get("sha") != sha or tree.get("truncated") is not False
                    or not isinstance(tree.get("tree"), list) or len(tree["tree"]) > 8192
                    or len(json.dumps(tree, ensure_ascii=False).encode()) > 1048576):
                raise PrivateSourceError("The exact source control directory is unavailable.")
            entries = {}
            for entry in tree["tree"]:
                name = entry.get("path") if isinstance(entry, dict) else None
                if not isinstance(name, str) or not name or "/" in name or name in entries:
                    raise PrivateSourceError("The source tree contains ambiguous paths.")
                entries[name] = entry
            directories[sha] = entries
        return directories[sha]

    observed = {}
    for path in paths:
        parts = path.split("/")
        entries = read_directory(tree_sha)
        for part in parts[:-1]:
            parent = entries.get(part)
            if parent is None:
                entries = {}
                break
            if parent.get("type") != "tree" or parent.get("mode") != "040000" or not SHA.fullmatch(str(parent.get("sha", ""))):
                raise PrivateSourceError("A source control parent is not a regular Git directory.")
            entries = read_directory(parent["sha"])
        entry = entries.get(parts[-1])
        if entry is None:
            observed[path] = None
            continue
        size = entry.get("size")
        if (entry.get("type") != "blob" or entry.get("mode") != "100644" or not SHA.fullmatch(str(entry.get("sha", "")))
                or type(size) is not int or not 0 <= size <= MAX_FILE_BYTES):
            raise PrivateSourceError("Source controls must be bounded regular UTF-8 files.")
        blob = client.call("GET", f"{prefix}/blobs/{entry['sha']}", bearer=token)
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


def inspect_owner_controls(value: Any, *, snapshot_reader: Callable[[], InstanceSourceSnapshot | None], args, legacy_reader=None,
                           client: InspectionClient | None = None) -> dict[str, Any]:
    value = validate_input(value)
    snapshot = snapshot_reader()
    reference = value["authority_ref"]
    if reference["canonical_authority"].get("kind") == "legacy-git":
        if snapshot is not None or legacy_reader is None or legacy_reader() != reference:
            raise PrivateSourceError("The selected retained source record is no longer eligible.")
        binding = reference["provider_repository"]

        def recheck() -> None:
            if snapshot_reader() is not None or legacy_reader() != reference:
                raise PrivateSourceError("The retained source record changed during inspection.")

        return _inspect_controls(value, binding, args, client=client, recheck=recheck, public_only=True)
    if not isinstance(snapshot, InstanceSourceSnapshot):
        raise PrivateSourceError("Private inspection requires its actual internal source authority.")
    checked = validated_snapshot({"schema_version": 1, "canonical_authority": snapshot.source_authority.get("canonical_authority"),
        "source_authority": snapshot.source_authority}, instance_id=snapshot.instance_id, owner=value["owner_repo"], operation=value["operation"], policy_ref=snapshot.policy_ref)
    if checked is None or snapshot.owner_repo != value["owner_repo"] or snapshot.operation != value["operation"] or digest(authority_ref(snapshot)) != digest(value["authority_ref"]):
        raise PrivateSourceError("Current source authority changed after preparation.")

    def recheck() -> None:
        if snapshot_reader() != snapshot:
            raise PrivateSourceError("Current source authority changed during inspection.")

    return _inspect_controls(value, snapshot.source_authority["provider_repository"], args, client=client, recheck=recheck)


def _inspect_controls(value, binding, args, *, client, recheck, public_only=False):
    with repository_read_token(binding, args, client=client) as (selected_client, token):
        commit, tree, visibility = _current(selected_client, token.token, binding)
        if public_only and visibility != "public":
            raise PrivateSourceError("Retained source records require verified public repository visibility.")
        observed = _files(selected_client, token.token, binding, tree, value["paths"])
        if _current(selected_client, token.token, binding) != (commit, tree, visibility):
            raise PrivateSourceError("The selected source main changed during inspection.")
        recheck()
        result = {"schema_version": 1, "read_scope": "trusted-owner-controls", "owner_repo": value["owner_repo"], "operation": value["operation"],
            "read_credential_issued": True, "read_credential_revoked": True,
            "authority_ref": value["authority_ref"], "provider_repository": binding, "fetched_base": commit,
            "observed_files": observed, "visibility": visibility, "default_branch": "main"}
        if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_RESULT_BYTES:
            raise PrivateSourceError("Source inspection exceeds its complete response bound.")
        return result


def inspect_prototype_import(value, *, authority_reader, args, client=None):
    fields = {"owner_repo", "provider_repository", "prototype_id", "merge_commit", "expected_main"}
    if (not isinstance(value, dict) or set(value) != fields
            or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", str(value["owner_repo"]))
            or not isinstance(value["prototype_id"], str)
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value["prototype_id"])
            or len(value["prototype_id"]) > 128 or not SHA.fullmatch(str(value["merge_commit"]))
            or (value["expected_main"] is not None and not SHA.fullmatch(str(value["expected_main"])))):
        raise PrivateSourceError("Select the exact reviewed Prototype merge and its admitted owner.")
    authority = authority_reader(value["owner_repo"])
    binding = authority["provider_repository"]
    if binding != value["provider_repository"]:
        raise PrivateSourceError("The accepted source owner changed before inspection.")
    with repository_read_token(binding, args, client=client) as (selected, credential):
        token = credential.token
        before = _current(selected, token, binding)
        if before[2] != "public":
            raise PrivateSourceError("Prototype transfer evidence requires a verified public destination.")
        if value["expected_main"] is not None:
            if before[0] != value["expected_main"] or authority_reader(value["owner_repo"]) != authority:
                raise PrivateSourceError("Canonical source changed during the transfer readback.")
            return {"current_main": before[0]}
        result = _prototype_import_files(value, binding, before[0], selected, token)
        if _current(selected, token, binding) != before or authority_reader(value["owner_repo"]) != authority:
            raise PrivateSourceError("Canonical source changed during the transfer readback.")
        result = {"current_main": before[0], **result}
        if len(json.dumps(result, ensure_ascii=False).encode()) > MAX_RESULT_BYTES:
            raise PrivateSourceError("Source inspection exceeds its complete response bound.")
        return result


def _prototype_import_files(value, binding, current_main, client, token):
    prefix = f"/repos/{binding['full_name']}"
    merge = value["merge_commit"]
    comparison = client.call("GET", f"{prefix}/compare/{merge}...{current_main}", bearer=token)
    if (not isinstance(comparison, dict) or comparison.get("status") not in {"ahead", "identical"}
            or (comparison.get("merge_base_commit") or {}).get("sha") != merge):
        raise PrivateSourceError("The accepted owner merge is not in current canonical main.")
    commit = client.call("GET", f"{prefix}/commits/{merge}", bearer=token)
    root = (commit.get("commit", {}).get("tree") or {}).get("sha") if isinstance(commit, dict) else None
    if not isinstance(root, str) or not SHA.fullmatch(root) or commit.get("sha") != merge:
        raise PrivateSourceError("The provider did not return the exact accepted commit tree.")
    tree = client.call("GET", f"{prefix}/git/trees/{root}?recursive=1", bearer=token)
    if (not isinstance(tree, dict) or tree.get("sha") != root or tree.get("truncated") is not False
            or not isinstance(tree.get("tree"), list) or len(tree["tree"]) > 8192):
        raise PrivateSourceError("Source import requires the complete bounded canonical tree.")
    entries = {}
    for entry in tree["tree"]:
        name = entry.get("path") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not name or name in entries:
            raise PrivateSourceError("The owner tree contains ambiguous source paths.")
        entries[name] = entry

    def file_entry(path, *, maximum, modes):
        if (not isinstance(path, str) or not 1 <= len(path) <= 512
                or not re.fullmatch(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*", path)):
            raise PrivateSourceError("The imported file path is invalid.")
        parts = path.split("/")
        for index, part in enumerate(parts):
            entry = entries.get("/".join(parts[:index + 1])) or {}
            if part.casefold() in {".", "..", ".git"}:
                raise PrivateSourceError("The imported file path is invalid.")
            if index < len(parts) - 1 and (entry.get("type"), entry.get("mode")) != ("tree", "040000"):
                raise PrivateSourceError("An imported file parent is not a regular Git directory.")
        if (entry.get("type") != "blob" or entry.get("mode") not in modes
                or not SHA.fullmatch(str(entry.get("sha", ""))) or type(entry.get("size")) is not int
                or not 0 <= entry["size"] <= maximum):
            raise PrivateSourceError("Imported source must be a bounded regular committed file.")
        return {"git_blob": entry["sha"], "git_mode": entry["mode"], "size": entry["size"]}

    metadata_path = f"records/prototype-source-imports/{value['prototype_id']}.json"
    metadata = file_entry(metadata_path, maximum=262144, modes={"100644"})
    blob_id = metadata["git_blob"]
    blob = client.call("GET", f"{prefix}/git/blobs/{blob_id}", bearer=token)
    if (not isinstance(blob, dict) or blob.get("sha") != blob_id or blob.get("encoding") != "base64"
            or not isinstance(blob.get("content"), str) or blob.get("size") != metadata["size"]
            or len(blob["content"]) > MAX_RESULT_BYTES):
        raise PrivateSourceError("Source-import metadata does not match the committed tree.")
    raw = base64.b64decode(blob["content"].replace("\n", "").replace("\r", ""), validate=True)
    if len(raw) != metadata["size"] or hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() != blob_id:
        raise PrivateSourceError("Source-import metadata bytes do not match their Git identity.")
    manifest_text = raw.decode("utf-8", errors="strict")
    manifest = json.loads(manifest_text, object_pairs_hook=strict_object, parse_constant=invalid_constant)
    mappings = manifest.get("file_mappings") if isinstance(manifest, dict) else None
    if (not isinstance(mappings, list) or not 1 <= len(mappings) <= 128
            or any(not isinstance(row, dict) or not isinstance(row.get("owner_path"), str) for row in mappings)):
        raise PrivateSourceError("Source import requires bounded file mappings.")
    paths = [row["owner_path"] for row in mappings]
    if len(set(paths)) != len(paths) or metadata_path in paths:
        raise PrivateSourceError("The imported file mappings are ambiguous.")
    return {"manifest_text": manifest_text, "files": {path: file_entry(path, maximum=4194304, modes={"100644", "100755"})
        for path in paths}}
