#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


MODULE_PATH = Path(__file__).with_name("console_runtime_observations.py")
SPEC = importlib.util.spec_from_file_location("console_runtime_observations", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ConsoleRuntimeObservationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="console-runtime-observations-")
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.now = datetime(2026, 9, 27, 8, 0, tzinfo=timezone.utc)
        self.policy = MODULE.load_policy()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def response(
        args: list[str],
        *,
        desired: int = 1,
        ready: int = 1,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps(
                {
                    "spec": {"replicas": desired},
                    "status": {"readyReplicas": ready},
                }
            ),
            stderr="",
        )

    def ready_runner(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        return self.response(args)

    def test_policy_and_projection_are_bounded_and_secret_free(self) -> None:
        output = self.root / "runtime" / "observations.json"
        receipt = self.root / "runtime" / "receipt.json"

        result = MODULE.project(
            self.policy,
            output,
            receipt,
            operator="mfshaf7",
            now=self.now,
            runner=self.ready_runner,
        )

        value = json.loads(output.read_text())
        MODULE.validate_projection(value)
        self.assertEqual(len(value["components"]), len(self.policy.components))
        self.assertTrue(
            all(component["runtime"]["state"] == "available" for component in value["components"])
        )
        self.assertTrue(
            all(
                capability["posture"] == "runtime-ready"
                for component in value["components"]
                for capability in component["capabilities"]
            )
        )
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)
        self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
        self.assertFalse(result["secret_values_embedded"])
        serialized = json.dumps(value).casefold()
        self.assertNotIn("token", serialized)
        self.assertNotIn("password", serialized)

    def test_product_health_policy_is_exact_and_source_active_for_1273(self) -> None:
        self.assertTrue(self.policy.product_health_runtime_activation)
        self.assertEqual(
            self.policy.inventory_authority,
            {
                "repo": "workspace-governance",
                "revision": "fab38a8266512b0004081039b017904c9c55f288",
                "path": "contracts/products.yaml",
                "sha256": "bf8c30d904731c922f60fb669246c7bb3e0c4eb64e7a5f11be4e31fda77b874a",
            },
        )
        self.assertEqual(
            [product.product_id for product in self.policy.products],
            ["product:openproject", "product:openclaw", "product:governance-operations-console"],
        )

    def test_case_1269_positive_projects_independent_product_health_and_owner_routes(self) -> None:
        runtime = MODULE.build_projection(
            self.policy,
            operator="mfshaf7",
            now=self.now,
            runner=self.ready_runner,
        )
        value = MODULE.build_product_health_projection(
            self.policy,
            runtime,
            now=self.now,
        )
        MODULE.validate_product_health_projection(value, runtime_projection=runtime, policy=self.policy)
        by_id = {product["productId"]: product for product in value["products"]}
        self.assertEqual(by_id["product:openproject"]["availability"]["state"], "available")
        self.assertEqual(by_id["product:openproject"]["freshness"], "current")
        self.assertEqual(by_id["product:openproject"]["runtimeOwner"], "platform-engineering")
        self.assertEqual(by_id["product:openproject"]["evidence"][0]["componentId"], "openproject")
        self.assertEqual(by_id["product:openclaw"]["availability"], {
            "state": "unknown",
            "reasonCode": "no_runtime_observation_admitted",
        })
        self.assertEqual(by_id["product:openclaw"]["recovery"]["owner"], "openclaw-runtime-distribution")
        self.assertTrue(all(grant is False for grant in value["grants"].values()))
        self.assertEqual(value["source"]["runtimeObservationRef"], runtime["source"]["reference"])
        self.assertEqual(value["source"]["runtimeObservationDigest"], MODULE.digest(runtime))
        self.assertNotIn("token", json.dumps(value).casefold())
        receipt = MODULE.create_product_health_receipt(self.policy, value, now=self.now)
        self.assertFalse(receipt["secret_values_embedded"])
        self.assertEqual(receipt["freshness"], "current")
        self.assertEqual(receipt["counts"], {
            "available": 1,
            "degraded": 0,
            "unavailable": 0,
            "unknown": 2,
        })
        self.assertEqual(
            MODULE.build_product_health_projection(self.policy, runtime, now=self.now),
            value,
        )

    def test_case_1273_negative_fails_closed_for_stale_and_contradictory_evidence(self) -> None:
        runtime = MODULE.build_projection(
            self.policy,
            operator="mfshaf7",
            now=self.now,
            runner=self.ready_runner,
        )
        stale = MODULE.build_product_health_projection(
            self.policy,
            runtime,
            now=self.now + timedelta(seconds=self.policy.maximum_age_seconds + 1),
        )
        self.assertTrue(all(product["freshness"] == "stale" for product in stale["products"]))
        self.assertTrue(all(product["availability"]["state"] == "unknown" for product in stale["products"]))
        stale_summary = MODULE.product_health_summary(
            MODULE.build_product_health_projection(self.policy, runtime, now=self.now),
            now=self.now + timedelta(seconds=self.policy.maximum_age_seconds + 1),
        )
        self.assertEqual(stale_summary["freshness"], "stale")
        self.assertEqual(stale_summary["counts"]["unknown"], 3)

        missing = json.loads(json.dumps(runtime))
        missing["components"] = [
            component for component in missing["components"] if component["id"] != "openproject"
        ]
        missing_health = MODULE.build_product_health_projection(self.policy, missing, now=self.now)
        self.assertEqual(missing_health["products"][0]["availability"], {
            "state": "unknown",
            "reasonCode": "required_observation_missing",
        })

        exact = MODULE.build_product_health_projection(self.policy, runtime, now=self.now)
        exact["source"]["runtimeObservationDigest"] = "sha256:" + "0" * 64
        exact["source"]["reference"] = MODULE.product_health_reference(exact)
        with self.assertRaisesRegex(MODULE.ObservationError, "exact runtime observation"):
            MODULE.validate_product_health_projection(
                exact,
                runtime_projection=runtime,
                policy=self.policy,
            )

        runtime_path = self.root / "runtime.json"
        runtime_path.write_text(json.dumps(runtime))
        output = self.root / "product-health.json"
        receipt = self.root / "product-health-receipt.json"
        projected_receipt = MODULE.project_product_health(
            self.policy, runtime_path, output, receipt, now=self.now,
        )
        projected = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(projected["source"]["runtimeObservationDigest"], MODULE.digest(runtime))
        self.assertEqual(projected_receipt["freshness"], "current")
        self.assertTrue(output.is_file())
        self.assertTrue(receipt.is_file())

    def test_product_health_maps_degraded_and_unavailable_without_workflow_claims(self) -> None:
        degraded_runtime = MODULE.build_projection(
            self.policy,
            operator="mfshaf7",
            now=self.now,
            runner=lambda args: self.response(args, desired=2, ready=1)
            if any("openproject-web" in argument for argument in args)
            else self.response(args),
        )
        degraded = MODULE.build_product_health_projection(self.policy, degraded_runtime, now=self.now)
        self.assertEqual(degraded["products"][0]["availability"]["state"], "degraded")
        self.assertEqual(degraded["products"][0]["issues"]["state"], "attention")

        unavailable_runtime = MODULE.build_projection(
            self.policy,
            operator="mfshaf7",
            now=self.now,
            runner=lambda args: self.response(args, desired=1, ready=0)
            if any("openproject-web" in argument for argument in args)
            else self.response(args),
        )
        unavailable = MODULE.build_product_health_projection(self.policy, unavailable_runtime, now=self.now)
        self.assertEqual(unavailable["products"][0]["availability"]["state"], "unavailable")
        self.assertFalse(unavailable["grants"]["runtime_mutation"])

    def test_runtime_state_distinguishes_degraded_missing_and_scaled_down(self) -> None:
        calls = 0

        def mixed_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            nonlocal calls
            calls += 1
            if calls == 1:
                return self.response(args, desired=2, ready=1)
            if calls == 2:
                return subprocess.CompletedProcess(
                    args,
                    1,
                    stdout="",
                    stderr='Error from server (NotFound): deployments.apps "missing" not found',
                )
            if calls == 3:
                return self.response(args, desired=0, ready=0)
            return self.response(args)

        value = MODULE.build_projection(
            self.policy,
            operator="mfshaf7",
            now=self.now,
            runner=mixed_runner,
        )

        states = [component["runtime"] for component in value["components"][:3]]
        self.assertEqual(states[0]["state"], "degraded")
        self.assertEqual(states[0]["reasonCode"], "runtime_partially_ready")
        self.assertEqual(states[1]["state"], "unavailable")
        self.assertEqual(states[1]["reasonCode"], "runtime_not_found")
        self.assertEqual(states[2]["reasonCode"], "runtime_scaled_down")

    def test_untrusted_command_failure_does_not_publish_a_projection(self) -> None:
        def failed_runner(args: list[str]) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args,
                1,
                stdout="",
                stderr="forbidden",
            )

        output = self.root / "runtime" / "observations.json"
        with self.assertRaisesRegex(MODULE.ObservationError, "command failed"):
            MODULE.project(
                self.policy,
                output,
                self.root / "runtime" / "receipt.json",
                operator="mfshaf7",
                now=self.now,
                runner=failed_runner,
            )
        self.assertFalse(output.exists())

    def test_inspection_marks_expired_projection_stale(self) -> None:
        value = MODULE.build_projection(
            self.policy,
            operator="mfshaf7",
            now=self.now,
            runner=self.ready_runner,
        )
        current = MODULE.projection_summary(value, now=self.now)
        stale = MODULE.projection_summary(
            value,
            now=self.now + timedelta(seconds=self.policy.maximum_age_seconds + 1),
        )
        self.assertEqual(current["freshness"], "current")
        self.assertEqual(stale["freshness"], "stale")

    def test_projection_rejects_mismatched_component_time(self) -> None:
        value = MODULE.build_projection(
            self.policy,
            operator="mfshaf7",
            now=self.now,
            runner=self.ready_runner,
        )
        value["components"][0]["observedAt"] = "2026-09-27T07:59:00Z"
        with self.assertRaisesRegex(MODULE.ObservationError, "must match"):
            MODULE.validate_projection(value)

    def test_operator_and_owner_runbooks_are_admitted(self) -> None:
        self.assertEqual(len(self.policy.components), 6)
        with self.assertRaisesRegex(MODULE.ObservationError, "lowercase workspace identifier"):
            MODULE.build_projection(
                self.policy,
                operator="Bad Operator",
                now=self.now,
                runner=self.ready_runner,
            )


if __name__ == "__main__":
    unittest.main()
