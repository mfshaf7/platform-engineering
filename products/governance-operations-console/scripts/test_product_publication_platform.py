from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch


SCRIPT = Path(__file__).with_name("product_publication_platform.py")
SPEC = importlib.util.spec_from_file_location("product_publication_platform", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class ProductPublicationPlatformTests(unittest.TestCase):
    def test_policy_is_exactly_internal_and_binds_activated_sources(self) -> None:
        policy = module.load_policy()
        binding = policy["product_publication"]
        self.assertEqual(policy["activation"]["delivery_id"], "delivery-894")
        self.assertEqual(
            policy["activation"]["security_gate_id"],
            "gate:product-publication-controlled-activation",
        )
        self.assertEqual(binding["target"]["posture"], "internal")
        self.assertEqual(
            policy["owners"]["wgcf"]["revision"],
            "556997107497ce1ae6ad8635c96591e186bca629",
        )
        self.assertEqual(
            policy["owners"]["oos"]["revision"],
            "e10a3265b6ca3e9ca16d74f453fe7b6285d5d5b1",
        )
        self.assertEqual(policy["owners"]["oos"]["container"], "operator-orchestration-service")
        self.assertEqual(policy["owners"]["wgcf"]["container"], "api")
        self.assertEqual(
            binding["wgcf_contract_root"], "/app/contracts/product-publication"
        )
        self.assertEqual(
            binding["authority_revision"],
            "8e91d765dcf0894507818f538f128071447b11ef",
        )
        self.assertEqual(
            binding["manifest_digest"],
            "sha256:e042aae5afc266cf23f02de747ee773561efb9541747ca14a94c0f35c614015e",
        )
        self.assertFalse(policy["credentials"]["browser_credentials_allowed"])

    def test_canonical_manifest_digest_matches_the_committed_owner_manifest(self) -> None:
        policy = module.load_policy()
        binding = policy["product_publication"]
        raw = module.git_file(
            module.base.repo_path(binding["owner_repo"]),
            binding["manifest_revision"],
            binding["manifest_path"],
        )
        self.assertEqual(
            module.canonical_digest(json.loads(raw)), binding["manifest_digest"]
        )

    def test_changed_authority_binding_supersedes_the_old_proof_identity(self) -> None:
        policy = module.load_policy()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            intent = state / "proof-intent.json"
            intent.write_text(
                json.dumps({
                    "request_id": "product-publication-request:platform:1258",
                    "idempotency_key": "product-publication:platform:1258",
                    "manifest_source": {"manifest_digest": "sha256:" + "0" * 64},
                }),
                encoding="utf-8",
            )
            with (
                patch.object(module, "STATE_ROOT", state),
                patch.object(module, "INTENT_PATH", intent),
                patch.object(module.base, "ensure_private_directory"),
            ):
                current = module.proof_intent(policy)
            self.assertNotEqual(
                current["request_id"], "product-publication-request:platform:1258"
            )
            self.assertTrue(list(state.glob("proof-intent-superseded-*.json")))

    def test_positive_proof_reads_a_durable_result_before_submitting(self) -> None:
        policy = module.load_policy()
        intent = {"request_id": "product-publication-request:platform:1258:test"}
        result = {
            "state": "applied",
            "packet": {"grants": {
                "source_authority": False,
                "runtime_authority": False,
                "release_authority": False,
                "security_acceptance": False,
                "lifecycle_mutation": False,
            }, "authority_refs": {"readiness_receipt_ref": "wgcf://readiness"}},
            "receipt": {
                "receipt_id": "receipt:test",
                "owner_receipt_ref": "oos://receipt/test",
                "publication_posture": "internal",
                "publication_version": 1,
            },
            "receipt_digest": "sha256:" + "1" * 64,
            "resolution": "read",
            "command": {"request_id": intent["request_id"]},
        }
        calls: list[tuple[str, dict | None]] = []

        def request(_policy, path, *, body=None):
            calls.append((path, body))
            if len(calls) == 1:
                return 502, {
                    "code": "product_publication_oos_unavailable",
                    "retryable": True,
                }
            return 200, result

        with (
            patch.object(module, "proof_intent", return_value=intent),
            patch.object(module, "console_request", side_effect=request),
            patch.object(module.time, "sleep"),
        ):
            proof = module.positive_proof(policy)
        self.assertEqual(proof["receipt_digest"], result["receipt_digest"])
        self.assertEqual(len(calls), 3)
        self.assertTrue(all(body is None for _, body in calls))

    def test_restart_replay_accepts_the_owner_post_replay_status(self) -> None:
        policy = module.load_policy()
        positive = {
            "command": {"request_id": "product-publication-request:test"},
            "receipt_digest": "sha256:" + "1" * 64,
        }
        replay = {
            "resolution": "replayed",
            "receipt_digest": positive["receipt_digest"],
        }
        with (
            patch.object(module.base, "kubectl", return_value=Mock(stdout="")),
            patch.object(module.base, "run", return_value=Mock(returncode=0)),
            patch.object(module, "product_mode", return_value={"mode": "live"}),
            patch.object(module.base, "read_oos_secret", return_value="secret"),
            patch.object(module, "direct_oos_request", return_value=(201, replay)),
        ):
            result = module.restart_and_replay(policy, positive)
        self.assertEqual(result, replay)

    def test_partial_or_broader_policy_fails_closed(self) -> None:
        policy = module.load_policy()
        policy["product_publication"]["target"]["posture"] = "public"
        with patch.object(module.base, "validate"):
            with self.assertRaisesRegex(module.ProductPublicationError, "only the approved internal"):
                module.validate(policy)

    def test_console_environment_adds_integrity_metadata_without_credentials(self) -> None:
        policy = module.load_policy()
        with tempfile.TemporaryDirectory() as directory:
            private = Path(directory)
            env_path = private / "console.env"
            env_path.write_text("OOS_CALLER_SECRET=private-value\n", encoding="utf-8")
            with (
                patch.object(module.base, "PRIVATE_ROOT", private),
                patch.object(module.base, "run", return_value=Mock(returncode=0)),
            ):
                module.write_console_environment(policy)
            content = env_path.read_text(encoding="utf-8")
            self.assertIn("GOVERNANCE_CONSOLE_PRODUCT_PUBLICATION_AUTHORITY_REVISION=", content)
            self.assertIn("OOS_CALLER_SECRET=private-value", content)
            self.assertNotIn("WGCF_PRODUCT_PUBLICATION_CALLER_SECRET=", content)

    def test_workload_patch_uses_secret_reference_and_read_only_owner_source(self) -> None:
        policy = module.load_policy()
        patches: list[tuple[str, str, dict]] = []
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(module, "state_directory", return_value=Path(directory)),
                patch.object(module.base, "ensure_private_directory"),
                patch.object(module.base, "repo_path", return_value=Path("/owner")),
                patch.object(module.base, "kubectl", return_value=Mock(stdout="")),
                patch.object(
                    module,
                    "strategic_patch",
                    side_effect=lambda namespace, deployment, value: patches.append(
                        (namespace, deployment, value)
                    ),
                ),
            ):
                module.configure_workloads(policy)
        self.assertEqual(len(patches), 2)
        oos_container = patches[0][2]["spec"]["template"]["spec"]["containers"][0]
        secret = next(
            item for item in oos_container["env"]
            if item["name"] == "WGCF_PRODUCT_PUBLICATION_CALLER_SECRET"
        )
        self.assertIn("valueFrom", secret)
        self.assertNotIn("value", secret)
        wgcf_mount = patches[1][2]["spec"]["template"]["spec"]["containers"][0]["volumeMounts"][0]
        self.assertTrue(wgcf_mount["readOnly"])

    def test_workload_rollback_deletes_mounts_by_their_patch_merge_key(self) -> None:
        policy = module.load_policy()
        patches: list[dict] = []
        with (
            patch.object(module.base, "kubectl", return_value=Mock(stdout="")),
            patch.object(
                module,
                "strategic_patch",
                side_effect=lambda _namespace, _deployment, value: patches.append(value),
            ),
        ):
            module.remove_workload_binding(policy, "oos")
            module.remove_workload_binding(policy, "wgcf")
        mounts = [
            value["spec"]["template"]["spec"]["containers"][0]["volumeMounts"][0]
            for value in patches
        ]
        self.assertEqual(
            [mount["mountPath"] for mount in mounts],
            [
                policy["product_publication"]["oos_mount_path"],
                policy["product_publication"]["wgcf_owner_mount_path"],
            ],
        )
        self.assertTrue(all(mount["$patch"] == "delete" for mount in mounts))

    def test_receipt_digest_excludes_its_own_digest_field(self) -> None:
        policy = module.load_policy()
        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(module, "STATE_ROOT", Path(directory)),
                patch.object(module, "RECEIPT_ROOT", Path(directory) / "receipts"),
                patch.object(module, "source_revisions", return_value={"platform-engineering": "a" * 40}),
                patch.object(module.base, "operator", return_value="operator"),
            ):
                path = module.receipt("test", policy, {"ok": True})
                value = json.loads(path.read_text(encoding="utf-8"))
                digest = value.pop("content_digest")
                self.assertEqual(
                    digest,
                    module.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()),
                )


if __name__ == "__main__":
    unittest.main()
