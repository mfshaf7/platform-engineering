"""Owner release data follows GitHub without changing the reviewed runtime code.

Only the existing OpenClaw release records may differ from the accepted Platform
revision. All other Git leaves (including workflows/scripts/policy) must match.
The private snapshot is a bounded derived read cache, never source authority.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import threading
import time
from urllib.parse import quote
import yaml

import console_release_identity as identity
from console_dev_integration_profiles import committed_document, ProfileReadError, MAX_BYTES

MUTABLE_RECORDS = frozenset({
    "environments/stage/release-candidate.yaml", "environments/stage/versions.yaml",
    "environments/stage/verification.yaml", "environments/stage/promotion-readiness.yaml",
    "environments/stage/argocd/kustomization.yaml",
    "environments/stage/values/openclaw-gateway.yaml", "environments/stage/values/platform-version.yaml",
    "environments/prod/openclaw-lifecycle.yaml", "environments/prod/versions.yaml",
    "environments/prod/verification.yaml", "environments/prod/argocd/kustomization.yaml",
    "environments/prod/argocd/openclaw-prod-lifecycle-configmap.yaml",
    "environments/prod/values/openclaw-gateway.yaml", "environments/prod/values/platform-version.yaml",
})
READ_PATHS = frozenset({
    "environments/stage/release-candidate.yaml", "environments/stage/verification.yaml",
    "environments/stage/promotion-readiness.yaml", "environments/prod/verification.yaml",
    "environments/prod/openclaw-lifecycle.yaml", "products/openclaw/verification-catalog.yaml",
    ".github/workflows/confirm-stage-promotion-readiness.yaml",
    ".github/workflows/promote-environment.yaml", ".github/workflows/manage-prod-environment.yaml",
})
SHA = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class SourceView:
    reader: object
    posture: str
    observed: datetime
    reason: str | None = None


class SourceChanged(ProfileReadError):
    pass


class ReleaseSource:
    def __init__(self, policy, fetch, *, local_reader=committed_document, base_loader=None, monotonic=time.monotonic):
        self.policy, self.fetch, self.local_reader = policy, fetch, local_reader
        self.revision = policy["security"]["platform_revision"]
        if not isinstance(self.revision, str) or not SHA.fullmatch(self.revision):
            raise ProfileReadError("The accepted release code revision is unavailable.")
        # The accepted executing checkout holds the immutable code objects;
        # release data never requires advancing a primary workspace checkout.
        self.root = Path(__file__).resolve().parents[3]
        self.cache_path = Path(policy["runtime_state_root"]) / "governed-release/source-snapshot.json"
        self.base_loader = base_loader or self._git_entries
        self.monotonic, self.lock = monotonic, threading.RLock()
        self.base = None
        self.frames = OrderedDict()
        self.proofs = OrderedDict()
        self.pending_proofs = OrderedDict()
        self.last = self._load()
        if self.last:
            self.frames[self.last["source_revision"]] = dict(self.last["documents"])
        self.tip, self.tip_until, self.backoff_until = None, 0, 0
        self.confirmed_at = None

    def _git_entries(self):
        result = subprocess.run(["git", "-C", str(self.root), "ls-tree", "-rz", self.revision], capture_output=True, timeout=10)
        if result.returncode or len(result.stdout) > 2_000_000:
            raise ProfileReadError("The accepted owner code tree is unavailable.")
        entries = {}
        for row in result.stdout.split(b"\0"):
            if row:
                header, path = row.split(b"\t", 1)
                mode, kind, sha = header.decode().split()
                entries[path.decode()] = (mode, kind, sha)
        return entries

    def _load(self):
        try:
            info = self.cache_path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 4_000_000:
                return None
            value = json.loads(self.cache_path.read_text())
            if not isinstance(value, dict) or set(value) != {"schema_version", "code_revision", "source_revision", "observed_at", "documents", "content_digest"}:
                return None
            claims = {key: item for key, item in value.items() if key != "content_digest"}
            if value["schema_version"] != 1 or value["code_revision"] != self.revision or identity.digest(claims) != value["content_digest"] or not SHA.fullmatch(value["source_revision"]):
                return None
            documents = value["documents"]
            if not isinstance(documents, dict) or set(documents) != READ_PATHS or any(not isinstance(raw, str) or len(raw.encode()) > MAX_BYTES for raw in documents.values()):
                return None
            datetime.fromisoformat(value["observed_at"])
            return value
        except (OSError, ValueError, TypeError, KeyError):
            return None

    def _view(self, frame, posture, reason=None):
        def reader(workspace, owner, relative):
            if owner != "platform-engineering":
                return self.local_reader(workspace, owner, relative)
            if relative not in READ_PATHS:
                raise ProfileReadError("This release source path is not admitted.")
            value = yaml.safe_load(frame["documents"][relative])
            if not isinstance(value, dict):
                raise ProfileReadError("The owner release record is invalid.")
            return value, frame["source_revision"]
        observed = self.confirmed_at if posture == "owner-main" else datetime.fromisoformat(frame["observed_at"])
        return SourceView(reader, posture, observed, reason)

    def _retained(self, reason):
        if self.last:
            return self._view(self.last, "retained-owner-main", reason)
        # A reviewed local snapshot stays inspectable without an App. It must
        # not be labelled current owner main or offer native execution.
        def reader(workspace, owner, relative):
            if owner != "platform-engineering":
                return self.local_reader(workspace, owner, relative)
            if relative not in READ_PATHS:
                raise ProfileReadError("This release source path is not admitted.")
            result = subprocess.run(["git", "-C", str(self.root), "show", self.revision + ":" + relative], capture_output=True, timeout=10)
            if result.returncode or len(result.stdout) > MAX_BYTES:
                raise ProfileReadError("The accepted owner record is unavailable.")
            value = yaml.safe_load(result.stdout)
            if not isinstance(value, dict):
                raise ProfileReadError("The accepted owner record is invalid.")
            return value, self.revision
        return SourceView(reader, "accepted-snapshot", datetime.now(timezone.utc), reason)

    def _call(self, route):
        if self.monotonic() > self.deadline:
            raise ProfileReadError("The bounded owner-source refresh has not completed.")
        return self.fetch("GET", route)

    def _proof(self, head):
        if head in self.proofs:
            return self.proofs[head]
        progress = self.pending_proofs.setdefault(head, {})
        self.pending_proofs.move_to_end(head)
        while len(self.pending_proofs) > 4:
            self.pending_proofs.popitem(last=False)
        if not progress.get("repository_verified"):
            repo = self._call("")
            if repo.get("id") != 1195328534 or repo.get("full_name") != "mfshaf7/platform-engineering":
                raise SourceChanged("The owner repository identity changed.")
            progress["repository_verified"] = True
        if "tree_sha" not in progress:
            commit = self._call("/git/commits/" + head)
            tree_sha = commit.get("tree", {}).get("sha")
            if commit.get("sha") != head or not isinstance(tree_sha, str) or not SHA.fullmatch(tree_sha):
                raise ProfileReadError("The owner source tree is unavailable.")
            progress["tree_sha"] = tree_sha
        if "entries" not in progress:
            tree_sha = progress["tree_sha"]
            tree = self._call("/git/trees/" + tree_sha + "?recursive=1")
            rows = tree.get("tree")
            if tree.get("sha") != tree_sha or tree.get("truncated") is not False or not isinstance(rows, list) or len(rows) > 20_000:
                raise ProfileReadError("The owner source tree exceeds its complete bounded proof.")
            entries = {}
            for row in rows:
                path, mode, kind, sha = (row.get(key) for key in ("path", "mode", "type", "sha"))
                if not isinstance(path, str) or path in entries or not isinstance(sha, str) or not SHA.fullmatch(sha) or kind not in {"blob", "commit", "tree"}:
                    raise ProfileReadError("The owner source tree is invalid.")
                if kind != "tree":
                    entries[path] = (mode, kind, sha)
            progress["entries"] = entries
        entries = progress["entries"]
        if self.base is None:
            self.base = self.base_loader()
        if ({key: value for key, value in entries.items() if key not in MUTABLE_RECORDS}
                != {key: value for key, value in self.base.items() if key not in MUTABLE_RECORDS}):
            raise SourceChanged("Owner workflow code changed; updated source acceptance is required before another native request.")
        if any(entries.get(path, ())[:2] != ("100644", "blob") for path in MUTABLE_RECORDS & entries.keys()):
            raise SourceChanged("Owner release records must remain regular data files.")
        if head != self.revision:
            ancestry = self._call("/compare/" + self.revision + "..." + head + "?per_page=1")
            if ancestry.get("merge_base_commit", {}).get("sha") != self.revision or ancestry.get("status") != "ahead":
                raise SourceChanged("Owner main is outside the accepted source lineage.")
        self.proofs[head] = {path: entries[path][2] for path in READ_PATHS if path in entries}
        self.pending_proofs.pop(head, None)
        while len(self.proofs) > 4:
            self.proofs.popitem(last=False)
        return self.proofs[head]

    def invalidate(self):
        with self.lock:
            self.tip_until = 0

    def view(self, *, force=False, require_current=False):
        with self.lock:
            reason = "Native release access is not commissioned; this is a source snapshot."
            changed = False
            if identity.selection_accepted(self.policy):
                try:
                    if self.monotonic() < self.backoff_until:
                        raise ProfileReadError("Owner source is temporarily unavailable.")
                    self.deadline = self.monotonic() + 6
                    if force or self.monotonic() >= self.tip_until:
                        ref = self._call("/git/ref/heads/main")
                        head = ref.get("object", {}).get("sha")
                        if not isinstance(head, str) or not SHA.fullmatch(head):
                            raise ProfileReadError("Owner main is unavailable.")
                        self.tip, self.tip_until = head, self.monotonic() + 5
                        self.confirmed_at = datetime.now(timezone.utc)
                    head = self.tip
                    proof = self._proof(head)
                    documents = self.frames.setdefault(head, {})
                    for path in sorted(READ_PATHS):
                        if path in documents:
                            continue
                        # Immutable blob identity allows unchanged records/code
                        # to be reused across releases and process restarts.
                        for previous in list(self.frames.values()):
                            raw = previous.get(path)
                            if raw is not None:
                                encoded_raw = raw.encode()
                                sha = hashlib.sha1(b"blob " + str(len(encoded_raw)).encode() + b"\0" + encoded_raw).hexdigest()
                                if sha == proof.get(path):
                                    documents[path] = raw
                                    break
                        if path in documents:
                            continue
                        value = self._call("/contents/" + path + "?ref=" + quote(head, safe=""))
                        encoded = value.get("content")
                        if value.get("type") != "file" or value.get("encoding") != "base64" or not isinstance(encoded, str) or len(encoded) > 400_000:
                            raise ProfileReadError("The owner source blob is invalid.")
                        raw = base64.b64decode("".join(encoded.split()), validate=True)
                        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
                        if len(raw) > MAX_BYTES or blob != proof.get(path) or not isinstance(yaml.safe_load(raw), dict):
                            raise ProfileReadError("The owner source blob differs from its admitted tree.")
                        documents[path] = raw.decode()
                    frame = {"schema_version": 1, "code_revision": self.revision, "source_revision": head, "observed_at": self.confirmed_at.isoformat(), "documents": dict(documents)}
                    frame["content_digest"] = identity.digest(frame)
                    if self.last is None or self.last["source_revision"] != head:
                        identity.atomic_json(self.cache_path, frame)
                    self.last = frame
                    while len(self.frames) > 4:
                        self.frames.popitem(last=False)
                    return self._view(frame, "owner-main")
                except SourceChanged as exc:
                    reason = str(exc)
                    changed = True
                except (identity.IdentityError, OSError, ValueError, KeyError, TypeError, yaml.YAMLError, subprocess.SubprocessError):
                    reason = "Current owner source is unavailable; retained evidence does not enable a new native request."
                self.backoff_until, self.tip_until = self.monotonic() + 3, 0
            if require_current:
                raise (SourceChanged if changed else ProfileReadError)(reason)
            return self._retained(reason)
