#!/usr/bin/env python3
"""Commission and prove the bounded lifecycle-context dev-integration composition."""

from __future__ import annotations

import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import stat
import subprocess
import sys
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[3]
DEFINITION = Path(__file__).with_name("composition.yaml")
OPERATOR_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
LIFECYCLE_ENVIRONMENTS = {
    "oos": {
        "CGG_LIFECYCLE_BASE_URL",
        "CGG_LIFECYCLE_CALLER_ID",
        "CGG_LIFECYCLE_CALLER_SECRET",
    },
    "cgg": {
        "CGG_LIFECYCLE_ALLOWED_CALLERS",
        "CGG_LIFECYCLE_CALLER_SHARED_SECRET",
    },
}


class CompositionError(RuntimeError):
    pass


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_definition(path: Path = DEFINITION) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise CompositionError("lifecycle-context composition must use schema_version 1")
    if payload.get("composition_id") != "lifecycle-context":
        raise CompositionError("composition_id must be lifecycle-context")
    if payload.get("owner_repo") != "platform-engineering":
        raise CompositionError("Platform must own lifecycle-context composition")
    if payload.get("lifecycle") != "controlled-dev-integration":
        raise CompositionError("lifecycle-context composition must remain controlled dev-integration")
    participants = payload.get("participants")
    if not isinstance(participants, dict) or set(participants) != {"oos", "cgg"}:
        raise CompositionError("composition must contain exactly the OOS and CGG participants")
    binding = payload.get("binding") or {}
    if binding.get("caller_id") != "operator-orchestration-service":
        raise CompositionError("lifecycle caller id must remain operator-orchestration-service")
    boundary = payload.get("runtime_boundary") or {}
    if (
        boundary.get("lane") != "dev-integration"
        or boundary.get("console_calls_oos_only") is not True
        or boundary.get("default_mode") != "packet"
        or boundary.get("raw_fallback") != "explicit-reasoned-measured"
        or boundary.get("stage_or_production_authority") is not False
    ):
        raise CompositionError("runtime boundary widens the approved lifecycle-context posture")
    for source in (payload.get("source_boundary") or {}).values():
        if not SHA_PATTERN.fullmatch(str(source.get("reviewed_revision") or "")):
            raise CompositionError("source boundary requires exact reviewed revisions")
    if not str((payload.get("commissioning_proof") or {}).get("work_item_id") or "").isdigit():
        raise CompositionError("commissioning proof requires a numeric work item id")
    return payload


def run(
    command: list[str],
    *,
    check: bool = True,
    input_text: str | None = None,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "command failed").strip()
        raise CompositionError(f"{Path(command[0]).name} failed: {detail}")
    return result


def workspace_root() -> Path:
    configured = os.environ.get("WORKSPACE_ROOT")
    if configured:
        root = Path(configured).expanduser().resolve()
    else:
        common = Path(run(["git", "-C", str(ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"]).stdout.strip())
        root = common.parent.parent.resolve()
    if not (root / "workspace-governance" / "contracts" / "repos.yaml").is_file():
        raise CompositionError("WORKSPACE_ROOT does not contain the governed workspace inventory")
    return root


def repo_root(root: Path, participant: dict[str, Any]) -> Path:
    candidate = (root / participant["owner_repo"]).resolve()
    profile_path = (candidate / participant["profile_path"]).resolve()
    try:
        profile_path.relative_to(candidate)
    except ValueError as exc:
        raise CompositionError("participant profile escapes its owner repository") from exc
    if not profile_path.is_file():
        raise CompositionError(f"participant profile is unavailable: {profile_path}")
    return candidate


def git_revision(repo: Path) -> str:
    return run(["git", "-C", str(repo), "rev-parse", "HEAD"]).stdout.strip()


def verify_source_boundary(definition: dict[str, Any], root: Path) -> dict[str, str]:
    revisions: dict[str, str] = {}
    for key, participant in definition["participants"].items():
        repo = repo_root(root, participant)
        selected = git_revision(repo)
        source = definition["source_boundary"][key]
        reviewed = source["reviewed_revision"]
        rule = source["selected_revision_rule"]
        if rule == "exact" and selected != reviewed:
            raise CompositionError(f"{key} source must equal reviewed revision {reviewed}")
        if rule == "reviewed-revision-or-descendant":
            result = run(
                ["git", "-C", str(repo), "merge-base", "--is-ancestor", reviewed, selected],
                check=False,
            )
            if result.returncode != 0:
                raise CompositionError(f"{key} source does not descend from reviewed revision {reviewed}")
        revisions[key] = selected
    return revisions


def normalized_operator(value: str) -> str:
    candidate = re.sub(r"[^a-z0-9-]+", "-", value.casefold()).strip("-")
    candidate = re.sub(r"-{2,}", "-", candidate)
    if not OPERATOR_PATTERN.fullmatch(candidate):
        raise CompositionError("operator must normalize to a Kubernetes-safe identifier")
    return candidate


def participant_namespace(root: Path, participant: dict[str, Any], operator: str) -> str:
    profile = yaml.safe_load((repo_root(root, participant) / participant["profile_path"]).read_text())
    template = profile.get("runtime", {}).get("namespace_pattern", "devint-{profile}-{operator}")
    if not isinstance(template, str) or template.count("{operator}") != 1 or template.count("{profile}") > 1:
        raise CompositionError(f"profile {participant['profile_id']} has no bounded namespace pattern")
    namespace = re.sub(
        r"-{2,}",
        "-",
        re.sub(
            r"[^a-z0-9-]+",
            "-",
            template.format(profile=participant["profile_id"], operator=operator).casefold(),
        ),
    ).strip("-")[:63]
    if len(namespace) > 63 or not OPERATOR_PATTERN.fullmatch(namespace):
        raise CompositionError(f"profile {participant['profile_id']} rendered an invalid namespace")
    return namespace


def kubectl_command() -> list[str]:
    return shlex.split(os.environ.get("DEVINT_KUBECTL", "k3s kubectl"))


def kubectl(args: list[str], *, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return run([*kubectl_command(), *args], check=check, input_text=input_text)


def deployment_json(namespace: str, deployment: str) -> dict[str, Any]:
    result = kubectl(["-n", namespace, "get", "deployment", deployment, "-o", "json"])
    return json.loads(result.stdout)


def deployment_environment(payload: dict[str, Any], container_name: str) -> dict[str, dict[str, Any]]:
    containers = payload.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
    matches = [item for item in containers if item.get("name") == container_name]
    if len(matches) != 1:
        raise CompositionError(f"deployment does not contain exact container {container_name}")
    return {item["name"]: item for item in matches[0].get("env", []) if isinstance(item, dict) and item.get("name")}


def state_root(root: Path, operator: str) -> Path:
    target = root / ".dev-integration" / "compositions" / "lifecycle-context" / operator
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(target, 0o700)
    return target


def read_state(path: Path) -> dict[str, Any] | None:
    state_path = path / "current.json"
    if not state_path.exists():
        return None
    if state_path.is_symlink() or not stat.S_ISREG(state_path.stat().st_mode):
        raise CompositionError("composition state must be a regular file")
    value = json.loads(state_path.read_text(encoding="utf-8"))
    if value.get("composition_id") != "lifecycle-context":
        raise CompositionError("composition state is owned by another composition")
    return value


def write_private_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def record_receipt(path: Path, action: str, state: dict[str, Any], evidence: dict[str, Any]) -> Path:
    receipt = {
        "schema_version": 1,
        "artifact_type": "lifecycle_context_composition_receipt",
        "composition_id": "lifecycle-context",
        "action": action,
        "outcome": "succeeded",
        "recorded_at": now_utc(),
        "operator": state["operator"],
        "generation": state["generation"],
        "lifecycle": state["lifecycle"],
        "source_revisions": state["source_revisions"],
        "secret_digest": state.get("secret_digest"),
        "secret_values_embedded": False,
        "evidence": evidence,
    }
    digest = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    receipt["digest"] = f"sha256:{digest}"
    receipt_path = path / "receipts" / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{action}.json"
    write_private_json(receipt_path, receipt)
    return receipt_path


def apply_secret(namespace: str, name: str, key: str, value: str) -> None:
    manifest = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": name, "namespace": namespace, "labels": {"governance.workspace/composition": "lifecycle-context"}},
        "type": "Opaque",
        "data": {key: base64.b64encode(value.encode()).decode()},
    }
    kubectl(["apply", "-f", "-"], input_text=json.dumps(manifest))


def set_environment(namespace: str, deployment: str, values: dict[str, str], secret_name: str) -> None:
    literals = [f"{key}={value}" for key, value in sorted(values.items())]
    kubectl(["-n", namespace, "set", "env", f"deployment/{deployment}", *literals])
    kubectl(["-n", namespace, "set", "env", f"deployment/{deployment}", f"--from=secret/{secret_name}"])
    kubectl(["-n", namespace, "rollout", "restart", f"deployment/{deployment}"])
    kubectl(["-n", namespace, "rollout", "status", f"deployment/{deployment}", "--timeout=240s"])


def remove_binding(definition: dict[str, Any], namespaces: dict[str, str]) -> None:
    binding = definition["binding"]
    for key in ("oos", "cgg"):
        participant = definition["participants"][key]
        removals = [f"{name}-" for name in sorted(LIFECYCLE_ENVIRONMENTS[key])]
        deployment = participant["deployment"]
        result = kubectl(["-n", namespaces[key], "get", "deployment", deployment], check=False)
        if result.returncode == 0:
            kubectl(["-n", namespaces[key], "set", "env", f"deployment/{deployment}", *removals])
            kubectl(["-n", namespaces[key], "rollout", "status", f"deployment/{deployment}", "--timeout=240s"])
        secret_name = binding[f"{key}_secret_name"]
        kubectl(["-n", namespaces[key], "delete", "secret", secret_name, "--ignore-not-found=true"])


def live_status(definition: dict[str, Any], namespaces: dict[str, str]) -> dict[str, Any]:
    binding = definition["binding"]
    participants: dict[str, Any] = {}
    for key, participant in definition["participants"].items():
        payload = deployment_json(namespaces[key], participant["deployment"])
        environment = deployment_environment(payload, participant["container"])
        expected = LIFECYCLE_ENVIRONMENTS[key]
        secret = kubectl(
            ["-n", namespaces[key], "get", "secret", binding[f"{key}_secret_name"]],
            check=False,
        )
        available = int(payload.get("status", {}).get("availableReplicas") or 0)
        participants[key] = {
            "namespace": namespaces[key],
            "deployment": participant["deployment"],
            "available": available > 0,
            "binding_environment_present": sorted(name for name in expected if name in environment),
            "binding_secret_present": secret.returncode == 0,
        }
    active = all(
        value["available"]
        and value["binding_secret_present"]
        and len(value["binding_environment_present"]) == len(LIFECYCLE_ENVIRONMENTS[key])
        for key, value in participants.items()
    )
    return {"active": active, "participants": participants}


def oos_request(namespace: str, work_item_id: str, context: dict[str, Any]) -> dict[str, Any]:
    script = r'''
import {readFileSync} from "node:fs";
const request = JSON.parse(readFileSync(0, "utf8"));
const callerId = "operator:workspace-owner";
const secrets = JSON.parse(process.env.CALLER_AUTH_SECRETS_JSON || "{}");
const response = await fetch(`http://127.0.0.1:8080/v1/delivery-work-items/${request.work_item_id}/work-session/context`, {
  method: "POST",
  headers: {
    "content-type": "application/json",
    "x-oos-caller-id": callerId,
    "x-oos-caller-secret": secrets[callerId] || "",
    "x-oos-operator-id": callerId,
  },
  body: JSON.stringify({context: request.context}),
});
let payload = null;
try { payload = await response.json(); } catch {}
const safe = payload && response.ok ? {
  mode: payload.mode,
  replayed: payload.replayed,
  binding: payload.binding,
  measurements: payload.measurements,
  authority: payload.authority,
} : {error: payload?.error || payload?.code || null, message: payload?.message || null};
process.stdout.write(JSON.stringify({status: response.status, body: safe}));
'''
    payload = json.dumps({"work_item_id": work_item_id, "context": context})
    result = kubectl(
        ["-n", namespace, "exec", "-i", "deploy/operator-orchestration-service", "--", "node", "--input-type=module", "-e", script],
        input_text=payload,
    )
    return json.loads(result.stdout)


def context_request(request_id: str, mode: str = "packet", *, budget: int = 3000, reason: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "request_id": request_id,
        "execution_id": f"platform-proof-{request_id}",
        "operation": "continue",
        "mode": mode,
        "budget_tokens": budget,
        "fallback_reason": reason,
    }


def require_http(result: dict[str, Any], expected: int | set[int], label: str) -> None:
    allowed = {expected} if isinstance(expected, int) else expected
    if result.get("status") not in allowed:
        raise CompositionError(f"{label} returned HTTP {result.get('status')}: {result.get('body')}")


def command_validate(definition: dict[str, Any], root: Path) -> int:
    revisions = verify_source_boundary(definition, root)
    print(f"Lifecycle context composition valid; oos={revisions['oos']} cgg={revisions['cgg']}")
    return 0


def command_up(definition: dict[str, Any], root: Path, operator: str) -> int:
    revisions = verify_source_boundary(definition, root)
    namespaces = {key: participant_namespace(root, value, operator) for key, value in definition["participants"].items()}
    for key, participant in definition["participants"].items():
        deployment_json(namespaces[key], participant["deployment"])
    state_dir = state_root(root, operator)
    previous = read_state(state_dir)
    generation = int((previous or {}).get("generation") or 0) + 1
    credential = secrets.token_urlsafe(48)
    digest = f"sha256:{hashlib.sha256(credential.encode()).hexdigest()}"
    if previous and digest == previous.get("secret_digest"):
        raise CompositionError("rotated lifecycle credential repeated the prior digest")
    binding = definition["binding"]
    apply_secret(namespaces["cgg"], binding["cgg_secret_name"], binding["cgg_secret_key"], credential)
    apply_secret(namespaces["oos"], binding["oos_secret_name"], binding["oos_secret_key"], credential)
    try:
        cgg_values = dict(binding["cgg_environment"])
        oos_values = {
            key: value.format(cgg_namespace=namespaces["cgg"])
            for key, value in binding["oos_environment"].items()
        }
        set_environment(namespaces["cgg"], definition["participants"]["cgg"]["deployment"], cgg_values, binding["cgg_secret_name"])
        set_environment(namespaces["oos"], definition["participants"]["oos"]["deployment"], oos_values, binding["oos_secret_name"])
        observed = live_status(definition, namespaces)
        if not observed["active"]:
            raise CompositionError("lifecycle context binding did not become ready")
    except Exception:
        remove_binding(definition, namespaces)
        raise
    state = {
        "schema_version": 1,
        "composition_id": "lifecycle-context",
        "operator": operator,
        "generation": generation,
        "lifecycle": "active",
        "updated_at": now_utc(),
        "namespaces": namespaces,
        "source_revisions": revisions,
        "secret_digest": digest,
        "secret_values_embedded": False,
    }
    write_private_json(state_dir / "current.json", state)
    receipt = record_receipt(state_dir, "up", state, observed)
    print(f"Lifecycle context composition active; generation={generation} receipt={receipt}")
    return 0


def command_status(definition: dict[str, Any], root: Path, operator: str) -> int:
    state_dir = state_root(root, operator)
    state = read_state(state_dir)
    if state is None:
        print("Lifecycle context composition state: absent")
        return 3
    observed = live_status(definition, state["namespaces"])
    expected_active = state["lifecycle"] == "active"
    if observed["active"] != expected_active:
        raise CompositionError("recorded lifecycle does not match the live binding")
    print(json.dumps({"composition_id": "lifecycle-context", "lifecycle": state["lifecycle"], "generation": state["generation"], **observed}, indent=2, sort_keys=True))
    return 0


def command_smoke(definition: dict[str, Any], root: Path, operator: str, work_item_id: str) -> int:
    state_dir = state_root(root, operator)
    state = read_state(state_dir)
    if state is None or state.get("lifecycle") != "active":
        raise CompositionError("composition must be active before smoke")
    namespaces = state["namespaces"]
    status = live_status(definition, namespaces)
    if not status["active"]:
        raise CompositionError("composition live binding is not ready")
    generation = state["generation"]
    proof_run_id = secrets.token_hex(6)
    prefix = f"platform-1167-g{generation}-{proof_run_id}"
    packet = context_request(f"{prefix}-packet")
    first = oos_request(namespaces["oos"], work_item_id, packet)
    require_http(first, 200, "packet projection")
    replay = oos_request(namespaces["oos"], work_item_id, packet)
    require_http(replay, 200, "identical replay")
    if replay["body"].get("replayed") is not True:
        raise CompositionError("identical lifecycle request did not replay")
    conflict_request = dict(packet)
    conflict_request["budget_tokens"] = 2999
    conflict = oos_request(namespaces["oos"], work_item_id, conflict_request)
    require_http(conflict, {409}, "conflicting replay")
    denied = oos_request(namespaces["oos"], work_item_id, context_request(f"{prefix}-denied", budget=8001))
    require_http(denied, {400, 413, 422}, "request validation denial")
    raw = oos_request(
        namespaces["oos"],
        work_item_id,
        context_request(
            f"{prefix}-raw",
            mode="raw-fallback",
            reason="Platform controlled proof of explicit measured raw fallback; no model use.",
        ),
    )
    require_http(raw, 200, "explicit raw fallback")
    if raw["body"].get("mode") != "raw-fallback":
        raise CompositionError("raw fallback did not remain explicit")

    cgg_deployment = definition["participants"]["cgg"]["deployment"]
    try:
        kubectl(["-n", namespaces["cgg"], "scale", f"deployment/{cgg_deployment}", "--replicas=0"])
        kubectl(["-n", namespaces["cgg"], "rollout", "status", f"deployment/{cgg_deployment}", "--timeout=120s"])
        unavailable = oos_request(namespaces["oos"], work_item_id, context_request(f"{prefix}-gateway-loss"))
        require_http(unavailable, {502, 503}, "gateway-loss denial")
    finally:
        kubectl(["-n", namespaces["cgg"], "scale", f"deployment/{cgg_deployment}", "--replicas=1"])
        kubectl(["-n", namespaces["cgg"], "rollout", "status", f"deployment/{cgg_deployment}", "--timeout=240s"])

    for key in ("cgg", "oos"):
        deployment = definition["participants"][key]["deployment"]
        kubectl(["-n", namespaces[key], "rollout", "restart", f"deployment/{deployment}"])
        kubectl(["-n", namespaces[key], "rollout", "status", f"deployment/{deployment}", "--timeout=240s"])
    restarted = oos_request(namespaces["oos"], work_item_id, packet)
    require_http(restarted, 200, "restart replay")
    if restarted["body"].get("replayed") is not True:
        raise CompositionError("packet replay was not preserved across restart")
    measurements = restarted["body"].get("measurements") or {}
    if measurements.get("packet_count", 0) < 1 or measurements.get("raw_fallback_count", 0) < 1 or measurements.get("denied_count", 0) < 1:
        raise CompositionError("lifecycle context measurements do not cover packet, raw fallback, and denial")
    evidence = {
        "proof_run_id": proof_run_id,
        "packet": {"status": first["status"], "replayed": first["body"].get("replayed")},
        "identical_replay": {"status": replay["status"], "replayed": replay["body"].get("replayed")},
        "conflicting_replay": {"status": conflict["status"]},
        "request_validation_denial": {"status": denied["status"]},
        "raw_fallback": {"status": raw["status"], "mode": raw["body"].get("mode")},
        "gateway_loss": {"status": unavailable["status"]},
        "restart_replay": {"status": restarted["status"], "replayed": restarted["body"].get("replayed")},
        "measurements": measurements,
        "secret_values_embedded": False,
    }
    receipt = record_receipt(state_dir, "smoke", state, evidence)
    print(f"Lifecycle context composition smoke passed; receipt={receipt}")
    return 0


def command_stop(definition: dict[str, Any], root: Path, operator: str, action: str) -> int:
    state_dir = state_root(root, operator)
    state = read_state(state_dir)
    if state is None:
        print("Lifecycle context composition already absent")
        return 0
    remove_binding(definition, state["namespaces"])
    state["lifecycle"] = "suspended" if action == "suspend" else "inactive"
    state["updated_at"] = now_utc()
    observed = live_status(definition, state["namespaces"])
    if observed["active"]:
        raise CompositionError("lifecycle binding remains active after teardown")
    denied = oos_request(
        state["namespaces"]["oos"],
        definition["commissioning_proof"]["work_item_id"],
        context_request(
            f"platform-{definition['commissioning_proof']['work_item_id']}-"
            f"g{state['generation']}-{action}-inactive"
        ),
    )
    require_http(denied, {503}, f"{action} fail-closed proof")
    write_private_json(state_dir / "current.json", state)
    receipt = record_receipt(
        state_dir,
        action,
        state,
        {
            **observed,
            "post_action_request": {"status": denied["status"], "error": denied["body"].get("error")},
        },
    )
    print(f"Lifecycle context composition {state['lifecycle']}; receipt={receipt}")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("validate", "up", "status", "smoke", "suspend", "down", "rollback"))
    parser.add_argument("--operator", default=os.environ.get("USER", "operator"))
    parser.add_argument("--work-item-id", default="1167")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        definition = load_definition()
        root = workspace_root()
        operator = normalized_operator(args.operator)
        if args.action == "validate":
            return command_validate(definition, root)
        if args.action == "up":
            return command_up(definition, root, operator)
        if args.action == "status":
            return command_status(definition, root, operator)
        if args.action == "smoke":
            return command_smoke(definition, root, operator, args.work_item_id)
        return command_stop(definition, root, operator, args.action)
    except (CompositionError, json.JSONDecodeError, OSError, KeyError, TypeError, ValueError) as exc:
        print(f"Lifecycle context composition failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
