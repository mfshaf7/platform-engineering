#!/usr/bin/env python3
"""Synthetic composition proof, not provider entitlement or live activation."""
from __future__ import annotations

import base64
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import yaml

SPEC = importlib.util.spec_from_file_location("console_model_management", Path(__file__).with_name("console_model_management.py"))
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
from governed_ai_test_support import prepare_contracts


def policy():
    return yaml.safe_load((ROOT / "products/governance-operations-console/complete-runtime-policy.yaml").read_text())


def manifest():
    return yaml.safe_dump_all([
        {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "governed-ai-gateway-app"}, "data": {}},
        {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "governed-ai-gateway"}, "spec": {"template": {"spec": {
            "containers": [{"name": "gateway", "image": "python:legacy", "env": [{"name": "GOVERNED_AI_OLLAMA_BASE_URL", "value": "http://192.0.2.1:11434"}],
                            "volumeMounts": [{"name": "audit", "mountPath": "/var/lib/governed-ai-gateway"}]}],
            "volumes": [{"name": "audit", "persistentVolumeClaim": {"claimName": "retained-owner-state"}}]}}}},
        {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy", "metadata": {"name": "governed-ai-gateway-provider-egress"},
         "spec": {"egress": [{"to": [{"ipBlock": {"cidr": "192.0.2.1/32"}}], "ports": [{"port": 11434}]}]}},
        {"apiVersion": "networking.k8s.io/v1", "kind": "NetworkPolicy", "metadata": {"name": "consumer-deny-direct-provider"}, "spec": {"egress": []}},
    ])


class ModelCompositionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="synthetic-model-management-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        prepare_contracts(self.root)
        (self.root / "products").symlink_to(ROOT / "products", target_is_directory=True)

    def overlay(self):
        return {"image": module.IMAGE_REPOSITORY + "@sha256:" + "a" * 64,
                "owner_policy": module.owner_policy(self.root, "operator:synthetic"), "memory_limit": "1Gi", "cpu_limit": "1"}

    def test_unreviewed_executable_image_and_resource_change_are_rejected(self):
        for field, value in [("codex_sha256", "0" * 64), ("base_image", "unreviewed:latest"), ("memory_limit", "8Gi"), ("enabled", False)]:
            selected = policy(); selected["model_management"][field] = value
            with self.subTest(field=field), self.assertRaises(module.ModelCompositionError):
                module.validate(selected)

    def test_reviewed_fixture_task_permissions_are_retained(self):
        value = module.owner_policy(self.root, "operator:synthetic")
        actual = yaml.safe_load((self.root / "security/governed-ai-model-profiles.yaml").read_text())["model_profiles"]
        expected = sorted(name + "/" + task for name, definition in actual.items() for task in definition["task_contracts"]["allowed"])
        self.assertEqual(set(actual), module.TASK_PROFILES)
        for backend in value["backends"].values(): self.assertEqual(backend["allowed_tasks"], expected)
        self.assertEqual(value["backends"]["managed-codex"]["vault"]["path"], module.ACCOUNT_PATH)
        self.assertNotIn("OPENAI_API_KEY", json.dumps(value))
        self.assertEqual(value["api_connections"]["allowed_tasks"], expected)
        self.assertEqual(value["api_connections"]["providers"], ["claude-api", "deepseek-api", "glm-api"])
        self.assertEqual(value["api_connections"]["vault"]["prefix"], module.API_CREDENTIAL_PREFIX)

    def test_extra_suspended_profile_still_requires_runtime_boundary_review(self):
        path = self.root / "security/governed-ai-model-profiles.yaml"
        document = yaml.safe_load(path.read_text())
        document["model_profiles"]["synthetic-suspended-qualification"] = {
            "status": "suspended", "task_contracts": {"allowed": {"synthetic_task": {}}}}
        path.write_text(yaml.safe_dump(document))
        with self.assertRaisesRegex(module.ModelCompositionError, "changed profile/data boundary"):
            module.owner_policy(self.root, "operator:synthetic")

    def test_rendered_pod_has_bounded_private_execution_without_project_or_service_account_mounts(self):
        docs = list(yaml.safe_load_all(module.patch_manifest(manifest(), self.overlay())))
        spec = docs[1]["spec"]["template"]["spec"]; main = spec["containers"][0]
        self.assertEqual(docs[1]["spec"]["strategy"], {"type": "Recreate", "rollingUpdate": None})
        self.assertFalse(spec["automountServiceAccountToken"])
        self.assertEqual(spec["securityContext"]["runAsUser"], 1000)
        self.assertEqual(main["resources"]["limits"], {"cpu": "1", "memory": "1Gi", "ephemeral-storage": "1Gi"})
        self.assertTrue(main["securityContext"]["readOnlyRootFilesystem"])
        self.assertFalse(main["securityContext"]["allowPrivilegeEscalation"])
        self.assertEqual(main["imagePullPolicy"], "IfNotPresent")
        self.assertEqual(main["readinessProbe"]["httpGet"]["path"], "/healthz")
        self.assertEqual(spec["initContainers"][0]["image"], main["image"])
        self.assertEqual(spec["initContainers"][0]["imagePullPolicy"], "IfNotPresent")
        self.assertFalse(any("hostPath" in item for item in spec["volumes"]))
        self.assertEqual(spec["volumes"][0]["persistentVolumeClaim"]["claimName"], "retained-owner-state")
        self.assertIn("0o600", spec["initContainers"][0]["command"][-1])
        self.assertFalse(any(item["name"] == "model-owner-secret" for item in main["volumeMounts"]))
        owner = json.loads(docs[0]["data"]["model-management-policy.json"])
        self.assertEqual(owner["backends"]["local-ollama"]["endpoint_origin"], "http://192.0.2.1:11434")

    def test_only_gateway_network_gains_public_tls_and_exact_vault_egress(self):
        docs = list(yaml.safe_load_all(module.patch_manifest(manifest(), self.overlay())))
        self.assertEqual(docs[3]["spec"]["egress"], [], "Consumer bypass denial remains closed")
        rules = docs[2]["spec"]["egress"]
        self.assertEqual(rules[-1]["ports"], [{"protocol": "TCP", "port": 443}])
        self.assertIn("10.0.0.0/8", rules[-1]["to"][0]["ipBlock"]["except"])
        self.assertIn("127.0.0.0/8", rules[-1]["to"][0]["ipBlock"]["except"])
        self.assertEqual(rules[-2]["to"][0]["podSelector"]["matchLabels"], {"app.kubernetes.io/name": "vault"})

    def test_pending_or_wrong_security_gate_causes_no_runtime_or_credential_effect(self):
        selected = policy()
        for state, gate in [("pending", "gate:ai-routing-composed-security"), ("accepted", "gate:other")]:
            selected["security"].update(status=state, gate_id=gate)
            effects = []
            with tempfile.TemporaryDirectory() as directory, self.assertRaises(module.ModelCompositionError):
                module.prepare(selected, repo_root=self.root, state_root=Path(directory), operator_id="operator:synthetic", gateway_namespace="synthetic", run=lambda *a, **k: effects.append((a, k)), vault_token=lambda: "synthetic-root")
            self.assertEqual(effects, [])

    def test_real_preparation_shape_limits_vault_authority_and_keeps_tokens_out_of_arguments(self):
        selected = policy(); selected["security"]["status"] = "accepted"
        calls = []
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            if "auth/token/create" in command:
                token = kwargs["input_value"].split("\n", 1)[1]
                return SimpleNamespace(returncode=0, stdout=json.dumps({"auth": {"client_token": token, "policies": ["default", module.VAULT_POLICY], "renewable": True}}))
            return SimpleNamespace(returncode=0, stdout="")
        with tempfile.TemporaryDirectory() as directory, patch.object(module, "build_image", return_value="synthetic:image"), patch.dict(os.environ, {}):
            root = Path(directory)
            module.prepare(selected, repo_root=self.root, state_root=root, operator_id="operator:synthetic", gateway_namespace="synthetic", run=execute, vault_token=lambda: "synthetic-root")
            self.assertEqual((root / "private/model-management/vault-token").stat().st_mode & 0o777, 0o600)
            self.assertTrue(Path(os.environ["DEVINT_GAI_MODEL_MANAGEMENT_OVERLAY"]).is_file())
        arguments = json.dumps([command for command, _ in calls])
        self.assertNotIn("synthetic-root", arguments); self.assertNotIn("synthetic-scoped", arguments)
        rule = next(kwargs["input_value"] for command, kwargs in calls if "policy" in command)
        self.assertIn('path "kv/data/' + module.ACCOUNT_PATH + '"', rule)
        self.assertNotIn('"list"', rule); self.assertNotIn('path "*"', rule)
        self.assertIn('path "kv/data/' + module.API_CREDENTIAL_PREFIX + '/api-*"', rule)
        self.assertNotIn('"delete"', rule); self.assertNotIn('"sudo"', rule)

    def test_reviewed_policy_extension_is_reconciled_for_existing_renewable_token(self):
        selected = policy(); selected["security"]["status"] = "accepted"
        calls = []
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            if "renew" in command:
                return SimpleNamespace(returncode=0, stdout=json.dumps({"auth": {"policies": ["default", module.VAULT_POLICY], "renewable": True}}))
            return SimpleNamespace(returncode=0, stdout="")
        with tempfile.TemporaryDirectory() as directory, patch.object(module, "build_image", return_value="synthetic:image"), patch.dict(os.environ, {}):
            root = Path(directory)
            module.private_write(root / "private/model-management/vault-token", "controlled-existing-scoped-token")
            module.prepare(selected, repo_root=self.root, state_root=root, operator_id="operator:synthetic", gateway_namespace="synthetic", run=execute, vault_token=lambda: "controlled-admin")
        self.assertTrue(any("policy" in command for command, _ in calls))
        self.assertFalse(any("auth/token/create" in command for command, _ in calls))
        self.assertNotIn("controlled-admin", json.dumps([command for command, _ in calls]))

    def test_oos_receives_only_separate_management_credential_and_exact_operator_binding(self):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); module.private_write(root / "private/model-management/management-token", "synthetic-management")
            module.bind_oos(policy(), state_root=root, namespace="devint-accepted-idea-delivery-synthetic", operator_id="operator:synthetic",
                            run=lambda command, **kwargs: calls.append((command, kwargs)))
        secret = json.loads(calls[0][1]["input_value"])
        self.assertEqual(set(secret["data"]), {"management-token"})
        self.assertEqual(base64.b64decode(secret["data"]["management-token"]), b"synthetic-management")
        deployment = json.loads(calls[1][1]["input_value"])["spec"]["template"]["spec"]
        env = {item["name"]: item["value"] for item in deployment["containers"][0]["env"]}
        self.assertEqual(json.loads(env["OOS_MODEL_OPERATIONS_CALLER_OPERATOR_BINDINGS_JSON"]), {"governance-operations-console": "operator:synthetic"})
        self.assertNotIn("vault-token", json.dumps(deployment))

    def test_renewal_uses_existing_scoped_lease_without_mint_or_admin_credential(self):
        calls = []
        def execute(command, **kwargs):
            calls.append((command, kwargs)); return SimpleNamespace(stdout=json.dumps({"auth": {"renewable": True, "policies": ["default", module.VAULT_POLICY]}}))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); module.private_write(root / "private/model-management/vault-token", "synthetic-scoped")
            module.renew_account_lease(state_root=root, run=execute)
        self.assertEqual(len(calls), 1); self.assertIn("renew -format=json", calls[0][0][-1])
        self.assertNotIn("synthetic-scoped", str(calls[0][0])); self.assertEqual(calls[0][1]["input_value"], "synthetic-scoped\n")

    def test_rollback_removes_owner_access_before_revoking_lease_and_retains_data(self):
        calls = []
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            return SimpleNamespace(stdout=json.dumps({"spec": {"egress": [{"ports": [{"port": port}]} for port in [53, 11434, 443, 8200]]}}))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); module.private_write(root / "private/model-management/vault-token", "synthetic-scoped")
            retained = root / "owner-data.json"; retained.write_text("preserved")
            module.disable(policy(), state_root=root, namespace="devint-accepted-idea-delivery-synthetic", run=execute)
            self.assertTrue(retained.exists()); self.assertFalse((root / "private/model-management/vault-token").exists())
        first = json.loads(calls[0][1]["input_value"])["spec"]["template"]["spec"]
        self.assertEqual(first["containers"][0]["volumeMounts"], [{"mountPath": "/run/model-management", "$patch": "delete"}])
        self.assertTrue(any("rollout" in command for command, _ in calls[:4]))
        network = json.loads(calls[-1][1]["input_value"])
        self.assertEqual([x["ports"][0]["port"] for x in network["spec"]["egress"]], [53, 11434])

    def test_uncertain_vault_issue_reconciles_the_same_persisted_credential_identity(self):
        selected = policy(); selected["security"]["status"] = "accepted"
        attempted = []
        def execute(command, **kwargs):
            if "auth/token/create" in command:
                token = kwargs["input_value"].split("\n", 1)[1]; attempted.append(token)
                if len(attempted) == 1:
                    raise module.ModelCompositionError("Synthetic acknowledgement loss")
                return SimpleNamespace(returncode=0, stdout=json.dumps({"auth": {"client_token": token, "renewable": True, "policies": ["default", module.VAULT_POLICY]}}))
            return SimpleNamespace(returncode=1 if "renew" in command else 0, stdout="")
        with tempfile.TemporaryDirectory() as directory, patch.object(module, "build_image", return_value="synthetic:image"), patch.dict(os.environ, {}):
            args = dict(repo_root=self.root, state_root=Path(directory), operator_id="operator:synthetic", gateway_namespace="synthetic", run=execute, vault_token=lambda: "synthetic-root")
            with self.assertRaisesRegex(module.ModelCompositionError, "acknowledgement loss"):
                module.prepare(selected, **args)
            retained = (Path(directory) / "private/model-management/vault-token").read_text()
            module.prepare(selected, **args)
        self.assertEqual(attempted, [retained, retained])

    def test_invalid_or_broader_lease_evidence_is_not_accepted(self):
        for value in [{}, {"auth": {"renewable": True, "policies": ["root"]}}, {"auth": {"renewable": False, "policies": ["default", module.VAULT_POLICY]}}]:
            with self.assertRaises(module.ModelCompositionError): module.account_lease(value)

    def test_registry_image_is_verified_and_consumed_by_immutable_digest_without_host_import(self):
        selected = policy(); value = module.validate(selected); calls = []
        immutable = module.IMAGE_REPOSITORY + "@sha256:" + "a" * 64
        def execute(command, **kwargs):
            calls.append(command)
            self.assertEqual(command[1], "--config")
            self.assertEqual(list(Path(command[2]).iterdir()), [], "Anonymous verification must not inherit Docker logins or helpers")
            command = [command[0], *command[3:]]
            if command[:3] == ["docker", "image", "inspect"]:
                result = ({"RootFS": {"Layers": ["base-one", "base-two"]}} if command[3] == value["base_image"] else
                          {"RepoDigests": [immutable], "Config": {"Labels": module.image_labels(value)},
                           "RootFS": {"Layers": ["base-one", "base-two", "executable"]}})
                return SimpleNamespace(returncode=0, stdout=json.dumps(result))
            return SimpleNamespace(returncode=0, stdout=value["codex_sha256"] + "  /usr/local/bin/codex\n")
        self.assertEqual(module.build_image(selected, ROOT, execute, import_image=True), immutable)
        self.assertTrue(all(command[0] == "docker" for command in calls))
        self.assertFalse(any("ctr" in command or "sudo" in command or "import" in command for command in calls))
        invocation = next(command for command in calls if "run" in command)
        self.assertIn(immutable, invocation)
        self.assertNotIn(module.image_name(selected), invocation)

    def test_wrong_registry_provenance_base_digest_or_executable_blocks_consumption(self):
        selected = policy(); value = module.validate(selected)
        immutable = module.IMAGE_REPOSITORY + "@sha256:" + "a" * 64
        for failure in ("source", "missing-digest", "invalid-digest", "base", "extra-layer", "binary"):
            with self.subTest(failure=failure):
                actual = {"RepoDigests": [immutable], "Config": {"Labels": module.image_labels(value)},
                          "RootFS": {"Layers": ["base", "executable"]}}
                if failure == "source": actual["Config"]["Labels"]["org.opencontainers.image.source"] = "https://example.invalid/other"
                if failure == "missing-digest": actual["RepoDigests"] = []
                if failure == "invalid-digest": actual["RepoDigests"] = [module.IMAGE_REPOSITORY + "@sha256:" + "z" * 64]
                if failure == "base": actual["RootFS"]["Layers"][0] = "different-base"
                if failure == "extra-layer": actual["RootFS"]["Layers"].append("unreviewed-layer")
                def execute(command, **kwargs):
                    command = [command[0], *command[3:]]
                    if command[:3] == ["docker", "image", "inspect"]:
                        return SimpleNamespace(returncode=0, stdout=json.dumps(
                            {"RootFS": {"Layers": ["base"]}} if command[3] == value["base_image"] else actual))
                    return SimpleNamespace(returncode=0, stdout=("0" * 64 if failure == "binary" else value["codex_sha256"]) + "  /usr/local/bin/codex\n")
                with self.assertRaises(module.ModelCompositionError):
                    module.build_image(selected, ROOT, execute, import_image=True)

    def test_registry_unavailability_precedes_new_credential_or_cluster_effects(self):
        selected = policy(); selected["security"]["status"] = "accepted"; calls = []
        def execute(command, **kwargs):
            calls.append(command)
            raise module.ModelCompositionError("Published runtime is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(module.ModelCompositionError, "Published runtime is unavailable"):
                module.prepare(selected, repo_root=self.root, state_root=Path(directory), operator_id="operator:synthetic",
                               gateway_namespace="synthetic", run=execute,
                               vault_token=lambda: self.fail("An unavailable image must not request an administrator token"))
            self.assertFalse((Path(directory) / "private/model-management").exists())
        self.assertEqual(len(calls), 1)
        self.assertEqual([calls[0][0], calls[0][3]], ["docker", "pull"])


if __name__ == "__main__":
    unittest.main()
