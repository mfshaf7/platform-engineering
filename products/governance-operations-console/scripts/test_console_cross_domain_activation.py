#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("console_cross_domain_activation.py")
SPEC = importlib.util.spec_from_file_location("console_cross_domain_activation", SCRIPT)
assert SPEC and SPEC.loader
activation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(activation)


class CrossDomainActivationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = activation.load_policy()
        self.catalog_policy = activation.load_policy(
            activation.PRODUCT_ROOT / "repository-catalog-commissioning-policy.yaml"
        )

    def test_policy_pins_two_distinct_owner_sources(self) -> None:
        owners = self.policy["owners"]
        self.assertEqual(owners["oos"]["repo"], "operator-orchestration-service")
        self.assertEqual(owners["wgcf"]["repo"], "workspace-governance-control-fabric")
        self.assertNotEqual(owners["oos"]["local_port"], owners["wgcf"]["local_port"])
        self.assertEqual(len(owners["oos"]["revision"]), 40)
        self.assertEqual(len(owners["wgcf"]["revision"]), 40)
        self.assertEqual(self.policy["schema_version"], 2)
        self.assertEqual(
            self.policy["activation"]["security_gate_id"],
            "gate:intake-inventory-controlled-activation",
        )
        self.assertIn(
            "workspace-intake-or-inventory-operating-readiness",
            self.policy["proof_scope"]["excludes"],
        )

    def test_policy_pins_exact_architecture_supersession(self) -> None:
        architecture = self.policy["architecture"]
        review = "\n".join([
            architecture["current"]["uri"],
            architecture["predecessor"]["uri"],
            self.policy["console"]["revision"],
            self.policy["owners"]["oos"]["revision"],
            self.policy["owners"]["wgcf"]["revision"],
            self.policy["authority"]["workspace_governance_revision"],
        ])
        activation.require_architecture_binding(self.policy, review)
        with self.assertRaisesRegex(activation.ActivationError, "predecessor"):
            activation.require_architecture_binding(
                self.policy,
                review.replace(architecture["predecessor"]["uri"], "missing"),
            )

    def test_validation_reads_security_review_text(self) -> None:
        architecture = self.policy["architecture"]
        review = "\n".join([
            architecture["current"]["uri"],
            architecture["predecessor"]["uri"],
            self.policy["console"]["revision"],
            self.policy["owners"]["oos"]["revision"],
            self.policy["owners"]["wgcf"]["revision"],
            self.policy["authority"]["workspace_governance_revision"],
        ])
        completed = activation.subprocess.CompletedProcess([], 0, stdout=review, stderr="")
        with (
            patch.object(activation, "operator", return_value="operator"),
            patch.object(activation, "require_revision"),
            patch.object(activation, "require_manifest"),
            patch.object(activation, "require_clean_platform_source"),
            patch.object(activation, "repo_path", return_value=Path("/security")),
            patch.object(activation, "run", return_value=completed),
        ):
            activation.validate(self.policy)

    def test_repo_path_override_is_explicit_and_absolute(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            resolved = activation.parse_repo_paths([f"workspace-governance={temp_dir}"])
            self.assertEqual(resolved["workspace-governance"], Path(temp_dir).resolve())
        with self.assertRaisesRegex(activation.ActivationError, "absolute repository path"):
            activation.parse_repo_paths(["workspace-governance=relative"])

    def test_units_keep_credentials_in_private_environment_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            units = root / "units"
            console = root / "console"
            console.mkdir()
            env_file = root / "private" / "console.env"
            env_file.parent.mkdir()
            env_file.write_text("OOS_CALLER_SECRET=secret\n", encoding="utf-8")
            with (
                patch.object(activation, "UNIT_ROOT", units),
                patch.object(activation, "repo_path", return_value=console),
                patch.object(activation, "run"),
                patch.object(activation, "operator", return_value="operator"),
                patch.object(
                    activation.shutil,
                    "which",
                    side_effect=lambda command: f"/tools/{command}",
                ),
            ):
                activation.write_units(self.policy, env_file)
            console_unit = (units / activation.unit_name("console")).read_text(encoding="utf-8")
            self.assertIn(f"EnvironmentFile={env_file}", console_unit)
            self.assertIn("ExecStart=/tools/npm run dev", console_unit)
            self.assertNotIn("secret", console_unit)
            self.assertIn("Wants=governance-console-cross-domain-oos.service", console_unit)

    def test_private_state_directory_is_hardened_when_it_already_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "state"
            path.mkdir(mode=0o755)
            activation.ensure_private_directory(path)
            self.assertEqual(path.stat().st_mode & 0o777, 0o700)

    def test_session_issue_hardens_projection_and_receipt_parents(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state = root / "state"
            private = state / "private"
            receipts = state / "receipts"
            for path in (state, private, receipts):
                path.mkdir(exist_ok=True, mode=0o755)
            with (
                patch.object(activation, "STATE_ROOT", state),
                patch.object(activation, "PRIVATE_ROOT", private),
                patch.object(activation, "RECEIPT_ROOT", receipts),
                patch.object(activation, "run"),
            ):
                activation.issue_session_projection(self.catalog_policy)
            self.assertEqual(state.stat().st_mode & 0o777, 0o700)
            self.assertEqual(private.stat().st_mode & 0o777, 0o700)
            self.assertEqual(receipts.stat().st_mode & 0o777, 0o700)

    def test_receipt_contains_source_proof_but_no_credentials(self) -> None:
        activity = {
            "mode": "live",
            "status": "current",
            "sources": [
                {"owner": "operator-orchestration-service", "state": "current"},
                {"owner": "workspace-governance-control-fabric", "state": "current"},
            ],
            "events": [{"eventId": "one"}],
            "observedAt": "2026-09-28T00:00:00Z",
            "truncated": False,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(activation, "RECEIPT_ROOT", Path(temp_dir)),
                patch.object(activation, "operator", return_value="operator"),
                patch.object(activation, "git_head", return_value="a" * 40),
            ):
                path = activation.receipt(
                    "status",
                    self.policy,
                    activity,
                    runtime_boundary={
                        "services_active": True,
                        "wgcf_reader_binding_present": True,
                    },
                )
            value = json.loads(path.read_text(encoding="utf-8"))
            serialized = json.dumps(value).casefold()
            self.assertEqual(value["result"], "succeeded")
            self.assertEqual(value["live_proof"]["event_count"], 1)
            self.assertEqual(
                value["architecture"]["current"]["digest"],
                self.policy["architecture"]["current"]["digest"],
            )
            self.assertFalse(value["credential_boundary"]["credentials_embedded"])
            self.assertEqual(value["proof_scope"], self.policy["proof_scope"])
            self.assertEqual(value["source_revisions"]["platform-engineering"], "a" * 40)
            self.assertTrue(value["runtime_boundary"]["services_active"])
            self.assertTrue(value["runtime_boundary"]["wgcf_reader_binding_present"])
            self.assertNotIn("caller_secret", serialized)
            self.assertNotIn("token_urlsafe", serialized)

    def test_live_proof_rejects_fixture_authority(self) -> None:
        fixture = {
            "mode": "live",
            "status": "current",
            "sources": [
                {"owner": "operator-orchestration-service", "state": "current"},
                {"owner": "workspace-governance-control-fabric", "state": "current"},
            ],
            "events": [{"source": {"mode": "prototype-local"}}],
        }
        with (
            patch.object(activation, "http_json", return_value=fixture),
            patch.object(activation.time, "sleep"),
            patch.object(activation.time, "monotonic", side_effect=[0, 1, 181]),
        ):
            with self.assertRaisesRegex(activation.ActivationError, "fixture authority"):
                activation.wait_for_activity(self.policy)

    def test_repository_catalog_policy_binds_exact_security_approved_sources(self) -> None:
        policy = self.catalog_policy
        self.assertEqual(
            policy["activation"]["security_gate_id"],
            "gate:repository-catalog-controlled-activation",
        )
        self.assertEqual(policy["architecture"]["relationship"], "exact-security-binding")
        self.assertEqual(
            policy["architecture"]["current"]["digest"],
            "sha256:ef13022a4fb930086617781eda0727217d3cae0d17e23cde7c82276e0da10db7",
        )
        self.assertEqual(
            policy["owners"]["oos"]["revision"],
            "968643ad3dca86366ae417ebe77a23ba7c2c2cb6",
        )
        self.assertEqual(
            policy["owners"]["wgcf"]["revision"],
            "3d04ccaa8a751dfcb743c06b253299ee028c8f46",
        )
        self.assertEqual(
            policy["authority"]["security_revision"],
            "3cb26a024fce1d01ff8eb80899d8f50299982c9a",
        )
        self.assertEqual(
            policy["authority"]["security_review_ref"],
            "docs/reviews/components/2026-10-04-repository-catalog-authority-schema-v2-reacceptance.md",
        )
        self.assertEqual(
            policy["console"]["revision"],
            "9347794a138f3649bb6ef5b7db057524d1c1e26d",
        )
        self.assertFalse(policy["credentials"]["browser_credentials_allowed"])
        self.assertIn("first-use-repository-readiness-issuance", policy["proof_scope"]["includes"])
        self.assertIn(
            "openclaw-runtime-distribution",
            policy["catalog_proof"]["repository_candidates"],
        )
        self.assertEqual(
            policy["catalog_proof"]["wgcf_contract_root"],
            "/app/contracts/repository-readiness",
        )
        self.assertNotIn(
            policy["catalog_proof"]["unavailable_readiness_repository"],
            policy["catalog_proof"]["repository_candidates"],
        )

    def test_wgcf_binding_selects_the_reviewed_repository_contract_bundle(self) -> None:
        completed = activation.subprocess.CompletedProcess(
            [], 0, stdout="apiVersion: v1\nkind: Secret\n", stderr=""
        )
        with (
            patch.object(activation, "kubectl", return_value=completed) as command,
            patch.object(activation.subprocess, "run", return_value=completed),
            patch.object(activation, "operator", return_value="operator"),
        ):
            activation.install_wgcf_binding(self.catalog_policy, "s" * 36)
        set_env = next(
            call.args for call in command.call_args_list
            if call.args[:4] == (
                "-n",
                "devint-governance-control-fabric-operator",
                "set",
                "env",
            )
        )
        self.assertIn(
            "WGCF_REPOSITORY_READINESS_CONTRACT_ROOT=/app/contracts/repository-readiness",
            set_env,
        )

    def test_exact_security_binding_requires_current_packet_and_revisions(self) -> None:
        policy = self.catalog_policy
        review = "\n".join([
            policy["architecture"]["current"]["uri"],
            policy["console"]["revision"],
            policy["owners"]["oos"]["revision"],
            policy["owners"]["wgcf"]["revision"],
            policy["authority"]["workspace_governance_revision"],
        ])
        activation.require_architecture_binding(policy, review)
        with self.assertRaisesRegex(activation.ActivationError, "current"):
            activation.require_architecture_binding(
                policy,
                review.replace(policy["architecture"]["current"]["uri"], "missing"),
            )

    def test_catalog_environment_adds_server_only_session_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (
                patch.object(activation, "PRIVATE_ROOT", root / "private"),
                patch.object(activation, "STATE_ROOT", root),
            ):
                path = activation.write_private_env(
                    self.catalog_policy,
                    "o" * 40,
                    "w" * 40,
                )
            value = path.read_text(encoding="utf-8")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn("GOVERNANCE_CONSOLE_OPERATOR_ID=operator:workspace-owner", value)
            self.assertIn("GOVERNANCE_CONSOLE_SESSION_PROJECTION_PATH=", value)
            self.assertNotIn("BROWSER", value)

    def test_catalog_command_separates_first_use_from_existing_reference(self) -> None:
        record = {
            "id": "workspace-registry-record:repo:context-governance-gateway",
            "lineage": {"source_ref": "git://workspace-governance/contracts/repos.yaml"},
        }
        first = activation.catalog_command(
            "context-governance-gateway",
            record,
            mode="add",
            target_value_id=None,
            prefix="first-use",
        )
        self.assertNotIn("repositoryReadiness", first)
        readiness = {
            "catalog_value_key": "context-governance-gateway",
            "repo_name": "context-governance-gateway",
            "repo_ref": "repo://context-governance-gateway",
            "receipt": {"digest": "sha256:" + "1" * 64},
        }
        existing = activation.catalog_command(
            "context-governance-gateway",
            record,
            mode="edit",
            target_value_id="catalog-value:one",
            readiness=readiness,
            prefix="existing-reference",
        )
        self.assertEqual(existing["repositoryReadiness"], readiness)
        self.assertEqual(existing["targetValueId"], "catalog-value:one")

    def test_denial_proof_cannot_accept_success(self) -> None:
        with self.assertRaisesRegex(activation.ActivationError, "did not fail closed"):
            activation.require_denied(200, {"status": "applied"}, "false success")

    def test_catalog_canonical_state_ignores_only_projection_timestamp(self) -> None:
        before = {
            "catalog_value_id": "catalog-value:one",
            "value_key": "workspace-governance",
            "last_projected_at": "2026-10-04T08:08:00Z",
            "repository_binding": {"receipt": {"digest": "sha256:" + "1" * 64}},
        }
        after = json.loads(json.dumps(before))
        after["last_projected_at"] = "2026-10-04T08:11:00Z"
        self.assertEqual(
            activation.catalog_canonical_state(before),
            activation.catalog_canonical_state(after),
        )
        after["repository_binding"]["receipt"]["digest"] = "sha256:" + "2" * 64
        self.assertNotEqual(
            activation.catalog_canonical_state(before),
            activation.catalog_canonical_state(after),
        )

    def test_scale_down_waits_for_zero_ready_and_available_replicas(self) -> None:
        responses = [
            activation.subprocess.CompletedProcess([], 0, stdout="", stderr=""),
            activation.subprocess.CompletedProcess(
                [], 0, stdout=json.dumps({"status": {"readyReplicas": 1}}), stderr=""
            ),
            activation.subprocess.CompletedProcess(
                [], 0, stdout=json.dumps({"status": {}}), stderr=""
            ),
        ]
        with (
            patch.object(activation, "kubectl", side_effect=responses) as command,
            patch.object(activation.time, "monotonic", side_effect=[0, 1, 2]),
            patch.object(activation.time, "sleep"),
        ):
            activation.set_deployment_replicas("owner", "catalog", 0)
        self.assertEqual(command.call_count, 3)

    def test_restart_waits_for_console_before_catalog_readback(self) -> None:
        events = []

        def ready(_policy):
            events.append("ready")
            return {"mode": "live", "status": "current"}

        def catalog(_policy):
            events.append("catalog")
            return {"catalog_projection_status": "ready"}

        with (
            patch.object(activation, "validate"),
            patch.object(activation, "kubectl"),
            patch.object(activation, "run"),
            patch.object(activation, "wait_for_activity", side_effect=ready),
            patch.object(activation, "repository_catalog_status", side_effect=catalog),
            patch.object(activation, "active_runtime_boundary", return_value={}),
            patch.object(activation, "receipt", return_value=Path("restart.json")),
        ):
            activation.restart(self.catalog_policy)

        self.assertEqual(events, ["ready", "catalog"])

    def test_commission_binds_child_receipts_and_restores_availability(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            children = []
            for index, action in enumerate([
                "activate", "status", "catalog-rehearse", "restart", "status",
                "rollback", "cleanup", "activate", "status",
            ]):
                path = root / f"{index}-{action}.json"
                payload = {
                    "action": action,
                    "content_digest": "sha256:" + f"{index + 1:064x}",
                }
                if index == 8:
                    payload["repository_catalog_proof"] = {
                        "catalog_projection_status": "ready"
                    }
                path.write_text(json.dumps(payload), encoding="utf-8")
                children.append(path)

            captured = {}

            def aggregate(action, policy, activity=None, **kwargs):
                captured.update({"action": action, "activity": activity, **kwargs})
                return root / "commission.json"

            with (
                patch.object(activation, "validate"),
                patch.object(activation, "activate", side_effect=[children[0], children[7]]),
                patch.object(
                    activation, "status", side_effect=[children[1], children[4], children[8]]
                ),
                patch.object(activation, "catalog_rehearse", return_value=children[2]),
                patch.object(activation, "restart", return_value=children[3]),
                patch.object(activation, "rollback", side_effect=[children[5], children[6]]),
                patch.object(activation, "wait_for_activity", return_value={"mode": "live"}),
                patch.object(
                    activation,
                    "active_runtime_boundary",
                    return_value={"services_active": True},
                ),
                patch.object(activation, "receipt", side_effect=aggregate),
            ):
                result = activation.commission(self.catalog_policy)

            self.assertEqual(result, root / "commission.json")
            self.assertEqual(captured["action"], "commission")
            self.assertTrue(captured["runtime_boundary"]["final_availability_restored"])
            proof = captured["repository_catalog_proof"]
            self.assertTrue(proof["commissioning_sequence_complete"])
            self.assertEqual(len(proof["child_receipts"]), 9)
            self.assertEqual(proof["child_receipts"][2]["action"], "catalog-rehearse")


if __name__ == "__main__":
    unittest.main()
