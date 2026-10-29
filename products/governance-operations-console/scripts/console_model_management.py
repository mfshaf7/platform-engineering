#!/usr/bin/env python3
"""Platform composition for the existing governed model-management owner."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import tempfile

import yaml

ACCOUNT_PATH = "components/governed-ai-gateway/dev-integration/codex-account"
VAULT_POLICY = "governed-ai-codex-account"
GATEWAY_SECRET = "governed-ai-model-management"
OOS_SECRET = "governed-ai-model-management-caller"
IMAGE_REPOSITORY = "ghcr.io/mfshaf7/governed-ai-runtime"
TASK_PROFILES = {
    "intake-classifier-v1", "delivery-work-design-advisor-v1",
    "delivery-refinement-advisor-v1", "agent-console-assistant-v1",
    "source-realization-v1", "prototype-source-authoring-v1",
}


class ModelCompositionError(RuntimeError):
    pass


def validate(policy):
    value = policy.get("model_management")
    if not isinstance(value, dict) or set(value) != {"enabled", "codex_version", "codex_sha256", "base_image", "memory_limit", "cpu_limit"}:
        raise ModelCompositionError("The model-management composition policy is incomplete.")
    if (value["enabled"] is not True or value["codex_version"] != "0.163.0"
            or value["codex_sha256"] != "399ff69c431c066e40de318fba45c2b07f45a76b19939d247ee4828fc70c4215"
            or value["base_image"] != "python@sha256:46cb7cc2877e60fbd5e21a9ae6115c30ace7a077b9f8772da879e4590c18c2e3"
            or value["memory_limit"] != "1Gi" or value["cpu_limit"] != "1"):
        raise ModelCompositionError("The model-management executable, image or resource boundary changed.")
    return value


def enabled(policy):
    return policy.get("model_management", {}).get("enabled") is True


def owner_json(raw):
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, TypeError):
        raise ModelCompositionError("The model credential owner returned invalid evidence.") from None


def account_lease(value, expected_token=None):
    auth = value.get("auth")
    if (not isinstance(auth, dict) or not isinstance(auth.get("policies"), list)
            or set(auth["policies"]) != {"default", VAULT_POLICY} or auth.get("renewable") is not True
            or expected_token is not None and auth.get("client_token") != expected_token):
        raise ModelCompositionError("The dedicated account credential has unexpected authority.")
    return auth


def private_write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink() or path.parent.is_symlink():
        raise ModelCompositionError("Private model-management state must not follow symlinks.")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(value)


def image_name(policy):
    value = validate(policy)
    inputs = {key: value[key] for key in ("base_image", "codex_version", "codex_sha256")}
    digest = hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return IMAGE_REPOSITORY + ":inputs-" + digest


def image_labels(value):
    return {"org.opencontainers.image.source": "https://github.com/mfshaf7/platform-engineering",
            "governed-ai.base-image": value["base_image"],
            "governed-ai.codex-version": value["codex_version"],
            "governed-ai.codex-sha256": value["codex_sha256"]}


def published_image(value, tag, run):
    run(["docker", "pull", tag])
    actual = owner_json(run(["docker", "image", "inspect", tag, "--format", "{{json .}}"]).stdout)
    labels = actual.get("Config", {}).get("Labels") or {}
    if any(labels.get(key) != expected for key, expected in image_labels(value).items()):
        raise ModelCompositionError("The published runtime image has different accepted inputs or source ownership.")
    digests = [item for item in actual.get("RepoDigests", []) if item.startswith(IMAGE_REPOSITORY + "@sha256:")]
    if len(digests) != 1 or len(digests[0].rsplit(":", 1)[-1]) != 64 or any(
            c not in "0123456789abcdef" for c in digests[0].rsplit(":", 1)[-1]):
        raise ModelCompositionError("The published runtime image has no exact immutable registry digest.")
    immutable = digests[0]
    run(["docker", "pull", value["base_image"]])
    base = owner_json(run(["docker", "image", "inspect", value["base_image"], "--format", "{{json .}}"]).stdout)
    base_layers = base.get("RootFS", {}).get("Layers")
    actual_layers = actual.get("RootFS", {}).get("Layers")
    if not base_layers or not actual_layers or actual_layers[:-1] != base_layers:
        raise ModelCompositionError("The published runtime image does not extend the exact accepted base with its executable layer.")
    observed = run(["docker", "run", "--rm", "--network=none", "--read-only", "--cap-drop=ALL", immutable,
                    "sha256sum", "/usr/local/bin/codex"]).stdout.split()
    if not observed or observed[0] != value["codex_sha256"]:
        raise ModelCompositionError("The published runtime executable differs from the accepted digest.")
    return immutable


def build_image(policy, repo_root, run, *, import_image=False):
    value = validate(policy)
    tag = image_name(policy)
    if import_image:
        # This fresh Docker configuration has no provider login or credential
        # helper. Prove the same anonymous pull that the node must perform.
        with tempfile.TemporaryDirectory(prefix="governed-image-anonymous-") as directory:
            def anonymous(command, **kwargs):
                return run([command[0], "--config", directory, *command[1:]], **kwargs)
            return published_image(value, tag, anonymous)
    binary = Path.home() / ".codex/packages/standalone/releases" / (value["codex_version"] + "-x86_64-unknown-linux-musl/bin/codex")
    if not binary.is_file():
        raise ModelCompositionError("Install the exact accepted Codex executable before commissioning.")
    with binary.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != value["codex_sha256"]:
            raise ModelCompositionError("The installed Codex executable differs from the accepted digest.")
    found = run(["docker", "image", "inspect", tag], check=False)
    if found.returncode:
        with tempfile.TemporaryDirectory(prefix="governed-model-image-") as directory:
            root = Path(directory)
            shutil.copyfile(binary, root / "codex")
            (root / "codex").chmod(0o755)
            (root / "Dockerfile").write_text(
                "FROM " + value["base_image"] + "\nCOPY --chmod=0555 codex /usr/local/bin/codex\n"
                "USER 1000:1000\n")
            labels = [argument for key, item in image_labels(value).items() for argument in ("--label", key + "=" + item)]
            run(["docker", "build", "--network=none", *labels, "--tag", tag, str(root)])
    observed = run(["docker", "run", "--rm", "--network=none", "--read-only", "--cap-drop=ALL", tag,
                    "sha256sum", "/usr/local/bin/codex"]).stdout.split()
    if not observed or observed[0] != value["codex_sha256"]:
        raise ModelCompositionError("The actual runtime image executable differs from the accepted digest.")
    return tag


def owner_policy(repo_root, operator_id):
    profiles = yaml.safe_load((repo_root / "security/governed-ai-model-profiles.yaml").read_text())["model_profiles"]
    if set(profiles) != TASK_PROFILES:
        raise ModelCompositionError("Review the changed profile/data boundary before commissioning.")
    tasks = sorted(name + "/" + task for name, profile in profiles.items() for task in profile["task_contracts"]["allowed"])
    value = {
        "schema_version": 1, "caller_id": "operator-orchestration-service", "operator_id": operator_id,
        "token_file": "/run/model-management/management-token", "backends": {
            "local-ollama": {"provider": "ollama", "endpoint_origin": "http://host.docker.internal:11434", "allowed_tasks": tasks},
            "managed-codex": {"provider": "codex-app-server", "executable": "/usr/local/bin/codex",
                "executable_digest": validate(yaml.safe_load((repo_root / "products/governance-operations-console/complete-runtime-policy.yaml").read_text()))["codex_sha256"],
                "vault": {"address": "http://vault.vault.svc.cluster.local:8200", "mount": "kv", "path": ACCOUNT_PATH,
                          "token_file": "/run/model-management/vault-token"}, "allowed_tasks": tasks},
        },
    }
    return value


def secret_document(namespace, name, data):
    return {"apiVersion": "v1", "kind": "Secret", "metadata": {"namespace": namespace, "name": name,
        "labels": {"app.kubernetes.io/managed-by": "platform-engineering"}}, "type": "Opaque",
        "data": {key: base64.b64encode(value.encode()).decode() for key, value in data.items()}}


def prepare(policy, *, repo_root, state_root, operator_id, gateway_namespace, run, vault_token):
    """Called only after exact source and Security acceptance, before composition."""
    if not enabled(policy):
        return
    validate(policy)
    if policy.get("security", {}).get("status") != "accepted" or policy["security"].get("gate_id") != "gate:ai-routing-composed-security":
        raise ModelCompositionError("Exact composed Security acceptance is required before model runtime effects.")
    image = build_image(policy, repo_root, run, import_image=True)
    root = state_root / "private/model-management"
    if root.is_symlink():
        raise ModelCompositionError("Private model-management state must not follow symlinks.")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    management = root / "management-token"
    if not management.exists():
        private_write(management, secrets.token_urlsafe(48))
    if management.is_symlink() or management.stat().st_mode & 0o077:
        raise ModelCompositionError("The management credential projection is unsafe.")
    account_token = root / "vault-token"
    existed = account_token.exists()
    if account_token.is_symlink() or existed and account_token.stat().st_mode & 0o077:
        raise ModelCompositionError("The dedicated account credential projection is unsafe.")
    if not existed:
        # Retain the intended owner credential before issuance. An uncertain
        # response can only reconcile this same Vault token ID, never mint a
        # second orphan with an undiscoverable random identity.
        private_write(account_token, "model-owner-" + secrets.token_hex(32))
    def vault(command, token, payload=None, *, check=True):
        # Credentials travel only on stdin. No inherited root token reaches a
        # pod, process argument, image, receipt, Console or OOS environment.
        script = 'IFS= read -r VAULT_TOKEN; export VAULT_TOKEN VAULT_ADDR=http://127.0.0.1:8200; exec vault "$@"'
        return run(["k3s", "kubectl", "-n", "vault", "exec", "-i", "vault-0", "--", "sh", "-c", script, "model-vault", *command],
                   input_value=token + "\n" + (payload or ""), check=check)
    renewed = None
    if existed:
        renewed = vault(["token", "renew", "-format=json"], account_token.read_text().strip(), check=False)
    if renewed is None or renewed.returncode:
        rule = 'path "kv/data/' + ACCOUNT_PATH + '" { capabilities = ["create", "read", "update"] }\n'
        vault(["policy", "write", VAULT_POLICY, "-"], vault_token(), rule)
        issued = owner_json(vault(["write", "-format=json", "auth/token/create", "policies=" + VAULT_POLICY,
                                  "period=24h", "renewable=true", "no_parent=true", "id=-"],
                                 vault_token(), account_token.read_text().strip()).stdout)
        account_lease(issued, account_token.read_text().strip())
    else:
        account_lease(owner_json(renewed.stdout))
    document = secret_document(gateway_namespace, GATEWAY_SECRET, {"management-token": management.read_text(), "vault-token": account_token.read_text()})
    run(["k3s", "kubectl", "apply", "-f", "-"], input_value=json.dumps(document))
    overlay = {"image": image, "owner_policy": owner_policy(repo_root, operator_id),
               "memory_limit": policy["model_management"]["memory_limit"], "cpu_limit": policy["model_management"]["cpu_limit"]}
    path = root / "overlay.json"
    private_write(path, json.dumps(overlay))
    os.environ["DEVINT_GAI_MODEL_MANAGEMENT_OVERLAY"] = str(path)


def patch_manifest(manifest, overlay):
    """Extend the existing gateway; provider credentials are gateway-only."""
    docs = list(yaml.safe_load_all(manifest))
    if set(overlay) != {"image", "owner_policy", "memory_limit", "cpu_limit"}:
        raise ModelCompositionError("The managed runtime overlay is incomplete.")
    config = next(row for row in docs if row and row["kind"] == "ConfigMap" and row["metadata"]["name"] == "governed-ai-gateway-app")
    config["data"]["model-management-policy.json"] = json.dumps(overlay["owner_policy"])
    deploy = next(row for row in docs if row and row["kind"] == "Deployment" and row["metadata"]["name"] == "governed-ai-gateway")
    # The retained journal and provider slots have one process owner. Stop the
    # preceding writer before handing legacy root-owned audit bytes to UID1000.
    deploy["spec"]["strategy"] = {"type": "Recreate", "rollingUpdate": None}
    spec = deploy["spec"]["template"]["spec"]
    spec["automountServiceAccountToken"] = False
    spec["securityContext"] = {"runAsNonRoot": True, "runAsUser": 1000, "runAsGroup": 1000, "fsGroup": 1000,
                               "fsGroupChangePolicy": "OnRootMismatch", "seccompProfile": {"type": "RuntimeDefault"}}
    container = spec["containers"][0]
    container.update(image=overlay["image"], imagePullPolicy="IfNotPresent", resources={"requests": {"cpu": "100m", "memory": "128Mi"},
        "limits": {"cpu": overlay["cpu_limit"], "memory": overlay["memory_limit"], "ephemeral-storage": "1Gi"}},
        securityContext={"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}})
    container.setdefault("readinessProbe", {"httpGet": {"port": 8080}})["httpGet"]["path"] = "/healthz"
    container["env"].append({"name": "GOVERNED_AI_MODEL_MANAGEMENT_POLICY_PATH", "value": "/app/model-management-policy.json"})
    # Reuse the renderer's actual resolved host route, rather than assuming
    # host.docker.internal resolves inside every pod.
    local = next(item["value"] for item in container["env"] if item["name"] == "GOVERNED_AI_OLLAMA_BASE_URL")
    overlay["owner_policy"]["backends"]["local-ollama"]["endpoint_origin"] = local
    config["data"]["model-management-policy.json"] = json.dumps(overlay["owner_policy"])
    spec["volumes"].extend([
        {"name": "model-owner-secret", "secret": {"secretName": GATEWAY_SECRET, "defaultMode": 0o444}},
        {"name": "model-owner-projection", "emptyDir": {"medium": "Memory", "sizeLimit": "2Mi"}},
        {"name": "model-tmp", "emptyDir": {"medium": "Memory", "sizeLimit": "128Mi"}},
    ])
    container["volumeMounts"].extend([{"name": "model-owner-projection", "mountPath": "/run/model-management", "readOnly": True},
                                     {"name": "model-tmp", "mountPath": "/tmp"}])
    spec["initContainers"] = [{"name": "model-owner-projection", "image": overlay["image"], "imagePullPolicy": "IfNotPresent",
        "command": ["python", "-c", "from pathlib import Path; import os; [(Path('/projection', n).write_bytes(Path('/secret', n).read_bytes()), os.chmod('/projection/'+n, 0o600)) for n in ('management-token','vault-token')]"],
        "securityContext": {"allowPrivilegeEscalation": False, "readOnlyRootFilesystem": True, "capabilities": {"drop": ["ALL"]}},
        "resources": {"requests": {"cpu": "10m", "memory": "16Mi"}, "limits": {"cpu": "100m", "memory": "64Mi"}},
        "volumeMounts": [{"name": "model-owner-secret", "mountPath": "/secret", "readOnly": True},
                         {"name": "model-owner-projection", "mountPath": "/projection"}]}]
    egress = next(row for row in docs if row and row["kind"] == "NetworkPolicy" and row["metadata"]["name"] == "governed-ai-gateway-provider-egress")
    egress["spec"]["egress"].extend([
        {"to": [{"namespaceSelector": {"matchLabels": {"kubernetes.io/metadata.name": "vault"}},
                 "podSelector": {"matchLabels": {"app.kubernetes.io/name": "vault"}}}], "ports": [{"protocol": "TCP", "port": 8200}]},
        {"to": [{"ipBlock": {"cidr": "0.0.0.0/0", "except": ["0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
            "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16", "224.0.0.0/4", "240.0.0.0/4"]}}],
         "ports": [{"protocol": "TCP", "port": 443}]},
    ])
    return yaml.safe_dump_all(docs, sort_keys=False)


def bind_oos(policy, *, state_root, namespace, operator_id, run):
    if not enabled(policy):
        return
    token = (state_root / "private/model-management/management-token").read_text()
    run(["k3s", "kubectl", "apply", "-f", "-"], input_value=json.dumps(secret_document(namespace, OOS_SECRET, {"management-token": token})))
    gateway_namespace = "devint-governed-ai-gateway-" + namespace.removeprefix("devint-accepted-idea-delivery-")
    env = {"OOS_MODEL_OPERATIONS_ENABLED": "true", "OOS_MODEL_OPERATIONS_STATE_ROOT": "/var/lib/oos/platform-operation/model-operations",
           "OOS_MODEL_OPERATIONS_PLATFORM_BASE_URL": "http://governed-ai-gateway." + gateway_namespace + ".svc.cluster.local:8080",
           "OOS_MODEL_OPERATIONS_MANAGEMENT_TOKEN_FILE": "/run/model-management/management-token",
           "OOS_MODEL_OPERATIONS_CALLER_OPERATOR_BINDINGS_JSON": json.dumps({"governance-operations-console": operator_id})}
    patch = {"spec": {"template": {"spec": {"containers": [{"name": "operator-orchestration-service",
        "env": [{"name": key, "value": value} for key, value in env.items()],
        "volumeMounts": [{"name": "model-management-caller", "mountPath": "/run/model-management", "readOnly": True}]}],
        "volumes": [{"name": "model-management-caller", "secret": {"secretName": OOS_SECRET, "defaultMode": 0o444}}]}}}}
    run(["k3s", "kubectl", "-n", namespace, "patch", "deployment", "operator-orchestration-service", "--type=strategic", "--patch-file=/dev/stdin"], input_value=json.dumps(patch))
    run(["k3s", "kubectl", "-n", namespace, "rollout", "status", "deployment/operator-orchestration-service", "--timeout=180s"])


def refresh_health(*, operator_id, gateway_namespace, run):
    """Only the post-core observation path invokes this finite owner request."""
    script = """import json,urllib.request
from pathlib import Path
policy=json.loads(Path('/app/model-management-policy.json').read_text())
request=urllib.request.Request('http://127.0.0.1:8080/v1/model-management/health',data=b'{}',headers={
 'Content-Type':'application/json','Authorization':'Bearer '+Path(policy['token_file']).read_text().strip(),
 'X-Platform-Caller':policy['caller_id'],'X-Platform-Operator':policy['operator_id']})
with urllib.request.urlopen(request,timeout=40) as response:
 value=json.loads(response.read(1048577))
 print(json.dumps({'checked_at':value['checked_at'],'configuration_revision':value['configuration_revision']}))
"""
    try:
        result = run(["k3s", "kubectl", "-n", gateway_namespace, "exec", "deployment/governed-ai-gateway", "--",
                      "python", "-c", script], check=False)
        if result.returncode:
            return {"state": "unknown", "code": "provider-observation-unavailable"}
        value = owner_json(result.stdout)
        return {"state": "checked", **value}
    except (OSError, ValueError, ModelCompositionError):
        return {"state": "unknown", "code": "provider-observation-unavailable"}


def renew_account_lease(*, state_root, run):
    path = state_root / "private/model-management/vault-token"
    if not path.is_file() or path.is_symlink() or path.stat().st_mode & 0o077:
        raise ModelCompositionError("The dedicated account lease requires owner recovery.")
    script = 'IFS= read -r VAULT_TOKEN; export VAULT_TOKEN VAULT_ADDR=http://127.0.0.1:8200; exec vault token renew -format=json'
    result = run(["k3s", "kubectl", "-n", "vault", "exec", "-i", "vault-0", "--", "sh", "-c", script], input_value=path.read_text().strip() + "\n")
    account_lease(owner_json(result.stdout))


def disable(policy, *, state_root, namespace, run):
    if not enabled(policy):
        return
    gateway_namespace = "devint-governed-ai-gateway-" + namespace.removeprefix("devint-accepted-idea-delivery-")
    for ns, deployment, container, volumes, environment in [
        (namespace, "operator-orchestration-service", "operator-orchestration-service", ["model-management-caller"],
         "OOS_MODEL_OPERATIONS_ENABLED"),
        (gateway_namespace, "governed-ai-gateway", "gateway", ["model-owner-secret", "model-owner-projection"],
         "GOVERNED_AI_MODEL_MANAGEMENT_POLICY_PATH"),
    ]:
        spec = {"containers": [{"name": container, "env": [{"name": environment, "$patch": "delete"}],
            "volumeMounts": [{"mountPath": "/run/model-management", "$patch": "delete"}]}],
            "volumes": [{"name": name, "$patch": "delete"} for name in volumes]}
        if deployment == "governed-ai-gateway":
            spec["initContainers"] = [{"name": "model-owner-projection", "$patch": "delete"}]
        run(["k3s", "kubectl", "-n", ns, "patch", "deployment", deployment, "--type=strategic", "--patch-file=/dev/stdin"],
            input_value=json.dumps({"spec": {"template": {"spec": spec}}}))
        run(["k3s", "kubectl", "-n", ns, "rollout", "status", "deployment/" + deployment, "--timeout=180s"])
    path = state_root / "private/model-management/vault-token"
    if path.exists():
        if path.is_symlink() or path.stat().st_mode & 0o077:
            raise ModelCompositionError("The account lease projection is unsafe.")
        script = 'IFS= read -r VAULT_TOKEN; export VAULT_TOKEN VAULT_ADDR=http://127.0.0.1:8200; exec vault token revoke -self'
        run(["k3s", "kubectl", "-n", "vault", "exec", "-i", "vault-0", "--", "sh", "-c", script], input_value=path.read_text().strip() + "\n")
        path.unlink()
    for ns, name in [(namespace, OOS_SECRET), (gateway_namespace, GATEWAY_SECRET)]:
        run(["k3s", "kubectl", "-n", ns, "delete", "secret", name, "--ignore-not-found=true"])
    network = owner_json(run(["k3s", "kubectl", "-n", gateway_namespace, "get", "networkpolicy",
                              "governed-ai-gateway-provider-egress", "-o", "json"]).stdout)
    rules = [rule for rule in network["spec"]["egress"] if not any(port.get("port") in {443, 8200} for port in rule.get("ports", []))]
    run(["k3s", "kubectl", "-n", gateway_namespace, "patch", "networkpolicy", "governed-ai-gateway-provider-egress",
         "--type=merge", "--patch-file=/dev/stdin"], input_value=json.dumps({"spec": {"egress": rules}}))
    (state_root / "private/model-management/management-token").unlink(missing_ok=True)
    os.environ.pop("DEVINT_GAI_MODEL_MANAGEMENT_OVERLAY", None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["patch-manifest", "build-image", "image-metadata"])
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--overlay", type=Path)
    args = parser.parse_args()
    if args.action == "patch-manifest":
        if not args.manifest or not args.overlay:
            parser.error("The existing rendered manifest and accepted overlay are required.")
        args.manifest.write_text(patch_manifest(args.manifest.read_text(), json.loads(args.overlay.read_text())))
    else:
        import subprocess
        repo = Path(__file__).resolve().parents[3]
        policy = yaml.safe_load((repo / "products/governance-operations-console/complete-runtime-policy.yaml").read_text())
        if args.action == "image-metadata":
            print(json.dumps({"image": image_name(policy), **validate(policy)}))
            return
        def run(command, *, check=True, **kwargs):
            result = subprocess.run(command, capture_output=True, text=True, **kwargs)
            if check and result.returncode:
                raise ModelCompositionError("The bounded runtime image validation failed.")
            return result
        print(build_image(policy, repo, run))


if __name__ == "__main__":
    main()
