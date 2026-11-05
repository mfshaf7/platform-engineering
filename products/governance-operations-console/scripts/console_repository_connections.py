"""Renew explicitly connected GitHub accounts inside the existing lifecycle.

The selection is operator-private configuration, not a second repository
registry. Keys stay in existing purpose-specific Vault custody. Only verified
account metadata and short-lived purpose-specific tokens reach OOS.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import repository_provider_identity as identity
from console_repository_reader import private_selection

ENV = "OOS_REPOSITORY_CONNECTIONS_JSON"
SECRET = "operator-orchestration-service-repository-provisioning-provider"
PERMISSIONS = {
    "metadata": {"metadata": "read"},
    "provisioning": {"administration": "write", "contents": "read", "metadata": "read"},
    "lifecycle": {"administration": "write", "metadata": "read"},
}
VAULT_PATHS = {"metadata": "repository-provider", "provisioning": "repository-provisioning-provider", "lifecycle": "repository-lifecycle-provider"}


def selection(path):
    value, digest = private_selection(path)
    try:
        if set(value) != {"schema_version", "default_connection_id", "connections"} or value["schema_version"] != 1 or not isinstance(value["connections"], list) or len(value["connections"]) > 32:
            raise ValueError()
        seen = set()
        for item in value["connections"]:
            if (set(item) != {"account", "account_type", "grants"} or not isinstance(item["account"], str)
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", item["account"])
                    or item["account_type"] not in ("personal", "organization") or item["account"].lower() in seen
                    or not isinstance(item["grants"], dict) or not item["grants"] or set(item["grants"]) - PERMISSIONS.keys()):
                raise ValueError()
            seen.add(item["account"].lower())
            for role, grant in item["grants"].items():
                expected = {"app_id", "installation_id", *(["repository"] if role == "lifecycle" else []), *(["key_slot"] if "key_slot" in grant else [])}
                if set(grant) != expected or any(type(grant[key]) is not int or grant[key] <= 0 for key in ("app_id", "installation_id")):
                    raise ValueError()
                if "key_slot" in grant and (not isinstance(grant["key_slot"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", grant["key_slot"])):
                    raise ValueError()
                if role == "lifecycle":
                    repo = grant["repository"]
                    if (not isinstance(repo, dict) or set(repo) != {"name", "provider_repository_id"}
                            or not isinstance(repo["name"], str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", repo["name"])
                            or not isinstance(repo["provider_repository_id"], str) or not re.fullmatch(r"[1-9][0-9]*", repo["provider_repository_id"])):
                        raise ValueError()
        if value["default_connection_id"] not in [None, *(f"github:{name}" for name in seen)]:
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise identity.IdentityError("GitHub connection selection is invalid") from None
    return value, digest


def issue(item, role, *, client, key):
    grant = item["grants"][role]
    jwt = identity.create_app_jwt(grant["app_id"], key)
    app = client.authenticated_app(jwt)
    permissions = PERMISSIONS[role]
    if app.get("id") != grant["app_id"] or app.get("permissions") != permissions or app.get("events") not in (None, []):
        raise identity.IdentityError("GitHub App does not match its purpose-specific grant")
    installed = client.installation(grant["installation_id"], jwt)
    account = installed.get("account") or {}
    if (installed.get("id") != grant["installation_id"] or installed.get("app_id") != grant["app_id"]
            or installed.get("suspended_at") is not None or installed.get("permissions") != permissions
            or installed.get("events") not in (None, [])
            or installed.get("repository_selection") not in (("all",) if role == "metadata" else ("all", "selected"))
            or str(account.get("login", "")).lower() != item["account"].lower()
            or account.get("type") != ("User" if item["account_type"] == "personal" else "Organization")
            or type(account.get("id")) is not int or account["id"] <= 0):
        raise identity.IdentityError("GitHub installation does not match the selected account and access scope")
    binding = {"provider": "github", "account_id": str(account["id"]), "account": item["account"].lower(),
        "account_type": item["account_type"], "role": role, **grant, "permissions": permissions}
    digest = "sha256:" + hashlib.sha256(json.dumps(binding, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    repository = grant.get("repository")
    token = client.issue_token(grant["installation_id"], jwt, [repository["name"]] if repository else None, permissions)
    remaining = (identity.parse_timestamp(token.expires_at) - datetime.now(timezone.utc)).total_seconds()
    exact_repository = bool(repository and len(token.repositories) == 1 and
        str(token.repositories[0].get("id")) == repository["provider_repository_id"] and
        token.repositories[0].get("full_name", "").lower() == f"{item['account']}/{repository['name']}".lower())
    if (token.permissions != permissions or not 300 <= remaining <= 3660 or
            (not exact_repository if repository else token.repository_selection != installed.get("repository_selection"))):
        client.revoke_token(token.token)
        raise identity.IdentityError("GitHub connection token exceeded its approved grant or lifetime")
    return str(account["id"]), {"token": token.token, "expires_at": token.expires_at,
        **({"repository_id": repository["provider_repository_id"]} if repository else {}),
        "installation_id": str(grant["installation_id"]), "credential_binding_ref": {
            "uri": f"platform-engineering://github-connections/{item['account'].lower()}/{role}", "digest": digest}}


class Connections:
    def __init__(self, *, state_root, namespace, run, private_key, client_factory=identity.ProviderClient):
        self.path = Path(state_root) / "private/repository-connections.json"
        self.state = Path(state_root) / "private/repository-connections-delivery.json"
        self.namespace, self.run, self.private_key, self.client_factory = namespace, run, private_key, client_factory
        self.previous = []

    def maintain(self, *, force=False):
        if not self.path.exists() and not self.path.is_symlink():
            return None
        selected, selection_digest = selection(self.path)
        observed = self.run(["k3s", "kubectl", "-n", self.namespace, "get", "secret", SECRET, "-o", "json"])
        secret = json.loads(observed.stdout)
        previous = base64.b64decode(secret.get("data", {}).get(ENV, "")).decode()
        retained = None
        if self.state.exists():
            retained, _ = private_selection(self.state)
        now = datetime.now(timezone.utc)
        current = bool(not force and retained and not retained.get("unavailable") and retained.get("selection_digest") == selection_digest and
            retained.get("payload_digest") == "sha256:" + hashlib.sha256(previous.encode()).hexdigest() and
            all((identity.parse_timestamp(time) - now).total_seconds() >= 1200 for time in retained.get("expires_at", [])))
        if not current:
            payload = {"schema_version": 1, "default_connection_id": selected["default_connection_id"], "connections": []}
            issued = []
            unavailable = []
            try:
                for item in selected["connections"]:
                    entry = {"id": f"github:{item['account'].lower()}", "account": item["account"], "account_type": item["account_type"], "grants": {}}
                    for role in item["grants"]:
                        key = None
                        try:
                            slot = item["grants"][role].get("key_slot")
                            suffix = f"/connections/{slot}" if slot else ""
                            key = self.private_key({"address": "http://127.0.0.1:8200", "namespace": "vault", "pod": "vault-0",
                                "secret_path": f"kv/components/operator-orchestration-service/dev-integration/{VAULT_PATHS[role]}{suffix}", "secret_property": "privateKey"})
                            client = self.client_factory("https://api.github.com")
                            account_id, grant = issue(item, role, client=client, key=key)
                        except (identity.IdentityError, OSError, RuntimeError):
                            unavailable.append({"account": item["account"], "role": role})
                            continue
                        finally:
                            if key is not None:
                                key.unlink(missing_ok=True)
                        issued.append((client, grant["token"]))
                        if entry.get("account_id", account_id) != account_id:
                            raise identity.IdentityError("GitHub connection account identity changed during verification")
                        entry["account_id"] = account_id
                        entry["grants"][role] = grant
                    if entry["grants"]:
                        payload["connections"].append(entry)
                if payload["default_connection_id"] not in [item["id"] for item in payload["connections"]]:
                    payload["default_connection_id"] = None
                if selection(self.path)[1] != selection_digest:
                    raise identity.IdentityError("GitHub selection changed during credential delivery")
            except Exception:
                for client, token in issued:
                    client.revoke_token(token)
                raise
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            # Resource-version CAS retains the existing producer and its fields.
            # An uncertain projection is reconciled on the next existing timer.
            try:
                self.run(["k3s", "kubectl", "-n", self.namespace, "patch", "secret", SECRET, "--type=merge", "--patch-file", "/dev/stdin"],
                    input_value=json.dumps({"metadata": {"resourceVersion": secret["metadata"]["resourceVersion"]}, "stringData": {ENV: raw}}))
            except Exception:
                raise identity.IdentityError("GitHub connection delivery was not confirmed; retry the original selection.") from None
            if previous:
                old = json.loads(previous)
                self.previous = [grant["token"] for item in old["connections"] for grant in item["grants"].values()]
            retained = {"schema_version": 1, "selection_digest": selection_digest,
                "unavailable": unavailable,
                "payload_digest": "sha256:" + hashlib.sha256(raw.encode()).hexdigest(),
                "expires_at": [grant["expires_at"] for item in payload["connections"] for grant in item["grants"].values()]}
            identity.write_receipt(self.state, retained)
        return {"digest": retained["payload_digest"], "state": "current" if current else "renewed"}

    def probe(self, digest):
        program = "const c=require('node:crypto');console.log(JSON.stringify({digest:'sha256:'+c.createHash('sha256').update(process.env." + ENV + "??'').digest('hex')}));"
        result = self.run(["k3s", "kubectl", "-n", self.namespace, "exec", "deployment/operator-orchestration-service",
            "-c", "operator-orchestration-service", "--", "node", "-e", program])
        if json.loads(result.stdout) != {"digest": digest}:
            raise identity.IdentityError("GitHub connections have not been consumed by the workflow service")
        for token in self.previous:
            try:
                self.client_factory("https://api.github.com").revoke_token(token)
            except identity.ProviderHttpError as error:
                if error.status_code not in (401, 404):
                    raise
        self.previous = []
