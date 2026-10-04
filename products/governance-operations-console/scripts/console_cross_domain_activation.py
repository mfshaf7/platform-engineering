#!/usr/bin/env python3
"""Activate and prove the Console's local cross-domain read boundary."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import stat
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml


PRODUCT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PRODUCT_ROOT.parents[1]
WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/home/mfshaf7/projects"))
POLICY_PATH = PRODUCT_ROOT / "cross-domain-activation-policy.yaml"
STATE_ROOT = Path.home() / ".local/state/platform-engineering/governance-console-cross-domain"
PRIVATE_ROOT = STATE_ROOT / "private"
RECEIPT_ROOT = STATE_ROOT / "receipts"
UNIT_ROOT = Path.home() / ".config/systemd/user"
CALLER_ID = "governance-operations-console"
UNIT_PREFIX = "governance-console-cross-domain"
WGCF_SECRET = "governance-console-history-reader"
REPO_PATH_OVERRIDES: dict[str, Path] = {}


class ActivationError(RuntimeError):
    pass


def ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ActivationError(f"private state directory must not be a symlink: {path}")
    info = path.stat()
    if info.st_uid != os.geteuid():
        raise ActivationError(f"private state directory has the wrong owner: {path}")
    path.chmod(0o700)


def run(
    args: list[str],
    *,
    check: bool = True,
    capture: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, text=True, capture_output=capture, check=False)
    if check and result.returncode:
        detail = (result.stderr or result.stdout or "command failed").strip().splitlines()[-1]
        raise ActivationError(f"{args[0]} failed: {detail}")
    return result


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 2:
        raise ActivationError("cross-domain activation policy is invalid")
    for owner in ("oos", "wgcf"):
        required = {
            "repo", "revision", "profile", "namespace", "service",
            "remote_port", "local_port",
        }
        if not required.issubset(value.get("owners", {}).get(owner, {})):
            raise ActivationError(f"cross-domain activation policy is incomplete for {owner}")
    return value


def parse_repo_paths(entries: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for entry in entries:
        if "=" not in entry:
            raise ActivationError("--repo-path must use repo=/absolute/path")
        name, raw_path = entry.split("=", 1)
        path = Path(raw_path).expanduser()
        if not name or not path.is_absolute() or not path.is_dir():
            raise ActivationError("--repo-path must use an existing absolute repository path")
        result[name] = path.resolve()
    return result


def operator() -> str:
    return os.environ.get("DEVINT_OPERATOR", os.environ.get("USER", "")).strip()


def repo_path(name: str) -> Path:
    return REPO_PATH_OVERRIDES.get(name, WORKSPACE_ROOT / name)


def git_head(path: Path) -> str:
    return run(["git", "-C", str(path), "rev-parse", "HEAD"]).stdout.strip()


def require_revision(name: str, revision: str) -> None:
    path = repo_path(name)
    if not path.is_dir() or git_head(path) != revision:
        raise ActivationError(f"{name} is not at the Security-approved revision {revision}")
    if run(["git", "-C", str(path), "status", "--porcelain"]).stdout.strip():
        raise ActivationError(f"{name} must be clean before activation")


def require_clean_platform_source() -> None:
    if run(["git", "-C", str(REPO_ROOT), "status", "--porcelain"]).stdout.strip():
        raise ActivationError("the executing Platform checkout must be clean before activation")


def require_architecture_binding(policy: dict[str, Any], review_content: str) -> None:
    architecture = policy.get("architecture", {})
    current = architecture.get("current", {})
    predecessor = architecture.get("predecessor", {})
    relationship = architecture.get("relationship")
    if architecture.get("artifact_id") != "architecture-packet:delivery-1203-v1":
        raise ActivationError("the architecture packet lineage binding is invalid")
    if relationship == "exact-supersession":
        if current.get("digest") == predecessor.get("digest"):
            raise ActivationError("the architecture packet lineage binding is invalid")
        references = (("current", current), ("predecessor", predecessor))
    elif relationship == "exact-security-binding":
        references = (("current", current),)
    else:
        raise ActivationError("the architecture packet lineage binding is invalid")
    for label, reference in references:
        digest = reference.get("digest", "")
        uri = reference.get("uri", "")
        if (
            not isinstance(digest, str)
            or not digest.startswith("sha256:")
            or len(digest) != 71
            or uri != f"wgcf://artifacts/delivery-art/sha256/{digest.removeprefix('sha256:')}"
        ):
            raise ActivationError(f"the {label} architecture packet reference is invalid")
        if uri not in review_content:
            raise ActivationError(
                f"the Security review does not bind the {label} architecture packet"
            )
    approved_revisions = [
        policy["console"]["revision"],
        *(owner["revision"] for owner in policy["owners"].values()),
        policy["authority"]["workspace_governance_revision"],
    ]
    missing = [revision for revision in approved_revisions if revision not in review_content]
    if missing:
        raise ActivationError("the Security review does not bind every configured source revision")


def manifest_path(profile: str) -> Path:
    return WORKSPACE_ROOT / ".dev-integration" / profile / operator() / "current-session.yaml"


def session_projection_path(policy: dict[str, Any]) -> Path:
    return STATE_ROOT / policy["session"]["projection"]


def session_receipt_path(policy: dict[str, Any], action: str) -> Path:
    key = "issue_receipt" if action == "issue" else "revoke_receipt"
    return STATE_ROOT / policy["session"][key]


def session_projection_command(
    policy: dict[str, Any],
    action: str,
) -> list[str]:
    script = PRODUCT_ROOT / "scripts" / "console_session_projection.py"
    command = [
        sys.executable,
        str(script),
        "--policy",
        str(PRODUCT_ROOT / policy["session"]["policy"]),
        action,
        "--projection",
        str(session_projection_path(policy)),
        "--receipt",
        str(session_receipt_path(policy, action)),
    ]
    if action == "issue":
        command.extend([
            "--session-manifest",
            str(manifest_path(policy["session"]["profile"])),
        ])
    return command


def issue_session_projection(policy: dict[str, Any]) -> None:
    if not policy.get("session"):
        return
    ensure_private_directory(STATE_ROOT)
    ensure_private_directory(PRIVATE_ROOT)
    ensure_private_directory(RECEIPT_ROOT)
    projection = session_projection_path(policy)
    if projection.exists():
        run(session_projection_command(policy, "revoke"), check=False)
    run(session_projection_command(policy, "issue"))


def revoke_session_projection(policy: dict[str, Any]) -> None:
    if policy.get("session") and session_projection_path(policy).exists():
        run(session_projection_command(policy, "revoke"))


def require_manifest(owner: dict[str, Any]) -> None:
    path = manifest_path(owner["profile"])
    if not path.is_file():
        raise ActivationError(f"{owner['profile']} has no current dev-integration session")
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    source = value.get("source_repos", {}).get(owner["repo"], {}) if isinstance(value, dict) else {}
    if source.get("head_sha") != owner["revision"] or source.get("dirty") is not False:
        raise ActivationError(
            f"{owner['profile']} is not running the approved {owner['repo']} source"
        )


def validate(policy: dict[str, Any]) -> None:
    if not operator():
        raise ActivationError("the dev-integration operator is unavailable")
    for command in ("git", "k3s", "npm", "systemctl"):
        if run(["bash", "-lc", f"command -v {command}"], check=False).returncode:
            raise ActivationError(f"required command is unavailable: {command}")
    require_clean_platform_source()
    require_revision(policy["console"]["repo"], policy["console"]["revision"])
    for owner in policy["owners"].values():
        require_revision(owner["repo"], owner["revision"])
        require_manifest(owner)
    require_revision("workspace-governance", policy["authority"]["workspace_governance_revision"])
    if policy.get("session"):
        required_session = {
            "policy", "operator_id", "profile", "projection",
            "issue_receipt", "revoke_receipt",
        }
        if not required_session.issubset(policy["session"]):
            raise ActivationError("the Console session projection policy binding is incomplete")
        if policy["session"]["profile"] != policy["owners"]["oos"]["profile"]:
            raise ActivationError("the Console session projection profile does not match OOS")
        session_policy = PRODUCT_ROOT / policy["session"]["policy"]
        if not session_policy.is_file():
            raise ActivationError("the Console session projection policy is unavailable")
    security = repo_path("security-architecture")
    revision = policy["authority"]["security_revision"]
    review = policy["authority"]["security_review_ref"]
    if run(
        ["git", "-C", str(security), "cat-file", "-e", f"{revision}^{{commit}}"],
        check=False,
    ).returncode:
        raise ActivationError("the Security activation revision is unavailable")
    if run(
        ["git", "-C", str(security), "cat-file", "-e", f"{revision}:{review}"],
        check=False,
    ).returncode:
        raise ActivationError(
            "the Security activation review is unavailable at the approved revision"
        )
    review_content = run(
        ["git", "-C", str(security), "show", f"{revision}:{review}"]
    ).stdout
    require_architecture_binding(policy, review_content)


def read_oos_secret(policy: dict[str, Any]) -> str:
    path = manifest_path(policy["owners"]["oos"]["profile"]).parent / "broker.env"
    if not path.is_file():
        raise ActivationError("the OOS runtime credential source is unavailable")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("CALLER_AUTH_SECRETS_JSON="):
            value = json.loads(line.split("=", 1)[1])
            secret = value.get(CALLER_ID, "")
            if isinstance(secret, str) and len(secret) >= 32:
                return secret
    raise ActivationError("the dedicated Console OOS credential is unavailable")


def wgcf_secret() -> str:
    path = PRIVATE_ROOT / "wgcf-caller-secret"
    if path.exists():
        secret = path.read_text(encoding="utf-8").strip()
    else:
        ensure_private_directory(PRIVATE_ROOT)
        secret = secrets.token_urlsafe(36)
        path.write_text(secret + "\n", encoding="utf-8")
        path.chmod(0o600)
    if len(secret) < 32:
        raise ActivationError("the WGCF Console credential is invalid")
    return secret


def namespace(template: str) -> str:
    return template.replace("{operator}", operator())


def kubectl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["k3s", "kubectl", *args], check=check)


def install_wgcf_binding(policy: dict[str, Any], secret: str) -> None:
    owner = policy["owners"]["wgcf"]
    ns = namespace(owner["namespace"])
    rendered = kubectl(
        "-n", ns, "create", "secret", "generic", WGCF_SECRET,
        f"--from-literal=WGCF_GOVERNANCE_HISTORY_CALLER_ID={CALLER_ID}",
        f"--from-literal=WGCF_GOVERNANCE_HISTORY_CALLER_SECRET={secret}",
        "--dry-run=client", "-o", "yaml",
    ).stdout
    applied = subprocess.run(
        ["k3s", "kubectl", "apply", "-f", "-"], input=rendered, text=True,
        capture_output=True, check=False,
    )
    if applied.returncode:
        raise ActivationError("WGCF reader credential installation failed")
    set_env = [
        "-n", ns, "set", "env", f"deployment/{owner['deployment']}",
        f"--from=secret/{WGCF_SECRET}",
    ]
    if policy.get("catalog_proof"):
        contract_root = policy["catalog_proof"].get("wgcf_contract_root")
        if contract_root != "/app/contracts/repository-readiness":
            raise ActivationError("WGCF repository-readiness contract root is invalid")
        set_env.append(f"WGCF_REPOSITORY_READINESS_CONTRACT_ROOT={contract_root}")
    kubectl(*set_env)
    kubectl("-n", ns, "rollout", "status", f"deployment/{owner['deployment']}", "--timeout=180s")


def wgcf_binding_present(policy: dict[str, Any]) -> bool:
    owner = policy["owners"]["wgcf"]
    ns = namespace(owner["namespace"])
    if kubectl("-n", ns, "get", "secret", WGCF_SECRET, check=False).returncode != 0:
        return False
    result = kubectl(
        "-n", ns, "get", f"deployment/{owner['deployment']}", "-o", "json",
        check=False,
    )
    if result.returncode:
        return False
    deployment = json.loads(result.stdout)
    expected = {
        "WGCF_GOVERNANCE_HISTORY_CALLER_ID",
        "WGCF_GOVERNANCE_HISTORY_CALLER_SECRET",
    }
    if policy.get("catalog_proof"):
        expected.add("WGCF_REPOSITORY_READINESS_CONTRACT_ROOT")
    observed = {
        item.get("name")
        for container in deployment.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        for item in container.get("env", [])
        if isinstance(item, dict)
    }
    return expected.issubset(observed)


def unit_name(role: str) -> str:
    return f"{UNIT_PREFIX}-{role}.service"


def write_private_env(policy: dict[str, Any], oos_secret: str, history_secret: str) -> Path:
    ensure_private_directory(PRIVATE_ROOT)
    path = PRIVATE_ROOT / "console.env"
    values = [
            f"OOS_BASE_URL=http://127.0.0.1:{policy['owners']['oos']['local_port']}",
            f"OOS_CALLER_ID={CALLER_ID}",
            f"OOS_CALLER_SECRET={oos_secret}",
            f"WGCF_BASE_URL=http://127.0.0.1:{policy['owners']['wgcf']['local_port']}",
            f"WGCF_CALLER_ID={CALLER_ID}",
            f"WGCF_CALLER_SECRET={history_secret}",
    ]
    if policy.get("session"):
        values.extend([
            f"GOVERNANCE_CONSOLE_OPERATOR_ID={policy['session']['operator_id']}",
            f"GOVERNANCE_CONSOLE_SESSION_PROJECTION_PATH={session_projection_path(policy)}",
        ])
    path.write_text(
        "\n".join(values) + "\n",
        encoding="utf-8",
    )
    path.chmod(0o600)
    return path


def write_units(policy: dict[str, Any], env_path: Path) -> None:
    UNIT_ROOT.mkdir(parents=True, exist_ok=True)
    k3s_path = shutil.which("k3s")
    npm_path = shutil.which("npm")
    if not k3s_path or not npm_path:
        raise ActivationError("validated runtime executable path is unavailable")
    for role in ("oos", "wgcf"):
        owner = policy["owners"][role]
        content = f"""[Unit]
Description=Governance Console {role.upper()} dev-integration tunnel
After=network.target

[Service]
ExecStart={k3s_path} kubectl -n {namespace(owner['namespace'])} port-forward service/{owner['service']} {owner['local_port']}:{owner['remote_port']} --address 127.0.0.1
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
"""
        (UNIT_ROOT / unit_name(role)).write_text(content, encoding="utf-8")
    console_root = repo_path(policy["console"]["repo"])
    console = f"""[Unit]
Description=Governance Operations Console cross-domain dev-integration
Wants={unit_name('oos')} {unit_name('wgcf')}
After={unit_name('oos')} {unit_name('wgcf')}

[Service]
WorkingDirectory={console_root}
EnvironmentFile={env_path}
Environment=PATH={Path(npm_path).parent}:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart={npm_path} run dev
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
"""
    (UNIT_ROOT / unit_name("console")).write_text(console, encoding="utf-8")
    run(["systemctl", "--user", "daemon-reload"])


def enable_units() -> None:
    units = [unit_name("oos"), unit_name("wgcf"), unit_name("console")]
    run(["systemctl", "--user", "enable", *units])
    run(["systemctl", "--user", "reset-failed", *units], check=False)
    run(["systemctl", "--user", "restart", *units])


def active_runtime_boundary(policy: dict[str, Any], env_path: Path | None = None) -> dict[str, Any]:
    selected_env = env_path or (PRIVATE_ROOT / "console.env")
    return {
        "console_private_environment_mode": (
            oct(selected_env.stat().st_mode & 0o777) if selected_env.is_file() else None
        ),
        "owner_sessions_preserved": all(
            manifest_path(item["profile"]).is_file()
            for item in policy["owners"].values()
        ),
        "services_active": all(
            run(
                ["systemctl", "--user", "is-active", "--quiet", unit_name(role)],
                check=False,
            ).returncode == 0
            for role in ("oos", "wgcf", "console")
        ),
        "wgcf_reader_binding_present": wgcf_binding_present(policy),
    }


def http_json(url: str) -> dict[str, Any]:
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=15) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ActivationError(f"live Console proof failed: {type(exc).__name__}") from None
    if not isinstance(value, dict):
        raise ActivationError("live Console proof returned an invalid payload")
    return value


def http_request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
    timeout: int = 20,
) -> tuple[int, dict[str, Any]]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(
        url,
        data=data,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            status = response.status
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        status = exc.code
        raw = exc.read().decode("utf-8")
    except (URLError, TimeoutError) as exc:
        raise ActivationError(f"live Console request failed: {type(exc).__name__}") from None
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        raise ActivationError("live Console request returned malformed JSON") from None
    if not isinstance(value, dict):
        raise ActivationError("live Console request returned an invalid payload")
    return status, value


def require_http_success(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    status, value = http_request_json(url, method=method, body=body)
    if status < 200 or status >= 300:
        code = value.get("code") or value.get("error") or "unknown"
        raise ActivationError(f"live Console request was rejected: {status} {code}")
    return value


def wait_for_activity(policy: dict[str, Any]) -> dict[str, Any]:
    url = f"http://127.0.0.1:{policy['console']['port']}/api/governance-activity"
    deadline = time.monotonic() + 180
    last = "Console did not become ready"
    while time.monotonic() < deadline:
        try:
            value = http_json(url)
            if value.get("mode") != "live" or value.get("status") not in {"current", "partial"}:
                last = "Console activity was not live and readable"
            else:
                current_owners = {
                    item.get("owner") for item in value.get("sources", [])
                    if isinstance(item, dict) and item.get("state") == "current"
                }
                if {
                    "operator-orchestration-service",
                    "workspace-governance-control-fabric",
                }.issubset(current_owners):
                    raw = json.dumps(value).casefold()
                    if "synthetic-scenario" in raw or "prototype-local" in raw:
                        raise ActivationError("live Console proof included fixture authority")
                    return value
                last = "Console activity did not expose both canonical owners"
        except ActivationError as exc:
            last = str(exc)
        time.sleep(2)
    raise ActivationError(last)


def console_url(policy: dict[str, Any], path: str) -> str:
    return f"http://127.0.0.1:{policy['console']['port']}{path}"


def wait_for_catalog(policy: dict[str, Any]) -> dict[str, Any]:
    deadline = time.monotonic() + 180
    last = "Catalog did not become ready"
    while time.monotonic() < deadline:
        try:
            value = require_http_success(
                console_url(policy, "/api/delivery/catalog/projection")
            )
            projection = value.get("projection")
            if (
                value.get("mode") == "live"
                and value.get("status") == "current"
                and isinstance(projection, dict)
                and projection.get("projection_status") == "ready"
            ):
                raw = json.dumps(value).casefold()
                if "synthetic-scenario" in raw or "prototype-local" in raw:
                    raise ActivationError("live Catalog proof included fixture authority")
                return value
            last = "Catalog projection was not live, current, and ready"
        except ActivationError as exc:
            last = str(exc)
        time.sleep(2)
    raise ActivationError(last)


def workspace_registry(policy: dict[str, Any]) -> dict[str, Any]:
    value = require_http_success(console_url(policy, "/api/workspace-registry"))
    if (
        value.get("canonical_mutation") is not False
        or value.get("canonical_authority", {}).get("repo") != "workspace-governance"
        or value.get("authority_revision") != policy["authority"]["workspace_governance_revision"]
    ):
        raise ActivationError("Workspace Registry did not return exact canonical authority")
    return value


def active_repository(registry: dict[str, Any], repo_name: str) -> dict[str, Any]:
    matches = [
        item for item in registry.get("records", [])
        if isinstance(item, dict)
        and item.get("kind") == "repo"
        and item.get("name") == repo_name
        and item.get("posture") == "active"
    ]
    if len(matches) != 1:
        raise ActivationError(f"Repository {repo_name} is not one exact active Registry record")
    return matches[0]


def catalog_projection(snapshot: dict[str, Any]) -> dict[str, Any]:
    value = snapshot.get("projection")
    if not isinstance(value, dict):
        raise ActivationError("Catalog projection is unavailable")
    return value


def catalog_value(
    projection: dict[str, Any],
    catalog_item_id: str,
    value_key: str,
) -> dict[str, Any] | None:
    matches = [
        item for item in projection.get("values", [])
        if isinstance(item, dict)
        and item.get("catalog_item_id") == catalog_item_id
        and item.get("value_key") == value_key
        and item.get("lifecycle_state") != "retired"
    ]
    if len(matches) > 1:
        raise ActivationError("Catalog contains duplicate active repository values")
    return matches[0] if matches else None


def catalog_canonical_state(value: dict[str, Any] | None) -> dict[str, Any] | None:
    """Remove projection-only metadata before comparing persisted Catalog state."""
    if value is None:
        return None
    canonical = json.loads(json.dumps(value))
    canonical.pop("last_projected_at", None)
    return canonical


def repository_option(repo_name: str, record: dict[str, Any]) -> dict[str, Any]:
    return {
        "admissionState": "admitted",
        "description": f"Active Workspace Inventory repository {repo_name}.",
        "id": record["id"],
        "label": repo_name,
        "owner": "workspace-governance",
        "repoRef": f"repo://{repo_name}",
        "routeSource": record["lineage"]["source_ref"],
        "valueKey": repo_name,
    }


def acceptance_id(prefix: str, repo_name: str) -> str:
    seed = f"{prefix}:{repo_name}:{datetime.now(UTC).isoformat()}:{secrets.token_hex(8)}"
    return f"platform-{prefix}:{hashlib.sha256(seed.encode()).hexdigest()[:32]}"


def catalog_command(
    repo_name: str,
    record: dict[str, Any],
    *,
    mode: str,
    target_value_id: str | None,
    readiness: dict[str, Any] | None = None,
    prefix: str,
) -> dict[str, Any]:
    command: dict[str, Any] = {
        "acceptanceId": acceptance_id(prefix, repo_name),
        "acceptedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "draft": {
            "description": f"Active Workspace Inventory owner repository {repo_name}.",
            "label": repo_name,
            "linkedRepository": repository_option(repo_name, record),
            "parentCatalogValueKey": None,
            "planningWindowEndDate": "",
            "planningWindowStartDate": "",
            "valueKey": repo_name,
        },
        "mode": mode,
        "targetValueId": target_value_id,
    }
    if readiness is not None:
        command["repositoryReadiness"] = readiness
    return command


def mutate_catalog(
    policy: dict[str, Any],
    command: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    item_id = policy["catalog_proof"]["catalog_item_id"]
    result: tuple[int, dict[str, Any]] = (503, {})
    for attempt in range(3):
        result = http_request_json(
            console_url(policy, f"/api/delivery/catalog/{item_id}/mutations"),
            method="POST",
            body=command,
        )
        if result[0] not in {502, 503, 504} or attempt == 2:
            return result
        # Reuse the exact acceptance id so a lost acknowledgement replays
        # instead of creating a second logical Catalog mutation.
        time.sleep(attempt + 1)
    return result


def require_applied(status: int, value: dict[str, Any], label: str) -> dict[str, Any]:
    if (
        status < 200 or status >= 300
        or value.get("status") != "applied"
        or value.get("readback_complete") is not True
        or not isinstance(value.get("value"), dict)
        or not isinstance(value.get("receipt"), dict)
    ):
        raise ActivationError(f"{label} did not return complete canonical readback")
    return value


def require_denied(
    status: int,
    value: dict[str, Any],
    label: str,
    *,
    expected_statuses: set[int] | None = None,
) -> dict[str, Any]:
    allowed = expected_statuses or {400, 401, 403, 409, 502, 503, 504}
    if status not in allowed or not (value.get("code") or value.get("error")):
        raise ActivationError(f"{label} did not fail closed")
    return {
        "code": value.get("code"),
        "http_status": status,
        "outcome": value.get("outcome") or value.get("status") or "denied",
    }


def deployment_replicas(namespace_name: str, deployment: str) -> int:
    value = json.loads(kubectl(
        "-n", namespace_name, "get", f"deployment/{deployment}", "-o", "json"
    ).stdout)
    replicas = value.get("spec", {}).get("replicas")
    if not isinstance(replicas, int) or replicas < 1:
        raise ActivationError(f"deployment {deployment} has no active replica to rehearse")
    return replicas


def set_deployment_replicas(
    namespace_name: str,
    deployment: str,
    replicas: int,
) -> None:
    kubectl(
        "-n", namespace_name, "scale", f"deployment/{deployment}",
        f"--replicas={replicas}",
    )
    if replicas > 0:
        kubectl(
            "-n", namespace_name, "rollout", "status", f"deployment/{deployment}",
            "--timeout=240s",
        )
        return
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        value = json.loads(kubectl(
            "-n", namespace_name, "get", f"deployment/{deployment}", "-o", "json"
        ).stdout)
        ready = value.get("status", {}).get("readyReplicas", 0)
        available = value.get("status", {}).get("availableReplicas", 0)
        if ready in (None, 0) and available in (None, 0):
            return
        time.sleep(1)
    raise ActivationError(f"deployment {deployment} did not scale down completely")


def repository_catalog_status(policy: dict[str, Any]) -> dict[str, Any]:
    registry = workspace_registry(policy)
    snapshot = wait_for_catalog(policy)
    projection = catalog_projection(snapshot)
    item_id = policy["catalog_proof"]["catalog_item_id"]
    if not any(
        isinstance(item, dict)
        and item.get("catalog_item_id") == item_id
        and item.get("lifecycle_state") == "active"
        for item in projection.get("items", [])
    ):
        raise ActivationError("the Owner Repo Catalog item is not active")
    return {
        "authority_revision": registry["authority_revision"],
        "catalog_item_id": item_id,
        "catalog_projection_status": projection["projection_status"],
        "catalog_source_revision": projection["source_revision"],
        "registry_projection_digest": registry["projection_digest"],
    }


def receipt(
    action: str,
    policy: dict[str, Any],
    activity: dict[str, Any] | None = None,
    *,
    negative_proof: dict[str, Any] | None = None,
    runtime_boundary: dict[str, Any] | None = None,
    repository_catalog_proof: dict[str, Any] | None = None,
) -> Path:
    ensure_private_directory(RECEIPT_ROOT)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload: dict[str, Any] = {
        "schema_version": 1,
        "artifact_type": "console-cross-domain-activation-receipt",
        "action": action,
        "recorded_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "lane": "dev-integration",
        "operator": operator(),
        "activation": policy["activation"],
        "architecture": policy["architecture"],
        "proof_scope": policy["proof_scope"],
        "source_revisions": {
            "platform-engineering": git_head(REPO_ROOT),
            policy["console"]["repo"]: policy["console"]["revision"],
            policy["owners"]["oos"]["repo"]: policy["owners"]["oos"]["revision"],
            policy["owners"]["wgcf"]["repo"]: policy["owners"]["wgcf"]["revision"],
            "workspace-governance": policy["authority"]["workspace_governance_revision"],
            "security-architecture": policy["authority"]["security_revision"],
        },
        "credential_boundary": {
            "browser_credentials_allowed": policy["credentials"]["browser_credentials_allowed"],
            "console_oos_caller_id": policy["credentials"]["console_oos"]["caller_id"],
            "console_wgcf_caller_id": policy["credentials"]["console_wgcf"]["caller_id"],
            "credentials_embedded": False,
        },
        "result": "succeeded",
    }
    if activity is not None:
        payload["live_proof"] = {
            "mode": activity.get("mode"),
            "status": activity.get("status"),
            "source_owners": sorted({
                item.get("owner") for item in activity.get("sources", [])
                if isinstance(item, dict)
            }),
            "current_source_owners": sorted({
                item.get("owner") for item in activity.get("sources", [])
                if isinstance(item, dict) and item.get("state") == "current"
            }),
            "event_count": len(activity.get("events", [])),
            "observed_at": activity.get("observedAt"),
            "truncated": activity.get("truncated"),
        }
    if negative_proof is not None:
        payload["negative_proof"] = negative_proof
    if runtime_boundary is not None:
        payload["runtime_boundary"] = runtime_boundary
    if repository_catalog_proof is not None:
        payload["repository_catalog_proof"] = repository_catalog_proof
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    payload["content_digest"] = f"sha256:{digest}"
    path = RECEIPT_ROOT / f"{timestamp}-{action}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(0o600)
    return path


def activate(policy: dict[str, Any]) -> Path:
    validate(policy)
    history_secret = wgcf_secret()
    install_wgcf_binding(policy, history_secret)
    issue_session_projection(policy)
    env_path = write_private_env(policy, read_oos_secret(policy), history_secret)
    write_units(policy, env_path)
    enable_units()
    activity = wait_for_activity(policy)
    catalog = repository_catalog_status(policy) if policy.get("catalog_proof") else None
    return receipt(
        "activate",
        policy,
        activity,
        runtime_boundary=active_runtime_boundary(policy, env_path),
        repository_catalog_proof=catalog,
    )


def status(policy: dict[str, Any]) -> Path:
    validate(policy)
    for role in ("oos", "wgcf", "console"):
        active = run(
            ["systemctl", "--user", "is-active", "--quiet", unit_name(role)],
            check=False,
        )
        if active.returncode:
            raise ActivationError(f"{role} activation service is not active")
    catalog = repository_catalog_status(policy) if policy.get("catalog_proof") else None
    return receipt(
        "status",
        policy,
        wait_for_activity(policy),
        runtime_boundary=active_runtime_boundary(policy),
        repository_catalog_proof=catalog,
    )


def restart(policy: dict[str, Any]) -> Path:
    validate(policy)
    if policy.get("catalog_proof"):
        oos = policy["owners"]["oos"]
        oos_namespace = namespace(oos["namespace"])
        kubectl(
            "-n", oos_namespace, "rollout", "restart", f"deployment/{oos['deployment']}"
        )
        kubectl(
            "-n", oos_namespace, "rollout", "status", f"deployment/{oos['deployment']}",
            "--timeout=240s",
        )
    run([
        "systemctl", "--user", "restart",
        unit_name("oos"), unit_name("wgcf"), unit_name("console"),
    ])
    activity = wait_for_activity(policy)
    catalog = repository_catalog_status(policy) if policy.get("catalog_proof") else None
    return receipt(
        "restart",
        policy,
        activity,
        runtime_boundary=active_runtime_boundary(policy),
        repository_catalog_proof=catalog,
    )


def rehearse(policy: dict[str, Any]) -> Path:
    validate(policy)
    run(["systemctl", "--user", "stop", unit_name("wgcf")])
    deadline = time.monotonic() + 60
    negative: dict[str, Any] | None = None
    try:
        while time.monotonic() < deadline:
            try:
                value = http_json(
                    f"http://127.0.0.1:{policy['console']['port']}/api/governance-activity"
                )
            except ActivationError:
                time.sleep(1)
                continue
            raw = json.dumps(value).casefold()
            unavailable = [
                source for source in value.get("sources", [])
                if isinstance(source, dict)
                and source.get("owner") == "workspace-governance-control-fabric"
                and source.get("state") == "unavailable"
            ]
            if (
                value.get("mode") == "live"
                and value.get("status") == "partial"
                and unavailable
                and "synthetic-scenario" not in raw
                and "prototype-local" not in raw
            ):
                negative = {
                    "disconnected_owner": "workspace-governance-control-fabric",
                    "mode": value.get("mode"),
                    "status": value.get("status"),
                    "fixture_fallback": False,
                    "error_code": unavailable[0].get("errorCode"),
                }
                break
            time.sleep(1)
        if negative is None:
            raise ActivationError(
                "configured owner disconnection did not fail visibly without fixture fallback"
            )
    finally:
        run(["systemctl", "--user", "start", unit_name("wgcf"), unit_name("console")])
    positive = wait_for_activity(policy)
    return receipt(
        "rehearse",
        policy,
        positive,
        negative_proof=negative,
        runtime_boundary=active_runtime_boundary(policy),
    )


def catalog_rehearse(policy: dict[str, Any]) -> Path:
    validate(policy)
    if not policy.get("catalog_proof") or not policy.get("session"):
        raise ActivationError("Repository and Catalog commissioning policy is required")
    for role in ("oos", "wgcf", "console"):
        if run(
            ["systemctl", "--user", "is-active", "--quiet", unit_name(role)],
            check=False,
        ).returncode:
            raise ActivationError(f"{role} activation service is not active")

    registry = workspace_registry(policy)
    before = catalog_projection(wait_for_catalog(policy))
    item_id = policy["catalog_proof"]["catalog_item_id"]
    selected_repo: str | None = None
    selected_record: dict[str, Any] | None = None
    selected_existing: dict[str, Any] | None = None
    fallback: tuple[str, dict[str, Any], dict[str, Any]] | None = None
    for candidate in policy["catalog_proof"]["repository_candidates"]:
        try:
            record = active_repository(registry, candidate)
        except ActivationError:
            continue
        existing_candidate = catalog_value(before, item_id, candidate)
        if existing_candidate is None:
            selected_repo = candidate
            selected_record = record
            break
        if (
            fallback is None
            and isinstance(existing_candidate.get("repository_binding"), dict)
        ):
            fallback = (candidate, record, existing_candidate)
    first_use_created = selected_repo is not None
    added: dict[str, Any] | None = None
    if selected_repo is None or selected_record is None:
        if fallback is None:
            raise ActivationError(
                "no active Repository has a current or creatable readiness binding"
            )
        selected_repo, selected_record, selected_existing = fallback

    if first_use_created:
        add_status, add_value = mutate_catalog(
            policy,
            catalog_command(
                selected_repo,
                selected_record,
                mode="add",
                target_value_id=None,
                prefix="first-use",
            ),
        )
        added = require_applied(add_status, add_value, "first-use Catalog mutation")
        added_value = added["value"]
    else:
        added_value = selected_existing
        if not isinstance(added_value, dict):
            raise ActivationError("the replayed first-use Catalog value is invalid")
    binding = added_value.get("repository_binding")
    if (
        not isinstance(binding, dict)
        or binding.get("repo_name") != selected_repo
        or binding.get("repo_ref") != f"repo://{selected_repo}"
        or binding.get("catalog_value_key") != selected_repo
        or binding.get("receipt", {}).get("issuer") != "workspace-governance-control-fabric"
        or binding.get("receipt", {}).get("outcome") != "ready"
    ):
        raise ActivationError("first-use mutation did not preserve exact readiness evidence")

    if first_use_created:
        first_readback = catalog_projection(wait_for_catalog(policy))
        current = catalog_value(first_readback, item_id, selected_repo)
        if current != added_value:
            raise ActivationError("first-use Catalog mutation is absent from canonical readback")

    existing_status, existing_value = mutate_catalog(
        policy,
        catalog_command(
            selected_repo,
            selected_record,
            mode="edit",
            target_value_id=added_value["catalog_value_id"],
            readiness=binding if first_use_created else None,
            prefix="existing-reference",
        ),
    )
    existing = require_applied(
        existing_status,
        existing_value,
        "existing-reference Catalog mutation",
    )
    stable_value = existing["value"]
    binding = stable_value.get("repository_binding")
    if (
        not isinstance(binding, dict)
        or binding.get("repo_name") != selected_repo
        or binding.get("receipt", {}).get("issuer")
        != "workspace-governance-control-fabric"
        or binding.get("receipt", {}).get("outcome") != "ready"
    ):
        raise ActivationError("existing-reference mutation did not refresh readiness evidence")

    stale_binding = json.loads(json.dumps(binding))
    stale_binding["receipt"]["digest"] = "sha256:" + "0" * 64
    stale_status, stale_value = mutate_catalog(
        policy,
        catalog_command(
            selected_repo,
            selected_record,
            mode="edit",
            target_value_id=stable_value["catalog_value_id"],
            readiness=stale_binding,
            prefix="stale-readiness",
        ),
    )
    negatives: dict[str, Any] = {
        "stale_or_false_readiness": require_denied(
            stale_status, stale_value, "stale or false readiness"
        )
    }

    revoke_session_projection(policy)
    try:
        unauthorized_status, unauthorized_value = mutate_catalog(
            policy,
            catalog_command(
                selected_repo,
                selected_record,
                mode="edit",
                target_value_id=stable_value["catalog_value_id"],
                readiness=binding,
                prefix="unauthorized",
            ),
        )
        negatives["unauthorized_session"] = require_denied(
            unauthorized_status,
            unauthorized_value,
            "unauthorized session",
            expected_statuses={401, 403},
        )
    finally:
        issue_session_projection(policy)

    run(["systemctl", "--user", "stop", unit_name("oos")])
    try:
        owner_status, owner_value = http_request_json(
            console_url(policy, "/api/delivery/catalog/projection")
        )
        negatives["oos_unavailable"] = require_denied(
            owner_status, owner_value, "OOS unavailability", expected_statuses={502, 503, 504}
        )
    finally:
        run(["systemctl", "--user", "start", unit_name("oos")])
        wait_for_catalog(policy)

    unavailable_repo = policy["catalog_proof"]["unavailable_readiness_repository"]
    unavailable_record = active_repository(registry, unavailable_repo)
    unavailable_target = catalog_value(before, item_id, unavailable_repo)
    wgcf_owner = policy["owners"]["wgcf"]
    wgcf_namespace = namespace(wgcf_owner["namespace"])
    wgcf_deployment = wgcf_owner["deployment"]
    wgcf_replicas = deployment_replicas(wgcf_namespace, wgcf_deployment)
    set_deployment_replicas(wgcf_namespace, wgcf_deployment, 0)
    try:
        wgcf_status, wgcf_value = mutate_catalog(
            policy,
            catalog_command(
                unavailable_repo,
                unavailable_record,
                mode="edit" if unavailable_target else "add",
                target_value_id=(
                    unavailable_target.get("catalog_value_id")
                    if unavailable_target else None
                ),
                prefix="wgcf-unavailable",
            ),
        )
        negatives["wgcf_unavailable"] = require_denied(
            wgcf_status,
            wgcf_value,
            "WGCF unavailability",
            expected_statuses={502, 503, 504},
        )
    finally:
        set_deployment_replicas(wgcf_namespace, wgcf_deployment, wgcf_replicas)

    backend = policy["catalog_proof"]["backend"]
    backend_namespace = namespace(backend["namespace"])
    backend_deployment = backend["deployment"]
    backend_replicas = deployment_replicas(backend_namespace, backend_deployment)
    set_deployment_replicas(backend_namespace, backend_deployment, 0)
    try:
        backend_status, backend_value = mutate_catalog(
            policy,
            catalog_command(
                selected_repo,
                selected_record,
                mode="edit",
                target_value_id=stable_value["catalog_value_id"],
                readiness=binding,
                prefix="backend-unavailable",
            ),
        )
        negatives["catalog_backend_unavailable"] = require_denied(
            backend_status,
            backend_value,
            "Catalog backend unavailability",
            expected_statuses={502, 503, 504},
        )
    finally:
        set_deployment_replicas(
            backend_namespace, backend_deployment, backend_replicas
        )

    final_projection = catalog_projection(wait_for_catalog(policy))
    if catalog_canonical_state(
        catalog_value(final_projection, item_id, selected_repo)
    ) != catalog_canonical_state(stable_value):
        raise ActivationError("a denied path changed canonical Catalog state")

    proof = {
        **repository_catalog_status(policy),
        "canonical_readback": True,
        "existing_reference_revalidated": True,
        "first_use_created": first_use_created,
        "first_use_replayed_from_canonical_binding": not first_use_created,
        "first_use_repository": selected_repo,
        "first_use_readiness_receipt": {
            "digest": binding["receipt"]["digest"],
            "generation": binding["receipt"]["generation"],
            "receipt_id": binding["receipt"]["receipt_id"],
            "uri": binding["receipt"]["uri"],
        },
        "mutation_receipts": [
            *([added["receipt"]] if added is not None else []),
            existing["receipt"],
        ],
        "negative_proof": negatives,
    }
    return receipt(
        "catalog-rehearse",
        policy,
        wait_for_activity(policy),
        negative_proof=negatives,
        runtime_boundary=active_runtime_boundary(policy),
        repository_catalog_proof=proof,
    )


def rollback(policy: dict[str, Any], *, remove_files: bool = False) -> Path:
    for role in ("console", "wgcf", "oos"):
        run(["systemctl", "--user", "disable", "--now", unit_name(role)], check=False)
    revoke_session_projection(policy)
    owner = policy["owners"]["wgcf"]
    ns = namespace(owner["namespace"])
    kubectl(
        "-n", ns, "set", "env", f"deployment/{owner['deployment']}",
        "WGCF_GOVERNANCE_HISTORY_CALLER_ID-", "WGCF_GOVERNANCE_HISTORY_CALLER_SECRET-",
        "WGCF_REPOSITORY_READINESS_CONTRACT_ROOT-",
    )
    kubectl("-n", ns, "delete", "secret", WGCF_SECRET, "--ignore-not-found=true")
    kubectl("-n", ns, "rollout", "status", f"deployment/{owner['deployment']}", "--timeout=180s")
    oos = policy["owners"]["oos"]
    kubectl(
        "-n", namespace(oos["namespace"]), "rollout", "status",
        "deployment/operator-orchestration-service", "--timeout=180s",
    )
    for item in policy["owners"].values():
        if not manifest_path(item["profile"]).is_file():
            raise ActivationError(f"rollback removed owner session state for {item['profile']}")
    if remove_files:
        for role in ("console", "wgcf", "oos"):
            (UNIT_ROOT / unit_name(role)).unlink(missing_ok=True)
        for name in ("console.env", "wgcf-caller-secret"):
            (PRIVATE_ROOT / name).unlink(missing_ok=True)
        if policy.get("session"):
            projection = session_projection_path(policy)
            projection.unlink(missing_ok=True)
            projection.with_suffix(projection.suffix + ".lock").unlink(missing_ok=True)
        run(["systemctl", "--user", "daemon-reload"])
    binding_absent = not wgcf_binding_present(policy)
    services_inactive = all(
        run(
            ["systemctl", "--user", "is-active", "--quiet", unit_name(role)],
            check=False,
        ).returncode != 0
        for role in ("console", "wgcf", "oos")
    )
    private_files_absent = all(
        not (PRIVATE_ROOT / name).exists()
        for name in ("console.env", "wgcf-caller-secret")
    )
    if remove_files and policy.get("session"):
        private_files_absent = (
            private_files_absent and not session_projection_path(policy).exists()
        )
    if not binding_absent or not services_inactive or (remove_files and not private_files_absent):
        raise ActivationError("rollback or cleanup live readback is incomplete")
    return receipt(
        "cleanup" if remove_files else "rollback",
        policy,
        runtime_boundary={
            "owner_sessions_preserved": True,
            "private_files_removed": private_files_absent,
            "services_active": False,
            "wgcf_reader_binding_present": False,
        },
    )


def receipt_reference(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    action = value.get("action")
    digest = value.get("content_digest")
    if (
        not isinstance(action, str)
        or not isinstance(digest, str)
        or not digest.startswith("sha256:")
        or len(digest) != 71
    ):
        raise ActivationError(f"child receipt is invalid: {path.name}")
    return {"action": action, "content_digest": digest}


def receipt_content_digest(value: dict[str, Any]) -> str:
    canonical = {key: item for key, item in value.items() if key != "content_digest"}
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def source_evidence_execution() -> bool:
    return (
        Path(sys.argv[0]).resolve() == Path(__file__).resolve()
        and os.environ.get("CI") == "true"
        and os.environ.get("NO_COLOR") == "1"
        and os.environ.get("OOS_DELIVERY_ART_MUTATION_ENABLED") == "true"
        and os.environ.get("OOS_DELIVERY_ART_WRITER_TOPOLOGY") == "single-writer"
    )


def verify_commissioning(policy: dict[str, Any]) -> Path:
    """Verify durable commissioning and current availability without restarting OOS."""
    validate(policy)
    expected_sources = {
        "platform-engineering": git_head(REPO_ROOT),
        policy["console"]["repo"]: policy["console"]["revision"],
        policy["owners"]["oos"]["repo"]: policy["owners"]["oos"]["revision"],
        policy["owners"]["wgcf"]["repo"]: policy["owners"]["wgcf"]["revision"],
        "workspace-governance": policy["authority"]["workspace_governance_revision"],
        "security-architecture": policy["authority"]["security_revision"],
    }
    candidates = sorted(RECEIPT_ROOT.glob("*-commission.json"), reverse=True)
    commissioning: dict[str, Any] | None = None
    for path in candidates:
        value = json.loads(path.read_text(encoding="utf-8"))
        if value.get("source_revisions") == expected_sources:
            commissioning = value
            break
    if commissioning is None:
        raise ActivationError("no commissioning receipt matches the exact source revisions")
    if (
        commissioning.get("action") != "commission"
        or commissioning.get("result") != "succeeded"
        or commissioning.get("architecture") != policy["architecture"]
        or commissioning.get("content_digest") != receipt_content_digest(commissioning)
        or commissioning.get("runtime_boundary", {}).get("final_availability_restored")
        is not True
        or commissioning.get("runtime_boundary", {}).get("services_active") is not True
        or commissioning.get("runtime_boundary", {}).get("wgcf_reader_binding_present")
        is not True
    ):
        raise ActivationError("the exact commissioning receipt is invalid or incomplete")
    proof = commissioning.get("repository_catalog_proof")
    expected_actions = [
        "activate", "status", "catalog-rehearse", "restart", "status",
        "rollback", "cleanup", "activate", "status",
    ]
    child_receipts = proof.get("child_receipts") if isinstance(proof, dict) else None
    if (
        not isinstance(proof, dict)
        or proof.get("commissioning_sequence_complete") is not True
        or not isinstance(child_receipts, list)
        or [item.get("action") for item in child_receipts] != expected_actions
    ):
        raise ActivationError("the commissioning receipt lacks the complete child sequence")
    available_digests: set[str] = set()
    for path in RECEIPT_ROOT.glob("*.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        digest = value.get("content_digest")
        if isinstance(digest, str) and digest == receipt_content_digest(value):
            available_digests.add(digest)
    if any(item.get("content_digest") not in available_digests for item in child_receipts):
        raise ActivationError("a commissioning child receipt is missing or invalid")

    activity = wait_for_activity(policy)
    catalog = repository_catalog_status(policy)
    boundary = active_runtime_boundary(policy)
    if (
        catalog.get("catalog_projection_status") != "ready"
        or boundary.get("services_active") is not True
        or boundary.get("wgcf_reader_binding_present") is not True
    ):
        raise ActivationError("current Repository/Catalog availability is incomplete")
    return receipt(
        "commission-verification",
        policy,
        activity,
        runtime_boundary=boundary,
        repository_catalog_proof={
            **catalog,
            "commissioning_receipt_digest": commissioning["content_digest"],
            "commissioning_recorded_at": commissioning["recorded_at"],
            "commissioning_sequence_verified": True,
            "child_receipts": child_receipts,
        },
    )


def commission(policy: dict[str, Any]) -> Path:
    """Run the complete bounded commissioning sequence and restore availability."""
    if source_evidence_execution():
        return verify_commissioning(policy)
    validate(policy)
    children: list[Path] = []
    restored = False
    try:
        children.append(activate(policy))
        children.append(status(policy))
        children.append(catalog_rehearse(policy))
        children.append(restart(policy))
        children.append(status(policy))
        children.append(rollback(policy))
        children.append(rollback(policy, remove_files=True))
        children.append(activate(policy))
        final_status = status(policy)
        children.append(final_status)
        restored = True
    except Exception as exc:
        restoration_error: Exception | None = None
        try:
            activate(policy)
            status(policy)
            restored = True
        except Exception as restore_exc:
            restoration_error = restore_exc
        if restoration_error is not None:
            raise ActivationError(
                f"commissioning failed ({exc}); final availability restoration also failed "
                f"({restoration_error})"
            ) from exc
        raise

    final_payload = json.loads(final_status.read_text(encoding="utf-8"))
    final_catalog = final_payload.get("repository_catalog_proof")
    if not isinstance(final_catalog, dict):
        raise ActivationError("final commissioning status lacks Repository/Catalog proof")
    return receipt(
        "commission",
        policy,
        wait_for_activity(policy),
        runtime_boundary={
            **active_runtime_boundary(policy),
            "final_availability_restored": restored,
        },
        repository_catalog_proof={
            **final_catalog,
            "commissioning_sequence_complete": True,
            "child_receipts": [receipt_reference(path) for path in children],
        },
    )


def main() -> int:
    global REPO_PATH_OVERRIDES
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, default=POLICY_PATH)
    parser.add_argument(
        "action",
        choices=(
            "validate", "activate", "status", "restart", "rehearse",
            "catalog-rehearse", "commission", "verify-commissioning",
            "rollback", "cleanup",
        ),
    )
    parser.add_argument(
        "--repo-path",
        action="append",
        default=[],
        metavar="REPO=/ABSOLUTE/PATH",
        help="select a clean exact-revision checkout without changing the workspace primary checkout",
    )
    args = parser.parse_args()
    try:
        REPO_PATH_OVERRIDES = parse_repo_paths(args.repo_path)
        policy = load_policy(args.policy)
        if args.action == "validate":
            validate(policy)
            print("cross-domain activation inputs valid")
            return 0
        path = {
            "activate": activate,
            "status": status,
            "restart": restart,
            "rehearse": rehearse,
            "catalog-rehearse": catalog_rehearse,
            "commission": commission,
            "verify-commissioning": verify_commissioning,
            "rollback": lambda value: rollback(value),
            "cleanup": lambda value: rollback(value, remove_files=True),
        }[args.action](policy)
        print(f"cross-domain {args.action} succeeded: {path}")
        return 0
    except ActivationError as exc:
        print(f"cross-domain {args.action} failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
