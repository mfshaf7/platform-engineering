"""Maintain an explicitly selected account metadata reader in the existing timer.

The existing identity producer writes the private delivery receipt. Its exact
scope is the selection; absence never enables a reader or selects an account.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import repository_provider_identity as identity
import repository_provider_account as account

SECRET = "operator-orchestration-service-repository-provider"
TOKEN_ENV = "OOS_REPOSITORY_PROVIDER_INSTALLATION_TOKEN"
ACCOUNT_ENV = account.ACCOUNT_ENV
VERSION_ANNOTATION = "workspace-governance/repository-reader-credential-version"


def selection_path(state_root):
    return Path(state_root) / "private/repository-reader-delivery.json"


def private_selection(path):
    if path.is_symlink():
        raise identity.IdentityError("repository reader selection must be a private regular file")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077 or info.st_size > 32768:
        raise identity.IdentityError("repository reader selection permissions or size are invalid")
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise identity.IdentityError("repository reader selection must be a JSON object")
    return value, "sha256:" + hashlib.sha256(raw).hexdigest()


class Reader:
    def __init__(self, *, repo_root, workspace_root, state_root, session_manifest, run, private_key):
        self.repo_root, self.workspace_root = Path(repo_root), Path(workspace_root)
        self.path = selection_path(state_root)
        self.session_manifest, self.run, self.private_key = Path(session_manifest), run, private_key
        self.contract_path = self.repo_root / "security/repository-provider-identity.yaml"
        self.previous_token = None

    def selection(self):
        definition = account.contract(self.contract_path)
        value, self.selection_digest = private_selection(self.path)
        if value.get("outcome") == "revoked":
            return None
        try:
            org = account.scope(value["scope"]["account"])
            target = identity.verify_dev_integration_cluster("k3s kubectl", identity.load_dev_integration_target(
                self.session_manifest, self.workspace_root, definition, require_running=True))
            if (value["scope"] != org or value.get("action") != "deliver"
                    or value.get("artifact_type") != "repository-provider-identity-receipt"
                    or value.get("identity_id") != definition.identity_id
                    or value.get("contract_digest") != definition.contract_digest
                    or value.get("outcome") not in ("prepared", "delivered")
                    or value.get("permissions") != {"metadata": "read"}
                    or value.get("repository_selection") != "all"
                    or value.get("secret_values_embedded") is not False
                    or type(value.get("app_id")) is not int or value["app_id"] <= 0
                    or type(value.get("installation_id")) is not int or value["installation_id"] <= 0
                    or value["runtime_target"]["namespace"] != target.namespace
                    or value["runtime_target"]["profile_id"] != target.profile_id
                    or value.get("credential_binding_digest") != account.binding_digest(
                        definition, value["app_id"], value["installation_id"], org["account"])):
                raise ValueError("selection")
        except (KeyError, TypeError, ValueError):
            raise identity.IdentityError("repository reader selection does not match its approved scope") from None
        return definition, value, target

    def secret(self, value, target, *, allow_missing=False):
        observed = self.run(["k3s", "kubectl", "-n", target.namespace, "get", "secret", SECRET, "--ignore-not-found", "-o", "json"], check=False)
        if getattr(observed, "returncode", 0):
            raise identity.IdentityError("repository reader Secret source is unavailable")
        if not observed.stdout.strip() and allow_missing:
            return None
        try:
            secret = json.loads(observed.stdout)
            metadata, data = secret["metadata"], secret["data"]
            annotations = metadata["annotations"]
            token = base64.b64decode(data[TOKEN_ENV], validate=True).decode()
            if (metadata["name"] != SECRET or metadata["namespace"] != target.namespace
                    or metadata["labels"]["app.kubernetes.io/managed-by"] != "platform-engineering"
                    or annotations["workspace-governance/dev-integration-profile"] != target.profile_id
                    or annotations["workspace-governance/credential-binding-digest"] != value["credential_binding_digest"]
                    or json.loads(annotations[account.SCOPE_ANNOTATION]) != value["scope"]
                    or annotations["workspace-governance/token-expires-at"] != value["token_expires_at"]
                    or base64.b64decode(data[ACCOUNT_ENV], validate=True).decode() != value["scope"]["account"]
                    or not token.startswith("ghs_")
                    or "sha256:" + hashlib.sha256(token.encode()).hexdigest() != value["token_digest"]
                    or not isinstance(metadata.get("resourceVersion"), str)):
                raise ValueError("binding")
        except (KeyError, ValueError, TypeError):
            raise identity.IdentityError("repository reader Secret does not match its protected selection") from None
        return secret

    def maintain(self, *, force=False, now=None):
        if not self.path.exists() and not self.path.is_symlink():
            return {"state": "not-selected"}
        selected = self.selection()
        if selected is None:
            return {"state": "revoked"}
        definition, value, target = selected
        # Prepared receipts are accepted only after actual Secret matching. A
        # failed/uncertain projection cannot silently become a current binding.
        secret = self.secret(value, target, allow_missing=True)
        current_time = now or datetime.now(timezone.utc)
        remaining = (identity.parse_timestamp(value["token_expires_at"]) - current_time).total_seconds()
        if remaining > definition.maximum_token_lifetime_seconds + 60:
            raise identity.IdentityError("repository reader lifetime exceeds the contract")
        refreshed = force or secret is None or remaining < 1200
        if refreshed:
            previous = base64.b64decode(secret["data"][TOKEN_ENV], validate=True).decode() if secret else None
            key = self.private_key({"address": "http://127.0.0.1:8200", "namespace": "vault", "pod": "vault-0",
                "secret_path": "kv/components/operator-orchestration-service/dev-integration/repository-provider",
                "secret_property": "privateKey"})
            try:
                self.run([sys.executable, str(self.repo_root / "scripts/repository_provider_identity.py"),
                    "--contract", str(self.contract_path), "deliver", "--app-id", str(value["app_id"]),
                    "--installation-id", str(value["installation_id"]), "--account", value["scope"]["account"],
                    "--private-key-file", str(key), "--session-manifest", str(self.session_manifest),
                    "--workspace-root", str(self.workspace_root), "--receipt", str(self.path),
                    "--expected-selection-digest", self.selection_digest])
            finally:
                key.unlink(missing_ok=True)
            selected = self.selection()
            if selected is None:
                self.previous_token = previous
                self.retire_previous(definition)
                return {"state": "revoked"}
            definition, value, target = selected
            secret = self.secret(value, target)
            if previous and base64.b64decode(secret["data"][TOKEN_ENV], validate=True).decode() != previous:
                self.previous_token = previous
        if value["outcome"] == "prepared":
            value = {**value, "outcome": "delivered"}
            identity.write_receipt(self.path, value)
        return {"state": "renewed" if refreshed else "current", "expires_at": value["token_expires_at"],
            "binding": {"account": value["scope"]["account"],
                "version": secret["metadata"]["resourceVersion"]}}

    def probe(self):
        selected = self.selection()
        if selected is None:
            self.retire_previous(account.contract(self.contract_path))
            return {"state": "revoked"}
        definition, value, target = selected
        self.secret(value, target)
        # No token or key leaves the pod. Compare against the delivered token's
        # fingerprint, and enforce the configured account in the consumer.
        program = ("const c=require('node:crypto');console.log(JSON.stringify({consumed:"
            "process.env.OOS_REPOSITORY_CUSTODY_ENABLED==='true'&&"
            f"process.env.{ACCOUNT_ENV}==={json.dumps(value['scope']['account'])}&&"
            f"'sha256:'+c.createHash('sha256').update(process.env.{TOKEN_ENV}??'').digest('hex')==={json.dumps(value['token_digest'])}"
            "}));")
        result = self.run(["k3s", "kubectl", "-n", target.namespace, "exec", "deployment/operator-orchestration-service",
            "-c", "operator-orchestration-service", "--", "node", "-e", program])
        if json.loads(result.stdout) != {"consumed": True}:
            raise identity.IdentityError("repository reader delivery has not been consumed")
        self.retire_previous(definition)
        return {"state": "consumed", "account": value["scope"]["account"], "expires_at": value["token_expires_at"]}

    def retire_previous(self, definition):
        if self.previous_token:
            try:
                identity.ProviderClient(definition.api_base_url).revoke_token(self.previous_token)
            except identity.ProviderHttpError as exc:
                if exc.status_code not in (401, 404):
                    raise
            self.previous_token = None
