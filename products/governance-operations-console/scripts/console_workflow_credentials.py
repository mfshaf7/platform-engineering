"""Renew existing, already-admitted Console workflow identities; never activate them."""
from __future__ import annotations

from argparse import Namespace
import base64
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
import prototype_workflow_identity as prototype_identity
import workspace_intake_identity as intake_identity
from repository_provider_identity import IdentityError, ProviderRepository, load_dev_integration_target, verify_dev_integration_cluster

# Previously commissioned identities. Neither callers nor browser input select Apps,
# destinations, repositories, permissions, or workflow activation.
WORKFLOWS = {
    "proposal-target": (5234872, 169176122),
    "prototype-landing": (4861143, 159774010),
    "prototype-maturity": (4901171, 160690261),
    "prototype-closure": (5007168, 163151088),
    "workspace-intake": (4845505, 159392456),
}
ANNOTATION = "workspace-governance/"
READINESS_WORKFLOWS = ("prototype-landing", "prototype-maturity", "prototype-closure")
READINESS_DEPLOYMENT = "workspace-governance-control-fabric-api"
READINESS_SECRET = READINESS_DEPLOYMENT + "-artifact-registry-callers"


class CredentialError(RuntimeError):
    pass


def validate_policy(policy: dict[str, Any]) -> None:
    if policy.get("workflow_credentials") != {"enabled": True, "required": sorted(WORKFLOWS)}:
        raise CredentialError("complete runtime requires the exact five admitted workflow identities")


class Credentials:
    def __init__(self, *, repo_root: Path, workspace_root: Path, session_manifest: Path,
                 run, private_key, readiness_revision: str | None = None):
        self.repo_root = repo_root
        self.workspace_root = workspace_root
        self.session_manifest = session_manifest
        self.run = run
        self.private_key = private_key
        self.readiness_revision = readiness_revision

    def contract(self, slug: str):
        path = self.repo_root / "security" / f"{slug}-identity.yaml"
        definition = yaml.safe_load(path.read_text())
        loader = intake_identity if slug == "workspace-intake" else prototype_identity
        contract = loader.load_contract(path)
        if slug != "workspace-intake" and not contract.workflow_runtime_enabled:
            raise CredentialError(f"{slug}: owner activation is disabled")
        if slug == "workspace-intake":
            intake_identity.assert_inventory_extension_approved(contract)
        return contract, definition

    def target(self, contract):
        return verify_dev_integration_cluster("k3s kubectl", load_dev_integration_target(
            self.session_manifest, self.workspace_root, contract, require_running=True,
        ))

    def binding(self, slug: str) -> tuple[Any, Any, dict]:
        contract, _ = self.contract(slug)
        target = self.target(contract)
        result = self.run(["k3s", "kubectl", "-n", target.namespace, "get", "secret",
                           contract.runtime_secret_name, "-o", "json"], check=False)
        if result.returncode:
            raise CredentialError(f"{slug}: existing owner identity is missing; use its commissioning procedure")
        try:
            secret = json.loads(result.stdout)
            metadata = secret["metadata"]
            annotations = metadata["annotations"]
            expected = intake_identity.binding_digest(contract, *WORKFLOWS[slug],
                                                       ProviderRepository(contract.repository, contract.repository_id))
            if (metadata["name"] != contract.runtime_secret_name
                    or metadata["namespace"] != target.namespace
                    or metadata["labels"]["app.kubernetes.io/managed-by"] != "platform-engineering"
                    or annotations[ANNOTATION + "credential-binding-digest"] != expected
                    or annotations[ANNOTATION + "dev-integration-profile"] != target.profile_id
                    or not isinstance(metadata["resourceVersion"], str)
                    or not base64.b64decode(secret["data"][contract.runtime_secret_key], validate=True).startswith(b"ghs_")):
                raise ValueError("binding")
        except (KeyError, TypeError, ValueError):
            raise CredentialError(f"{slug}: existing owner identity binding is invalid") from None
        return contract, target, secret

    def readiness_source(self, bindings: dict) -> tuple[str, str]:
        """Prove the already-admitted WGCF principal and its consumed credential.

        This is not a new caller or a secret rotation. These three consumers
        already use the SAME OOS registry principal. Their GitHub identities
        and authoring permissions remain separate and unchanged.
        """
        try:
            if not re.fullmatch(r"[0-9a-f]{40}", self.readiness_revision or ""):
                raise ValueError("exact reviewed WGCF revision required")
            target = bindings[READINESS_WORKFLOWS[0]][1]
            namespace = prototype_identity.runner_owned_readiness_namespace(
                self.workspace_root, target, require_running=True,
            )
            deployment = json.loads(self.run(["k3s", "kubectl", "-n", namespace,
                "get", "deployment", READINESS_DEPLOYMENT, "-o", "json"]).stdout)
            containers = deployment["spec"]["template"]["spec"]["containers"]
            api = next(item for item in containers if item["name"] == "api")
            environment = {item["name"]: item for item in api["env"]}
            if (environment["WGCF_ARTIFACT_REGISTRY_OOS_CALLER_ID"].get("value") != "operator-orchestration-service"
                    or environment["WGCF_ARTIFACT_REGISTRY_OOS_CALLER_SECRET"].get("valueFrom") != {
                        "secretKeyRef": {"name": READINESS_SECRET, "key": "oos-caller-secret"}}):
                raise ValueError("issuer binding")
            for slug in READINESS_WORKFLOWS:
                contract, member_target, _ = bindings[slug]
                if (member_target.namespace != target.namespace
                        or contract.wgcf_caller_id != "operator-orchestration-service"
                        or contract.wgcf_secret_key != "wgcf-caller-secret"
                        or environment["WGCF_" + slug.upper().replace("-", "_") + "_READINESS_ENABLED"].get("value") != "true"):
                    raise ValueError("consumer or activation binding")
            source = json.loads(self.run(["k3s", "kubectl", "-n", namespace,
                "get", "secret", READINESS_SECRET, "-o", "json"]).stdout)
            if (source["metadata"]["name"] != READINESS_SECRET
                    or source["metadata"]["namespace"] != namespace
                    or source["metadata"]["labels"].get("devint.profile") != "governance-control-fabric"
                    or source["metadata"]["labels"].get("app.kubernetes.io/component") != "artifact-registry-auth"):
                raise ValueError("credential source")
            value = base64.b64decode(source["data"]["oos-caller-secret"], validate=True).decode()
            if len(value) < 32 or "\n" in value or "\r" in value:
                raise ValueError("credential shape")
            fingerprint = hashlib.sha256(value.encode()).hexdigest()
            # Only a fingerprint enters argv; only a boolean leaves the pod.
            program = ("import os,hashlib,json; from control_fabric_core.artifact_registry import read_implementation_ref; "
                "print(json.dumps({'consumed': read_implementation_ref() == " + repr(self.readiness_revision) + " and "
                "os.environ.get('WGCF_ARTIFACT_REGISTRY_OOS_CALLER_ID') == 'operator-orchestration-service' and "
                "hashlib.sha256(os.environ.get('WGCF_ARTIFACT_REGISTRY_OOS_CALLER_SECRET','').encode()).hexdigest() == "
                + repr(fingerprint) + "}))")
            observed = self.run(["k3s", "kubectl", "-n", namespace, "exec",
                "deployment/" + READINESS_DEPLOYMENT, "-c", "api", "--", "python3", "-c", program])
            if json.loads(observed.stdout) != {"consumed": True}:
                raise ValueError("issuer consumption")
            return value, f"http://{READINESS_DEPLOYMENT}.{namespace}.svc.cluster.local:8080"
        except Exception:
            raise CredentialError("current admitted WGCF readiness caller source or issuer consumption is unavailable") from None

    def reconcile_readiness(self, bindings: dict) -> dict:
        value, _ = self.readiness_source(bindings)
        encoded = base64.b64encode(value.encode()).decode()
        for slug in READINESS_WORKFLOWS:
            contract, target, secret = bindings[slug]
            if secret["data"].get(contract.wgcf_secret_key) != encoded:
                updated = {**secret, "data": {**secret["data"], contract.wgcf_secret_key: encoded}}
                self._project_binding(slug, contract, target, updated)
        # Fresh resourceVersions identify caller-only delivery and make a crash
        # between replacement and consumption retryable without minting tokens.
        return {slug: self.binding(slug) for slug in WORKFLOWS}

    def probe(self, bindings: dict, *, provider: bool = True) -> dict:
        _, readiness_url = self.readiness_source(bindings)
        specs = []
        for slug, (contract, _, secret) in bindings.items():
            required = {
                contract.token_file_env: f"{contract.runtime_directory}/{contract.runtime_filename}",
                contract.repository_owner_env: contract.repository_owner,
                contract.repository_id_env: str(contract.repository_id),
                "OOS_" + ("PROPOSAL_TARGET_APPLICATION" if slug == "proposal-target" else slug.upper().replace("-", "_")) + "_ENABLED": "true",
            }
            specs.append({"slug": slug, "required": required, "file_env": contract.token_file_env,
                          "repository": contract.repository, "id": contract.repository_id,
                          "token_digest": hashlib.sha256(base64.b64decode(secret["data"][contract.runtime_secret_key], validate=True)).hexdigest()})
            if slug in READINESS_WORKFLOWS:
                required.update({contract.wgcf_base_url_env: readiness_url,
                                 contract.wgcf_caller_id_env: "operator-orchestration-service",
                                 contract.wgcf_implementation_ref_env: self.readiness_revision,
                                 contract.wgcf_service_identity_ref_env: contract.wgcf_service_identity_ref})
                specs[-1]["readiness"] = {
                    "secret_env": contract.wgcf_caller_secret_env,
                    "caller_env": contract.wgcf_caller_id_env,
                    "url_env": contract.wgcf_base_url_env,
                    "secret_digest": hashlib.sha256(base64.b64decode(secret["data"][contract.wgcf_secret_key], validate=True)).hexdigest(),
                }
        # Only the bounded result leaves the pod. Credentials are read in the child
        # environment, never expanded into process arguments, output, or receipts.
        program = r"""
const fs=require('node:fs');
const crypto=require('node:crypto');
const specs=SPECIFICATIONS;
(async()=>{const results={};for(const s of specs){
  if(Object.entries(s.required).some(([k,v])=>process.env[k]!==v))throw Error(s.slug+': owner runtime binding is unavailable');
  const token=fs.readFileSync(process.env[s.file_env],'utf8').trim();
  if(!token.startsWith('ghs_'))throw Error(s.slug+': mounted installation credential is unavailable');
  if(!CHECK_PROVIDER){results[s.slug]={configured:true};continue;}
  if(s.readiness){
    const r=s.readiness;
    if(process.env[r.caller_env]!=='operator-orchestration-service'||
       crypto.createHash('sha256').update(process.env[r.secret_env]??'').digest('hex')!==r.secret_digest)
      throw Error(s.slug+': readiness credential delivery has not been consumed');
    const response=await fetch(process.env[r.url_env]+'/v1/readiness/'+s.slug+'/'+'0'.repeat(64),{
      headers:{'x-wgcf-caller-id':process.env[r.caller_env],'x-wgcf-caller-secret':process.env[r.secret_env]},
      redirect:'error',signal:AbortSignal.timeout(5000)});
    if(response.status!==404)throw Error(s.slug+': bounded readiness authentication read failed');
  }
  if(crypto.createHash('sha256').update(token).digest('hex')!==s.token_digest)throw Error(s.slug+': credential delivery has not been consumed');
  const response=await fetch('https://api.github.com/installation/repositories?per_page=2',{
    headers:{Authorization:'Bearer '+token,Accept:'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'},
    redirect:'error',signal:AbortSignal.timeout(15000)});
  if(response.status===401){results[s.slug]={configured:true,token_consumed:true,http:401};continue;}
  if(response.status!==200)throw Error(s.slug+': provider credential check denied HTTP '+response.status);
  const value=await response.json();
  if(value.total_count!==1||value.repositories?.length!==1||value.repositories[0].id!==s.id||value.repositories[0].full_name!==s.repository)
    throw Error(s.slug+': mounted credential has the wrong repository scope');
  results[s.slug]={configured:true,token_consumed:true,http:200,repository_id:s.id,
    ...(s.readiness?{readiness_authenticated:true}: {})};
}console.log(JSON.stringify(results));})().catch(()=>{console.error('Required workflow credential or runtime binding failed its bounded check');process.exitCode=1;});
""".replace("SPECIFICATIONS", json.dumps(specs)).replace("CHECK_PROVIDER", "true" if provider else "false")
        namespace = next(iter(bindings.values()))[1].namespace
        result = self.run(["k3s", "kubectl", "-n", namespace, "exec", "deployment/operator-orchestration-service",
                           "--", "node", "-e", program], check=False)
        if result.returncode:
            raise CredentialError("required workflow credentials failed the actual OOS runtime check")
        try:
            value = json.loads(result.stdout)
            if not isinstance(value, dict) or set(value) != set(WORKFLOWS):
                raise ValueError("incomplete proof")
            for slug, result in value.items():
                if not isinstance(result, dict) or result.get("configured") is not True:
                    raise ValueError("configuration proof")
                if provider and (result.get("token_consumed") is not True or result.get("http") not in (200, 401)
                                 or (result.get("http") == 200 and result.get("repository_id") != bindings[slug][0].repository_id)):
                    raise ValueError("provider proof")
                if provider and result.get("http") == 200 and slug in READINESS_WORKFLOWS and result.get("readiness_authenticated") is not True:
                    raise ValueError("readiness proof")
            return value
        except (ValueError, TypeError):
            raise CredentialError("workflow credential runtime proof is incomplete") from None

    @staticmethod
    def expiry(secret: dict) -> datetime:
        try:
            value = datetime.fromisoformat(secret["metadata"]["annotations"][ANNOTATION + "token-expires-at"].replace("Z", "+00:00"))
            if value.tzinfo is None:
                raise ValueError("timezone")
            return value
        except (KeyError, ValueError, TypeError):
            raise CredentialError("workflow credential expiry is missing or invalid") from None

    def status(self) -> dict:
        bindings = {slug: self.binding(slug) for slug in WORKFLOWS}
        current_caller, _ = self.readiness_source(bindings)
        encoded_caller = base64.b64encode(current_caller.encode()).decode()
        for slug in READINESS_WORKFLOWS:
            contract, _, secret = bindings[slug]
            if secret["data"].get(contract.wgcf_secret_key) != encoded_caller:
                raise CredentialError("workflow readiness caller projection is stale; run the existing credential refresh")
        for slug, (_, target, secret) in bindings.items():
            if ((self.expiry(secret) - datetime.now(UTC)).total_seconds() < 300
                    or secret["metadata"]["annotations"][ANNOTATION + "dev-integration-session"] != target.session_id):
                raise CredentialError(f"{slug}: workflow credential is expired or bound to a stale session")
        results = self.probe(bindings)
        if any(result.get("http") != 200 for result in results.values()):
            raise CredentialError("a required workflow credential is not accepted by the provider")
        return {slug: {**results[slug], "expires_at": self.expiry(secret).isoformat()}
                for slug, (_, _, secret) in bindings.items()}

    def renew(self, *, force: bool = False, extra_annotations: dict | None = None) -> dict:
        bindings = {slug: self.binding(slug) for slug in WORKFLOWS}
        self.probe(bindings, provider=False)
        bindings = self.reconcile_readiness(bindings)
        due = [slug for slug, (_, target, secret) in bindings.items()
               if force
               or (self.expiry(secret) - datetime.now(UTC)).total_seconds() < 1200
               or secret["metadata"]["annotations"][ANNOTATION + "dev-integration-session"] != target.session_id]
        if not due:
            # Finish an interrupted delivery before judging the mounted token or
            # minting another one. A fresh Secret alone does not prove consumption.
            bindings = {slug: self.binding(slug) for slug in WORKFLOWS}
            self.consume(bindings, extra_annotations)
            observed = self.probe(bindings)
            due = [slug for slug in WORKFLOWS if observed[slug].get("http") == 401]
            if not due:
                return {"refreshed": [], "identities": self.status()}
        keys = {}
        prepared = []
        previous = []
        refreshed = []
        try:
            # Prove all required key sources before replacing a provider token.
            for slug in due:
                _, definition = self.contract(slug)
                source = definition["secret_custody"]["private_key_source"]
                if source != {"backend": "vault", "path": "components/operator-orchestration-service/dev-integration/" + slug,
                              "property": "privateKey"}:
                    raise CredentialError(f"{slug}: private-key source is outside the admitted Vault boundary")
                keys[slug] = self.private_key({"address": "http://127.0.0.1:8200", "namespace": "vault", "pod": "vault-0",
                                               "secret_path": "kv/" + source["path"], "secret_property": "privateKey"})
            for slug in due:
                contract, target, secret = bindings[slug]
                args = Namespace(app_id=WORKFLOWS[slug][0], installation_id=WORKFLOWS[slug][1],
                                 private_key_file=keys[slug], provider_api_base_url=None, sandbox=False)
                client, token, _ = intake_identity.validated_token(args, contract)
                prepared.append((slug, client, token))
            # Every key, App, installation and exact repository grant is proven
            # before the first Secret changes. Failed preparation revokes only
            # new, unprojected tokens and leaves the owner bindings untouched.
            for slug, client, token in prepared:
                contract, target, secret = bindings[slug]
                old = base64.b64decode(secret["data"][contract.runtime_secret_key], validate=True).decode()
                secret["data"][contract.runtime_secret_key] = base64.b64encode(token.token.encode()).decode()
                annotations = secret["metadata"]["annotations"]
                annotations[ANNOTATION + "token-expires-at"] = token.expires_at
                annotations[ANNOTATION + "dev-integration-session"] = target.session_id
                try:
                    self._project_binding(slug, contract, target, secret)
                except Exception:
                    raise CredentialError(f"{slug}: credential replacement failed") from None
                previous.append((client, old))
                refreshed.append(slug)
            # Always reconcile the delivery versions: this also repairs a crash
            # after Secret replacement but before pod consumption. No forced restart
            # occurs on an unchanged timer tick, and the group takes one rollout.
            bindings = {slug: self.binding(slug) for slug in WORKFLOWS}
            self.consume(bindings, extra_annotations)
            current = self.status()
            for client, old in previous:
                try:
                    client.revoke_token(old)
                except IdentityError as error:
                    if "HTTP 401" not in str(error) and "HTTP 404" not in str(error):
                        raise CredentialError("prior workflow credential revocation failed") from None
            return {"refreshed": refreshed, "identities": current}
        finally:
            revoke_failed = False
            for slug, client, token in prepared:
                if slug not in refreshed:
                    try:
                        client.revoke_token(token.token)
                    except IdentityError:
                        revoke_failed = True
            for key in keys.values():
                key.unlink(missing_ok=True)
            if revoke_failed:
                raise CredentialError("unprojected workflow credential revocation failed")

    def _project_binding(self, slug: str, contract, target, secret: dict) -> None:
        # Retain the original producer's Apply ownership, not an Update/replace
        # manager that would make its existing recovery command conflict. Keep
        # resourceVersion for CAS and all existing fields to avoid SSA deletion.
        manager = "platform-workspace-intake" if slug == "workspace-intake" else f"platform-{contract.workflow_slug}"
        payload = {**secret, "metadata": dict(secret["metadata"])}
        payload["metadata"].pop("managedFields", None)
        self.run(["k3s", "kubectl", "-n", target.namespace, "apply", "--server-side",
                  f"--field-manager={manager}", "-f", "-"], input_value=json.dumps(payload))

    def consume(self, bindings: dict, extra_annotations: dict | None) -> None:
        namespace = next(iter(bindings.values()))[1].namespace
        versions = dict(extra_annotations or {})
        versions.update({ANNOTATION + slug + "-token-expires-at": secret["metadata"]["annotations"][ANNOTATION + "token-expires-at"]
                         for slug, (_, _, secret) in bindings.items()})
        versions.update({ANNOTATION + slug + "-credential-resource-version": secret["metadata"]["resourceVersion"]
                         for slug, (_, _, secret) in bindings.items() if slug in READINESS_WORKFLOWS})
        # Historical identity activation revisions are floors, not the issuer
        # version of the current reviewed composition. Bind consumers to that
        # exact accepted issuer; never weaken OOS's exact-receipt checks.
        environment = [{"name": bindings[slug][0].wgcf_implementation_ref_env,
                        "value": self.readiness_revision} for slug in READINESS_WORKFLOWS]
        self.run(["k3s", "kubectl", "-n", namespace, "patch", "deployment/operator-orchestration-service",
                  "--type=strategic", "--patch", json.dumps({"spec": {"template": {
                      "metadata": {"annotations": versions}, "spec": {"containers": [{
                          "name": "operator-orchestration-service", "env": environment}]}}}})])
        self.run(["k3s", "kubectl", "-n", namespace, "rollout", "status", "deployment/operator-orchestration-service", "--timeout=300s"])
