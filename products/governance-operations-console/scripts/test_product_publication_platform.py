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


DIGESTS = {letter: "sha256:" + letter * 64 for letter in "abcdef123456789"}
REVISIONS = {name: str(index) * 40 for index, name in enumerate(
    ("active", "retired", "restored", "final", "source"), start=1
)}


def artifact(name: str, digest: str) -> dict:
    return {"id": name, "digest": digest}


def lifecycle(action: str, posture: str, version: int, digest: str, event: dict) -> dict:
    return {
        "request_id": f"workspace-inventory-lifecycle-request:{action}:1273",
        "status": "succeeded",
        "canonical_mutation": True,
        "request": {
            "action": action,
            "prior_event_ref": None,
            "target": {
                "kind": "product",
                "name": "governance-operations-console",
                "record_id": "product:governance-operations-console",
            },
        },
        "receipt": {
            "action": action,
            "receipt_id": f"workspace-inventory-lifecycle-receipt:{action}:1273",
            "receipt_digest": digest,
        },
        "merged_state": {
            "action": action,
            "authority_revision": str(version) * 40,
            "history_event_ref": event,
            "record": {
                "version": version,
                "record_digest": DIGESTS["a"] if posture == "active" else DIGESTS["b"],
                "posture": posture,
            },
        },
    }


def manifest(
    *, revision: str, lifecycle_state: str, posture: str,
    binding: dict | None = None,
) -> dict:
    value = {
        "schema_version": 2 if binding else 1,
        "artifact_type": "product-publication-owner-manifest",
        "manifest_id": "product-publication-manifest:governance-operations-console:1",
        "product_id": "product:governance-operations-console",
        "product_record_ref": "workspace-governance://products/governance-operations-console/v1",
        "product_record_version": 1,
        "product_classification": "owner-managed",
        "lifecycle_state": lifecycle_state,
        "owner_repo": "governance-operations-console",
        "owner_role": "runtime-owner",
        "owner_revision": REVISIONS["source"],
        "source_refs": [{
            "repo": "governance-operations-console",
            "revision": REVISIONS["source"],
            "path": "src/domain-workspaces/portfolio",
        }],
        "lifecycle_evidence": {
            "project_phase": "operational",
            "source_custody": "dedicated-owner-repo",
            "runtime_environment": "dev-integration",
            "release_posture": "not-applicable",
            "publication_posture": posture,
            "evidence_refs": [f"git://governance-operations-console/{revision}"],
        },
        "issued_at": "2026-10-13T00:00:00Z",
    }
    if binding:
        value["inventory_lifecycle_binding"] = binding
    return value


def result(
    policy: dict, *, action: str, before: str, after: str, version: int,
    previous: dict, revision: str, digest: str,
    lifecycle_binding: dict | None = None,
    history: list[dict] | None = None,
) -> dict:
    command = {
        "schema_version": 2 if action in {"archive", "restore"} else 1,
        "action": action,
        "current_publication_posture": before,
        "expected_publication_version": version - 1,
        "previous_receipt": {
            key: value for key, value in previous.items()
            if key != "publication_posture" or action in {"archive", "restore"}
        },
        "security_decision": module.command_security_decision(policy),
        "target_publication": policy["product_publication"]["allowed_targets"][after],
        "manifest_source": {
            "repo": "governance-operations-console",
            "path": "product-publication/manifest.json",
            "source_revision": REVISIONS["source"],
            "manifest_revision": revision,
            "manifest_digest": digest,
        },
    }
    readiness = {
        "manifest_binding": {
            "manifest_digest": digest,
            "owner_repo": "governance-operations-console",
        },
    }
    if lifecycle_binding:
        readiness["inventory_lifecycle_binding"] = lifecycle_binding
    return {
        "state": "applied",
        "request_id": f"product-publication-request:1273:{action}",
        "command": command,
        "readiness": {"readiness": readiness},
        "packet": {"grants": {
            "source_authority": False,
            "runtime_authority": False,
            "release_authority": False,
            "security_acceptance": False,
            "lifecycle_mutation": False,
        }},
        "receipt": {
            "receipt_id": f"product-publication-receipt:1273:{action}",
            "publication_version": version,
            "publication_posture": after,
        },
        "receipt_digest": DIGESTS[str(version)],
        "maintenance_projection": {"history": history or []},
    }


def fixture(policy: dict) -> tuple[dict, dict, dict, dict]:
    retire_event = {**artifact("workspace-inventory-history-event:retire:1273", DIGESTS["7"]), "sequence": 11}
    restore_event = {**artifact("workspace-inventory-history-event:restore:1273", DIGESTS["8"]), "sequence": 12}
    retired = lifecycle(
        "retire", "retired", 11, DIGESTS["6"],
        artifact(retire_event["id"], retire_event["digest"]),
    )
    restored = lifecycle(
        "restore", "active", 12, DIGESTS["5"],
        artifact(restore_event["id"], restore_event["digest"]),
    )
    restored["request"]["prior_event_ref"] = artifact(
        retire_event["id"], retire_event["digest"]
    )
    retire_ref = artifact(retired["receipt"]["receipt_id"], retired["receipt"]["receipt_digest"])
    restore_ref = artifact(restored["receipt"]["receipt_id"], restored["receipt"]["receipt_digest"])
    retire_binding = {
        "action": "retire",
        "receipt_ref": retire_ref,
        "history_event_ref": retire_event,
        "previous_event_ref": None,
        "after": {"record_version": 11, "record_digest": DIGESTS["b"], "posture": "retired"},
    }
    restore_binding = {
        "action": "restore",
        "receipt_ref": restore_ref,
        "history_event_ref": restore_event,
        "previous_event_ref": artifact(retire_event["id"], retire_event["digest"]),
        "after": {"record_version": 12, "record_digest": DIGESTS["a"], "posture": "active"},
    }
    manifests = {
        REVISIONS["active"]: manifest(revision=REVISIONS["active"], lifecycle_state="active", posture="internal"),
        REVISIONS["retired"]: manifest(revision=REVISIONS["retired"], lifecycle_state="retired", posture="unlisted", binding=retire_binding),
        REVISIONS["restored"]: manifest(revision=REVISIONS["restored"], lifecycle_state="active", posture="unlisted", binding=restore_binding),
        REVISIONS["final"]: manifest(revision=REVISIONS["final"], lifecycle_state="active", posture="internal", binding=restore_binding),
    }
    manifest_digests = {revision: module.canonical_digest(value) for revision, value in manifests.items()}
    prior = policy["product_publication"]["existing_internal_publication"]
    previous = {
        "receipt_id": prior["receipt_id"],
        "receipt_digest": prior["receipt_digest"],
        "publication_version": 1,
        "publication_posture": "internal",
    }
    publications = {}
    publications["unpublish"] = result(
        policy, action="unpublish", before="internal", after="unlisted", version=2,
        previous=previous, revision=REVISIONS["active"], digest=manifest_digests[REVISIONS["active"]],
    )
    previous = module.previous_receipt({
        "receipt_id": publications["unpublish"]["receipt"]["receipt_id"],
        "receipt_digest": publications["unpublish"]["receipt_digest"],
        "publication_version": 2, "publication_posture": "unlisted",
    })
    publications["archive"] = result(
        policy, action="archive", before="unlisted", after="archived", version=3,
        previous=previous, revision=REVISIONS["retired"], digest=manifest_digests[REVISIONS["retired"]],
        lifecycle_binding=retire_binding,
    )
    previous = module.previous_receipt({
        "receipt_id": publications["archive"]["receipt"]["receipt_id"],
        "receipt_digest": publications["archive"]["receipt_digest"],
        "publication_version": 3, "publication_posture": "archived",
    })
    publications["restore"] = result(
        policy, action="restore", before="archived", after="unlisted", version=4,
        previous=previous, revision=REVISIONS["restored"], digest=manifest_digests[REVISIONS["restored"]],
        lifecycle_binding=restore_binding,
    )
    previous = module.previous_receipt({
        "receipt_id": publications["restore"]["receipt"]["receipt_id"],
        "receipt_digest": publications["restore"]["receipt_digest"],
        "publication_version": 4, "publication_posture": "unlisted",
    })
    history = [
        {"action": "publish", "publication_posture": "internal"},
        {"action": "unpublish", "publication_posture": "unlisted"},
        {"action": "archive", "publication_posture": "archived"},
        {"action": "restore", "publication_posture": "unlisted"},
        {"action": "publish", "publication_posture": "internal"},
    ]
    publications["publish"] = result(
        policy, action="publish", before="unlisted", after="internal", version=5,
        previous=previous, revision=REVISIONS["restored"], digest=manifest_digests[REVISIONS["restored"]],
        lifecycle_binding=None, history=history,
    )
    evidence = {
        "schema_version": 1,
        "product_id": "product:governance-operations-console",
        "publication_request_ids": {key: value["request_id"] for key, value in publications.items()},
        "inventory_request_ids": {"retire": retired["request_id"], "restore": restored["request_id"]},
        "final_manifest": {
            "revision": REVISIONS["final"],
            "digest": manifest_digests[REVISIONS["final"]],
            "source_revision": REVISIONS["source"],
        },
    }
    return evidence, publications, {"retire": retired, "restore": restored}, manifests


class ProductPublicationPlatformTests(unittest.TestCase):
    def test_current_workspace_authority_requires_unchanged_reviewed_bundle(self) -> None:
        policy = module.load_policy()
        current = "f" * 40
        authority_files = {
            "contracts/product-publication.yaml": b"policy\n",
            "contracts/schemas/product-publication-manifest.schema.json": b"{}\n",
            "contracts/schemas/workspace-inventory-history.schema.json": b"history\n",
        }
        bundle = {
            "authority_repo": "workspace-governance",
            "authority_commit": policy["product_publication"]["authority_revision"],
            "authority_files": {
                path: module.sha256(raw).removeprefix("sha256:")
                for path, raw in authority_files.items()
            },
        }

        def repo_path(name: str) -> Path:
            return Path(f"/{name}")

        def git_file(repo: Path, revision: str, path: str) -> bytes:
            if repo == Path("/workspace-governance-control-fabric"):
                self.assertEqual(revision, policy["owners"]["wgcf"]["revision"])
                return json.dumps(bundle).encode()
            self.assertEqual(repo, Path("/workspace-governance"))
            self.assertEqual(revision, current)
            return authority_files[path]

        with (
            patch.object(module.base, "repo_path", side_effect=repo_path),
            patch.object(module.base, "require_source_authority") as require_source,
            patch.object(module.base, "git_head", return_value=current),
            patch.object(module, "git_file", side_effect=git_file),
        ):
            self.assertEqual(module.workspace_authority_revision(policy), current)
        require_source.assert_called_once_with({
            "repo": "workspace-governance",
            "minimum_revision": policy["product_publication"]["security_reviewed_authority_revision"],
        })

    def test_current_workspace_authority_rejects_contract_drift(self) -> None:
        policy = module.load_policy()
        bundle = {
            "authority_repo": "workspace-governance",
            "authority_commit": policy["product_publication"]["authority_revision"],
            "authority_files": {"contracts/product-publication.yaml": "0" * 64},
        }
        with (
            patch.object(module.base, "repo_path", side_effect=lambda name: Path(f"/{name}")),
            patch.object(module.base, "require_source_authority"),
            patch.object(module.base, "git_head", return_value="f" * 40),
            patch.object(module, "git_file", side_effect=[
                json.dumps(bundle).encode(),
                b"changed policy\n",
            ]),
        ):
            with self.assertRaisesRegex(
                module.ProductPublicationError,
                "changes the reviewed Product Publication authority bundle",
            ):
                module.workspace_authority_revision(policy)

    def test_activate_primes_security_binding_before_cross_domain_runtime_wait(self) -> None:
        policy = module.load_policy()
        observed: list[str] = []
        with (
            patch.object(module, "validate", side_effect=lambda _policy: observed.append("validate")),
            patch.object(
                module,
                "configure_oos_security_binding",
                side_effect=lambda _policy: observed.append("prime-security-binding"),
            ),
            patch.object(module.base, "activate", side_effect=lambda _policy: observed.append("base-activate")),
            patch.object(
                module,
                "configure_workloads",
                side_effect=lambda _policy: observed.append("configure-workloads"),
            ),
            patch.object(
                module,
                "product_health_proof",
                side_effect=lambda: observed.append("project-product-health") or {"freshness": "current"},
            ),
            patch.object(
                module,
                "write_console_environment",
                side_effect=lambda _policy: observed.append("write-console-environment"),
            ),
            patch.object(module, "runtime_status", return_value={"ready": True}),
            patch.object(module, "receipt", return_value=Path("activation-receipt.json")),
        ):
            self.assertEqual(module.activate(policy), Path("activation-receipt.json"))
        self.assertEqual(observed, [
            "validate",
            "prime-security-binding",
            "base-activate",
            "configure-workloads",
            "project-product-health",
            "write-console-environment",
        ])

    def test_console_environment_activates_publication_and_maintenance_together(self) -> None:
        policy = module.load_policy()
        with tempfile.TemporaryDirectory() as directory:
            private_root = Path(directory) / "private"
            state_root = Path(directory) / "product-publication"
            private_root.mkdir()
            state_root.mkdir()
            environment = private_root / "console.env"
            environment.write_text("OOS_BASE_URL=http://127.0.0.1:38180\n", encoding="utf-8")
            with (
                patch.object(module.base, "PRIVATE_ROOT", private_root),
                patch.object(module, "STATE_ROOT", state_root),
                patch.object(module, "workspace_authority_revision", return_value="a" * 40),
                patch.object(module.base, "run"),
            ):
                module.write_console_environment(policy)

            values = dict(
                line.split("=", 1)
                for line in environment.read_text(encoding="utf-8").splitlines()
            )
            self.assertEqual(values["OOS_BASE_URL"], "http://127.0.0.1:38180")
            self.assertEqual(
                values["GOVERNANCE_CONSOLE_PRODUCT_MAINTENANCE_AUTHORITY_REVISION"],
                "a" * 40,
            )
            self.assertEqual(
                values["GOVERNANCE_CONSOLE_PRODUCT_MAINTENANCE_SECURITY_DECISION_URI"],
                policy["product_publication"]["security_decision"]["uri"],
            )
            self.assertEqual(
                values["GOVERNANCE_CONSOLE_PRODUCT_HEALTH_PROJECTION_PATH"],
                str(state_root / "product-health.json"),
            )
            self.assertEqual(
                values["GOVERNANCE_CONSOLE_PRODUCT_HEALTH_RECEIPT_PATH"],
                str(state_root / "product-health.receipt.json"),
            )

    def test_policy_binds_1273_and_exact_approved_scope(self) -> None:
        policy = module.load_policy()
        self.assertEqual(policy["activation"], {
            "delivery_id": "delivery-894",
            "work_item_ref": "openproject://work_packages/1273",
            "security_gate_id": "gate:product-publication-lifecycle-maintenance-activation",
        })
        self.assertEqual(
            policy["console"]["minimum_revision"],
            "9c1b9117a98a59662ba570d90bce01bc0b869fb0",
        )
        self.assertEqual(policy["product_publication"]["allowed_actions"], [
            "publish", "unpublish", "archive", "restore",
        ])
        self.assertEqual(set(policy["product_publication"]["allowed_targets"]), {
            "internal", "unlisted", "archived",
        })
        self.assertEqual(policy["product_publication"]["denied_targets"], ["client", "public"])
        self.assertEqual(policy["owners"]["oos"]["revision"], "94534d621aa9300b51035cd05554f27b6b4e3180")

    def test_case_1273_positive_validates_complete_order_and_fresh_manifests(self) -> None:
        policy = module.load_policy()
        evidence, publications, lifecycles, manifests = fixture(policy)
        self.assertNotIn("sequence", lifecycles["retire"]["merged_state"]["history_event_ref"])
        self.assertNotIn("sequence", lifecycles["restore"]["merged_state"]["history_event_ref"])
        with (
            patch.object(module, "manifest_at", side_effect=lambda _policy, revision: (
                manifests[revision], module.canonical_digest(manifests[revision])
            )),
            patch.object(module.base, "repo_path", return_value=Path("/owner")),
            patch.object(module.base, "run", return_value=Mock(returncode=0)),
        ):
            proof = module.validate_sequence(policy, evidence, publications, lifecycles)
        self.assertEqual(proof["final_state"], {
            "lifecycle": "active", "publication_posture": "internal", "publication_version": 5,
        })
        self.assertTrue(proof["immutable_history_verified"])
        self.assertEqual(set(proof["manifests"]), {
            "active-internal", "retired-unlisted", "active-unlisted-restored", "active-internal-final",
        })

    def test_case_1273_negative_rejects_reordered_or_copied_evidence(self) -> None:
        policy = module.load_policy()
        evidence, publications, lifecycles, manifests = fixture(policy)
        publications["archive"]["command"]["current_publication_posture"] = "internal"
        with (
            patch.object(module, "manifest_at", side_effect=lambda _policy, revision: (
                manifests[revision], module.canonical_digest(manifests[revision])
            )),
            patch.object(module.base, "repo_path", return_value=Path("/owner")),
            patch.object(module.base, "run", return_value=Mock(returncode=0)),
        ):
            with self.assertRaisesRegex(module.ProductPublicationError, "archive result is not exact"):
                module.validate_sequence(policy, evidence, publications, lifecycles)

    def test_case_1273_negative_requires_every_named_fail_closed_outcome(self) -> None:
        names = {
            "retirement-before-unpublish", "stale-or-copied-manifest",
            "archive-without-retirement", "publication-restore-before-registry-restore",
            "direct-listed-restoration", "client-target", "public-target",
            "unauthorized-caller", "replay-conflict", "interrupted-operation",
        }
        evidence = {"negative_outcomes": {
            name: {"denied": True, "canonical_state_changed": False, "evidence_ref": f"receipt://{name}"}
            for name in names
        }}
        self.assertEqual(set(module.require_negative_evidence(evidence)), names)
        evidence["negative_outcomes"]["archive-without-retirement"]["canonical_state_changed"] = True
        with self.assertRaisesRegex(module.ProductPublicationError, "archive-without-retirement"):
            module.require_negative_evidence(evidence)

    def test_process_loss_restores_oos_without_creating_state(self) -> None:
        policy = module.load_policy()
        positive = {
            "request_id": "product-publication-request:1273:publish",
            "receipt_digest": DIGESTS["5"],
            "command": {"request_id": "product-publication-request:1273:publish", "idempotency_key": "publication:1273:publish"},
        }

        def kubectl(*args):
            if "get" in args:
                return Mock(stdout=json.dumps({"status": {"readyReplicas": 0}}))
            return Mock(stdout="")

        with (
            patch.object(module.base, "kubectl", side_effect=kubectl),
            patch.object(module.base, "run", return_value=Mock(returncode=0)),
            patch.object(module, "product_mode", return_value={"mode": "live"}),
            patch.object(module, "console_request", side_effect=[
                (503, {"code": "product_publication_oos_unavailable"}),
                (404, {"code": "not_found"}),
                (200, {"receipt_digest": positive["receipt_digest"]}),
            ]),
        ):
            proof = module.process_loss_and_recovery(policy, positive)
        self.assertTrue(proof["interrupted_state_absent"])
        self.assertEqual(proof["accepted_receipt_digest"], positive["receipt_digest"])

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
                self.assertEqual(digest, module.sha256(json.dumps(
                    value, sort_keys=True, separators=(",", ":"),
                ).encode()))


if __name__ == "__main__":
    unittest.main()
