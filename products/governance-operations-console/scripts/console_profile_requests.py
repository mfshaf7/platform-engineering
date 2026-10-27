"""Compose the existing OOS request lifecycle and Platform evidence publisher."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import model_profile_lifecycle as lifecycle

CALLER = "governance-operations-console"
FULFILLER = lifecycle.ACTOR_ID


class ProfileCompositionError(RuntimeError):
    pass


def enabled(policy):
    return policy.get("purpose_profiles", {}).get("enabled") is True


def paths(state_root):
    root = state_root / "private/model-profile-requests"
    return root, root / "current-registry.json", root / "request-history", root / "fulfillment-caller-secret"


def private_directory(path):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.geteuid():
        raise ProfileCompositionError("Model-profile publication requires private owner directories.")
    path.chmod(0o700)


def prepare(policy, *, repo_root, state_root, run):
    if not enabled(policy):
        return
    if policy.get("security", {}).get("status") != "accepted":
        raise ProfileCompositionError("Model-profile composition requires exact Security acceptance.")
    root, projection, history, credential = paths(state_root)
    private_directory(root)
    private_directory(history)
    if credential.is_symlink():
        raise ProfileCompositionError("Model-profile fulfillment credential must not be a symlink.")
    if not credential.exists():
        lifecycle.write_atomic(credential, (secrets.token_urlsafe(48) + "\n").encode())
    if credential.is_symlink() or credential.stat().st_uid != os.geteuid() or credential.stat().st_mode & 0o077:
        raise ProfileCompositionError("Model-profile fulfillment credential custody is invalid.")
    # Current registry readiness is independent of any earlier transaction.
    run([sys.executable, str(repo_root / "scripts/model_profile_lifecycle.py"),
         "--repo-root", str(repo_root), "project", "--output", str(projection)])


def activation_environment(state_root):
    _, projection, history, _ = paths(state_root)
    return {"GOVERNANCE_CONSOLE_MODEL_PROFILE_SOURCE_PROJECTION_PATH": str(projection),
            "GOVERNANCE_CONSOLE_MODEL_PROFILE_REQUEST_HISTORY_ROOT": str(history)}


def bind_oos(policy, *, state_root, namespace, operator_id, run):
    if not enabled(policy):
        return
    if policy.get("security", {}).get("status") != "accepted":
        raise ProfileCompositionError("Model-profile bindings require exact Security acceptance.")
    _, _, _, credential = paths(state_root)
    if (credential.is_symlink() or not credential.is_file() or
            credential.stat().st_uid != os.geteuid() or credential.stat().st_mode & 0o077):
        raise ProfileCompositionError("Model-profile fulfillment credential is unavailable.")
    token = credential.read_text().strip()
    if not token:
        raise ProfileCompositionError("Model-profile fulfillment credential is empty.")
    # Extend the existing API authentication source, preserving every caller and
    # secret. The distinct fulfiller never receives an operator binding.
    observed = json.loads(run(["k3s", "kubectl", "-n", namespace, "get", "secret",
                               "operator-orchestration-service-env", "-o", "json"]).stdout)
    data = {key: base64.b64decode(value, validate=True).decode() for key, value in observed["data"].items()}
    allowed = [value.strip() for value in data["CALLER_ALLOWED_IDS"].split(",") if value.strip()]
    callers = json.loads(data["CALLER_AUTH_SECRETS_JSON"])
    if CALLER not in allowed or CALLER not in callers or not operator_id.startswith("operator:"):
        raise ProfileCompositionError("The existing authenticated Console operator binding is unavailable.")
    if FULFILLER not in allowed:
        allowed.append(FULFILLER)
    callers[FULFILLER] = token
    if token in [value for caller, value in callers.items() if caller != FULFILLER] or token == data.get("CALLER_AUTH_SHARED_SECRET"):
        raise ProfileCompositionError("The Platform fulfiller must have a distinct credential.")
    values = {"CALLER_ALLOWED_IDS": ",".join(allowed),
              "CALLER_AUTH_SECRETS_JSON": json.dumps(callers, separators=(",", ":"))}
    run(["k3s", "kubectl", "-n", namespace, "patch", "secret", "operator-orchestration-service-env",
         "--type=merge", "--patch-file=/dev/stdin"], input_value=json.dumps({"stringData": values}))
    settings = {"OOS_MODEL_PROFILE_REQUEST_ENABLED": "true",
                "OOS_MODEL_PROFILE_REQUEST_STATE_ROOT": "/var/lib/oos/model-profile-requests",
                "OOS_MODEL_PROFILE_REQUEST_CALLER_OPERATOR_BINDINGS_JSON": json.dumps({CALLER: operator_id}),
                "OOS_MODEL_PROFILE_FULFILLMENT_CALLER_IDS": FULFILLER}
    version = hashlib.sha256(json.dumps({**settings, **values}, sort_keys=True).encode()).hexdigest()
    patch = {"spec": {"template": {"metadata": {"annotations": {"workspace-governance/model-profile-bindings": version}},
             "spec": {"containers": [{"name": "operator-orchestration-service",
                       "env": [{"name": key, "value": value} for key, value in settings.items()]}]}}}}
    run(["k3s", "kubectl", "-n", namespace, "patch", "deployment", "operator-orchestration-service",
         "--type=strategic", "--patch-file=/dev/stdin"], input_value=json.dumps(patch))
    run(["k3s", "kubectl", "-n", namespace, "rollout", "status",
         "deployment/operator-orchestration-service", "--timeout=180s"])


def status(policy, *, state_root, namespace, operator_id, run):
    if not enabled(policy):
        return {"enabled": False}
    _, projection, history, _ = paths(state_root)
    value = lifecycle.load_private_json(projection, label="current model-profile registry")
    if lifecycle.digest_value(value, "digest") != value.get("digest"):
        raise ProfileCompositionError("Current model-profile registry digest is invalid.")
    if history.is_symlink() or not history.is_dir() or history.stat().st_mode & 0o777 != 0o700:
        raise ProfileCompositionError("Model-profile request history is not private.")
    script = """const e=process.env;const id=process.argv[1];const s=JSON.parse(e.CALLER_AUTH_SECRETS_JSON||'{}');
console.log(JSON.stringify({enabled:e.OOS_MODEL_PROFILE_REQUEST_ENABLED==='true',
bindings:JSON.parse(e.OOS_MODEL_PROFILE_REQUEST_CALLER_OPERATOR_BINDINGS_JSON||'{}'),
fulfillers:(e.OOS_MODEL_PROFILE_FULFILLMENT_CALLER_IDS||'').split(','),
authenticated:(e.CALLER_ALLOWED_IDS||'').split(',').includes(id)&&Boolean(s[id]),
state_root:e.OOS_MODEL_PROFILE_REQUEST_STATE_ROOT}));"""
    observed = json.loads(run(["k3s", "kubectl", "-n", namespace, "exec",
        "deployment/operator-orchestration-service", "-c", "operator-orchestration-service", "--",
        "node", "-e", script, FULFILLER]).stdout)
    if (observed.get("enabled") is not True or observed.get("authenticated") is not True or
            observed.get("bindings") != {CALLER: operator_id} or observed.get("fulfillers") != [FULFILLER] or
            observed.get("state_root") != "/var/lib/oos/model-profile-requests"):
        raise ProfileCompositionError("Live model-profile request/fulfillment bindings are incomplete.")
    return {"enabled": True, "operator_bound": True, "distinct_fulfiller_bound": True,
            "registry_digest": value["digest"], "registry_source": value["source"]["source_version"],
            "profile_count": len(value["profiles"]), "transaction_required_for_registry": False}


def disable(policy, *, namespace, run):
    if not enabled(policy):
        return
    observed = run(["k3s", "kubectl", "-n", namespace, "get", "deployment",
                    "operator-orchestration-service", "--ignore-not-found", "-o", "json"])
    if not observed.stdout.strip():
        return
    patch = {"spec": {"template": {"spec": {"containers": [{"name": "operator-orchestration-service",
        "env": [{"name": "OOS_MODEL_PROFILE_REQUEST_ENABLED", "value": "false"}]}]}}}}
    run(["k3s", "kubectl", "-n", namespace, "patch", "deployment", "operator-orchestration-service",
         "--type=strategic", "--patch-file=/dev/stdin"], input_value=json.dumps(patch))
    observed = run(["k3s", "kubectl", "-n", namespace, "get", "secret",
                    "operator-orchestration-service-env", "--ignore-not-found", "-o", "json"])
    if observed.stdout.strip():
        data = {key: base64.b64decode(value, validate=True).decode()
                for key, value in json.loads(observed.stdout)["data"].items()}
        allowed = [value.strip() for value in data["CALLER_ALLOWED_IDS"].split(",")
                   if value.strip() and value.strip() != FULFILLER]
        callers = json.loads(data["CALLER_AUTH_SECRETS_JSON"])
        callers.pop(FULFILLER, None)
        values = {"CALLER_ALLOWED_IDS": ",".join(allowed), "CALLER_AUTH_SECRETS_JSON": json.dumps(callers)}
        run(["k3s", "kubectl", "-n", namespace, "patch", "secret", "operator-orchestration-service-env",
             "--type=merge", "--patch-file=/dev/stdin"], input_value=json.dumps({"stringData": values}))
    run(["k3s", "kubectl", "-n", namespace, "rollout", "status",
         "deployment/operator-orchestration-service", "--timeout=180s"])
    # Preserve canonical OOS request state, historical source evidence and the
    # scoped private credential for a reviewed resume; only runtime grants stop.
