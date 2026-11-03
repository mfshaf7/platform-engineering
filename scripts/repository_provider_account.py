"""Account metadata scope for the existing repository-provider identity tool.

The account grant is deliberate, not a fallback from selected-repository
denial. Omit token repository filters so later repositories need no new setup.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import re
import stat

import yaml

import repository_provider_identity as identity

SCOPE_ANNOTATION = "workspace-governance/provider-scope"
ACCOUNT_ENV = "OOS_REPOSITORY_PROVIDER_ACCOUNT"
REVIEW = "docs/reviews/components/2026-11-03-account-repository-reader.md"


def contract(path):
    value = yaml.safe_load(path.read_text())
    if not isinstance(value, dict) or value.get("account_readback") != {
        "scope": "single-approved-account", "required_permissions": {"metadata": "read"},
        "installation_selection": "all", "covers_future_repositories": True,
        "security_review_ref": REVIEW,
    }:
        raise identity.IdentityError("account readback lacks its explicit metadata-only contract")
    return identity.load_contract(path)


def scope(account):
    if not isinstance(account, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,38}", account):
        raise identity.IdentityError("one GitHub account is required")
    return {"kind": "account-metadata", "account": account.casefold()}


def binding_digest(definition, app_id, installation_id, account):
    value = {"identity_id": definition.identity_id, "contract_digest": definition.contract_digest,
        "app_id": app_id, "installation_id": installation_id, "permissions": {"metadata": "read"},
        "provider_api_base_url": definition.api_base_url, "scope": scope(account)}
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def issued(args, definition):
    if args.app_id <= 0 or args.installation_id <= 0 or getattr(args, "repository", None):
        raise identity.IdentityError("account scope cannot be combined with repository selection")
    account = scope(args.account)["account"]
    client = identity.ProviderClient(args.provider_api_base_url or definition.api_base_url, sandbox=args.sandbox)
    jwt = identity.create_app_jwt(args.app_id, args.private_key_file)
    app = client.authenticated_app(jwt)
    if app.get("id") != args.app_id or app.get("permissions") != {"metadata": "read"} or app.get("events") not in (None, []):
        raise identity.IdentityError("the reader App must have Metadata: read only and no events")
    installation = client.installation(args.installation_id, jwt)
    native_account = installation.get("account") or {}
    if (installation.get("id") != args.installation_id or installation.get("app_id") != args.app_id
            or installation.get("suspended_at") is not None or installation.get("permissions") != {"metadata": "read"}
            or installation.get("events") not in (None, []) or native_account.get("type") not in ("User", "Organization")
            or str(native_account.get("login", "")).casefold() != account):
        raise identity.IdentityError("reader installation does not match the approved account and metadata-only grant")
    if installation.get("repository_selection") != "all":
        raise identity.IdentityError("account readback requires an explicit All repositories grant")
    # No repository list: the token follows the one approved account grant.
    token = client.issue_token(args.installation_id, jwt, None, {"metadata": "read"})
    try:
        remaining = (identity.parse_timestamp(token.expires_at) - datetime.now(timezone.utc)).total_seconds()
        if token.permissions != {"metadata": "read"} or token.repository_selection != "all" or not identity.MIN_REMAINING_TOKEN_SECONDS <= remaining <= definition.maximum_token_lifetime_seconds + 60:
            raise identity.IdentityError("account token permissions or lifetime exceed the contract")
    except Exception:
        client.revoke_token(token.token)
        raise
    return client, token


def receipt(args, definition, action, outcome, *, token=None, target=None):
    value = identity.receipt(definition, action=action, app_id=args.app_id,
        installation_id=args.installation_id, repositories=(), outcome=outcome,
        expires_at=token.expires_at if token else None, target=target)
    value.update(scope=scope(args.account), credential_binding_digest=binding_digest(
        definition, args.app_id, args.installation_id, args.account))
    if token:
        value["token_digest"] = "sha256:" + hashlib.sha256(token.token.encode()).hexdigest()
        value["repository_selection"] = token.repository_selection
    return value


def target(args, definition, *, running):
    identity.verify_kubectl_command(args.kubectl, sandbox=args.sandbox)
    return identity.verify_dev_integration_cluster(args.kubectl, identity.load_dev_integration_target(
        args.session_manifest, args.workspace_root, definition, require_running=running))


def secret_manifest(args, definition, token, runtime_target):
    value = yaml.safe_load(identity.secret_manifest(definition, token, (), binding_digest(
        definition, args.app_id, args.installation_id, args.account), runtime_target))
    value["metadata"]["annotations"][SCOPE_ANNOTATION] = json.dumps(scope(args.account), sort_keys=True)
    value["stringData"][ACCOUNT_ENV] = scope(args.account)["account"]
    return yaml.safe_dump(value, sort_keys=False)


@contextmanager
def selection_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    descriptor = os.open(lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise identity.IdentityError("reader selection lock is not private")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)


def command(args, action):
    if action in ("deliver", "revoke"):
        with selection_lock(args.receipt):
            expected = getattr(args, "expected_selection_digest", None)
            if expected is not None:
                if args.receipt.is_symlink() or not args.receipt.exists() or "sha256:" + hashlib.sha256(args.receipt.read_bytes()).hexdigest() != expected:
                    raise identity.IdentityError("reader selection changed; stale renewal is denied")
            return command_locked(args, action)
    return command_locked(args, action)


def command_locked(args, action):
    definition = contract(args.contract)
    if action == "validate":
        print(f"repository provider identity contract valid: {definition.identity_id}; selected and account metadata scopes")
        return 0
    if action == "revoke":
        return revoke(args, definition)
    runtime_target = target(args, definition, running=True) if action == "deliver" else None
    client, token = issued(args, definition)
    projected = False
    projection_attempted = False
    try:
        if action == "deliver":
            # Persist the intended scope before projection. A crash after Apply
            # can resume only when the actual Secret matches this exact token.
            identity.write_receipt(args.receipt, receipt(args, definition, action, "prepared",
                token=token, target=runtime_target))
            projection_attempted = True
            identity.run_kubectl(args.kubectl, ["apply", "-f", "-"],
                input_text=secret_manifest(args, definition, token, runtime_target))
            projected = True
            outcome = "delivered"
        else:
            client.revoke_token(token.token)
            outcome = "verified-and-proof-token-revoked"
        identity.write_receipt(args.receipt, receipt(args, definition, action, outcome,
            token=token, target=runtime_target))
    except Exception:
        # A projected token may already be consumed. Retain it and its Secret
        # after an uncertain receipt write; never revoke a live replacement.
        if not projection_attempted and not projected:
            client.revoke_token(token.token)
        raise
    print(f"account metadata identity {outcome}; receipt={args.receipt}")
    return 0


def revoke(args, definition):
    runtime_target = target(args, definition, running=False)
    result = identity.run_kubectl(args.kubectl, ["-n", runtime_target.namespace, "get", "secret",
        definition.runtime_secret_name, "-o", "json"])
    try:
        secret = json.loads(result.stdout)
        annotations = secret["metadata"]["annotations"]
        if (json.loads(annotations[SCOPE_ANNOTATION]) != scope(args.account)
                or annotations["workspace-governance/credential-binding-digest"] != binding_digest(
                    definition, args.app_id, args.installation_id, args.account)
                or secret["metadata"]["namespace"] != runtime_target.namespace
                or annotations["workspace-governance/dev-integration-profile"] != runtime_target.profile_id
                or secret["metadata"]["labels"]["app.kubernetes.io/managed-by"] != "platform-engineering"):
            raise ValueError("binding")
        token = base64.b64decode(secret["data"][definition.runtime_secret_key], validate=True).decode()
    except (KeyError, ValueError, TypeError):
        raise identity.IdentityError("account reader revocation binding is invalid") from None
    client = identity.ProviderClient(args.provider_api_base_url or definition.api_base_url, sandbox=args.sandbox)
    try:
        client.revoke_token(token)
    except identity.ProviderHttpError as exc:
        if exc.status_code not in (401, 404):
            raise
    identity.run_kubectl(args.kubectl, ["-n", runtime_target.namespace, "delete", "secret", definition.runtime_secret_name, "--ignore-not-found"])
    identity.write_receipt(args.receipt, receipt(args, definition, "revoke", "revoked", target=runtime_target))
    print(f"account reader revoked; receipt={args.receipt}")
    return 0
