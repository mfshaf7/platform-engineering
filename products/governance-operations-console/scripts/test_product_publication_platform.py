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
    retired = lifecycle("retire", "retired", 11, DIGESTS["6"], retire_event)
    restored = lifecycle("restore", "active", 12, DIGESTS["5"], restore_event)
    restored["request"]["prior_event_ref"] = retire_event
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
        "previous_event_ref": retire_event,
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
        self.assertEqual(policy["owners"]["oos"]["revision"], "2bb51556202a9f3819ca99bad3cad06256480db9")

    def test_case_1273_positive_validates_complete_order_and_fresh_manifests(self) -> None:
        policy = module.load_policy()
        evidence, publications, lifecycles, manifests = fixture(policy)
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
