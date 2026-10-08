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
        self.proposal_target_policy = activation.load_policy(
            activation.PRODUCT_ROOT / "proposal-target-commissioning-policy.yaml"
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
            "sha256:3a4b5edb6bc54ff47a45f610b41f75bc57dd9d1ab56e9475518100d75ff72ab0",
        )
        self.assertEqual(
            policy["owners"]["oos"]["revision"],
            "7ea390c28ac95d64a8fee285f212585bf7863cf6",
        )
        self.assertEqual(
            policy["owners"]["wgcf"]["revision"],
            "3d04ccaa8a751dfcb743c06b253299ee028c8f46",
        )
        self.assertEqual(
            policy["authority"]["security_revision"],
            "2e4fc1472c3f6d38bbfb68b6676c7e3cd520bece",
        )
        self.assertEqual(
            policy["authority"]["security_review_ref"],
            "docs/reviews/components/2026-10-04-repository-catalog-authority-schema-v2-reacceptance.md",
        )
        self.assertEqual(
            policy["console"]["revision"],
            "f7e1db75739e5fbeb8d7a5ad0d9a7858f2289aac",
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

    def test_proposal_target_policy_binds_activation_and_target_owner(self) -> None:
        policy = self.proposal_target_policy
        self.assertEqual(
            policy["activation"]["security_gate_id"],
            "gate:proposal-target-controlled-activation",
        )
        self.assertEqual(
            policy["owners"]["oos"]["revision"],
            "0e935029327c3195f7ad1026c6f450f4b32c52dd",
        )
        self.assertEqual(
            policy["source_authorities"]["prototype_studio"],
            {
                "repo": "workspace-prototype-studio",
                "minimum_revision": "4066ea5ba5a68ab7ab12acc7fc395897e1ae6c3f",
            },
        )
        self.assertEqual(
            policy["proposal_target_proof"]["repository_id"],
            1231020532,
        )
        review = "\n".join(
            [
                policy["architecture"]["current"]["uri"],
                *policy["architecture"]["security_review_revisions"],
            ]
        )
        activation.require_architecture_binding(policy, review)

    def test_receipt_keeps_activation_source_after_target_authority_advances(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(activation, "RECEIPT_ROOT", Path(temp_dir)),
                patch.object(activation, "operator", return_value="operator"),
                patch.object(activation, "git_head", return_value="a" * 40),
            ):
                path = activation.receipt("status", self.proposal_target_policy)
            value = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(
                value["source_revisions"]["workspace-prototype-studio"],
                self.proposal_target_policy["source_authorities"]["prototype_studio"][
                    "minimum_revision"
                ],
            )
            self.assertEqual(value["source_revisions"]["platform-engineering"], "a" * 40)

    def test_catalog_mutation_retries_transient_response_with_same_command(self) -> None:
        command = {"acceptanceId": "stable-acceptance", "mode": "edit"}
        responses = [
            (502, {"error": "owner_temporarily_unavailable"}),
            (200, {"status": "applied", "readback_complete": True}),
        ]
        with (
            patch.object(activation, "http_request_json", side_effect=responses) as request,
            patch.object(activation.time, "sleep") as sleep,
        ):
            result = activation.mutate_catalog(self.catalog_policy, command)

        self.assertEqual(result, responses[-1])
        self.assertEqual(request.call_count, 2)
        self.assertIs(request.call_args_list[0].kwargs["body"], command)
        self.assertIs(request.call_args_list[1].kwargs["body"], command)
        sleep.assert_called_once_with(1)

    def test_catalog_mutation_does_not_retry_contract_denial(self) -> None:
        command = {"acceptanceId": "denied-acceptance", "mode": "edit"}
        denied = (409, {"error": "catalog_mutation_denied"})
        with patch.object(
            activation, "http_request_json", return_value=denied
        ) as request:
            result = activation.mutate_catalog(self.catalog_policy, command)

        self.assertEqual(result, denied)
        request.assert_called_once()

    def test_evidence_profile_uses_non_disruptive_commissioning_verifier(self) -> None:
        profile = json.loads(
            (activation.REPO_ROOT / "contracts/delivery-art-work-session/evidence-profile.json")
            .read_text(encoding="utf-8")
        )
        command = next(
            item for item in profile["commands"]
            if item["id"] == "repository-catalog-operating-commissioning"
        )
        self.assertEqual(command["args"][-1], "verify-commissioning")
        self.assertEqual(
            command["conformance_case_ids"],
            [
                "case:repository-catalog-operating-positive",
                "case:repository-catalog-operating-negative",
            ],
        )
        proposal = next(
            item for item in profile["commands"]
            if item["id"] == "proposal-target-operating-commissioning"
        )
        self.assertEqual(
            proposal["args"][-1],
            "verify-proposal-target-commissioning",
        )
        self.assertEqual(
            proposal["conformance_case_ids"],
            [
                "case:proposal-target-operating-positive",
                "case:proposal-target-operating-negative",
            ],
        )

    def test_proposal_target_application_requires_canonical_merged_readback(self) -> None:
        application = {
            "workflow_id": "proposal-target-application",
            "application_id": "proposal-target-application:idea-851",
            "proposal_id": "idea-851",
            "prototype_id": "prototype:proposal-851",
            "status": "succeeded",
            "revision": 5,
            "canonical_target_mutation": True,
            "proposal_mutation": True,
            "runtime_activation": False,
            "preparation": {
                "changed_paths": [
                    "records/prototype-captures/proposal-851/record.yaml",
                    "records/prototype-captures/proposal-851/receipt.json",
                ],
            },
            "review": {
                "repository": "workspace-prototype-studio",
                "number": 41,
                "merged": True,
                "human_reviewed": True,
                "merge_commit": "b" * 40,
            },
            "target_result": {"receipt": {"receipt_ref": "receipt://target/851"}},
            "proposal_acknowledgement": {
                "projection": {
                    "record_version": "version-9",
                    "handoff": {"state": "applied"},
                },
            },
        }
        completed = activation.subprocess.CompletedProcess([], 0, stdout="", stderr="")
        with (
            patch.object(activation, "repo_path", return_value=Path("/studio")),
            patch.object(activation, "git_head", return_value="c" * 40),
            patch.object(activation, "run", return_value=completed),
        ):
            proof = activation.validate_proposal_target_application(
                self.proposal_target_policy,
                application,
                application["application_id"],
            )
        self.assertTrue(proof["canonical_proposal_acknowledged"])
        self.assertTrue(proof["human_reviewed_merge"])
        self.assertEqual(proof["studio_revision"], "c" * 40)

        application["proposal_acknowledgement"]["projection"]["handoff"]["state"] = "ready"
        with self.assertRaisesRegex(activation.ActivationError, "canonically complete"):
            activation.validate_proposal_target_application(
                self.proposal_target_policy,
                application,
                application["application_id"],
            )

    def test_proposal_target_negative_and_child_proofs_are_exact_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            negative = root / "negative.json"
            negative.write_text(
                json.dumps({
                    "schema_version": 1,
                    "outcomes": {
                        scenario: {
                            "http_status": 409,
                            "code": f"denied_{index}",
                            "canonical_state_changed": False,
                        }
                        for index, scenario in enumerate(
                            activation.PROPOSAL_TARGET_NEGATIVE_SCENARIOS
                        )
                    },
                }),
                encoding="utf-8",
            )
            negative.chmod(0o600)
            outcomes = activation.validate_proposal_target_negatives(negative)
            self.assertEqual(set(outcomes), activation.PROPOSAL_TARGET_NEGATIVE_SCENARIOS)

            sources = {"operator-orchestration-service": "a" * 40}
            actions = [
                "activate", "status", "restart", "status",
                "rollback", "cleanup", "activate", "status",
            ]
            paths = []
            for index, action in enumerate(actions):
                path = root / f"{index}-{action}.json"
                value = {"action": action, "source_revisions": sources}
                value["content_digest"] = activation.receipt_content_digest(value)
                path.write_text(json.dumps(value), encoding="utf-8")
                path.chmod(0o600)
                paths.append(path)
            children = activation.validate_child_receipts(paths, sources)
            self.assertEqual([item["action"] for item in children], actions)

            negative.chmod(0o644)
            with self.assertRaisesRegex(activation.ActivationError, "operator-private"):
                activation.validate_proposal_target_negatives(negative)

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

        refreshed = activation.catalog_command(
            "context-governance-gateway",
            record,
            mode="edit",
            target_value_id="catalog-value:one",
            prefix="existing-reference-refresh",
        )
        self.assertNotIn("repositoryReadiness", refreshed)
        self.assertEqual(refreshed["targetValueId"], "catalog-value:one")

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
