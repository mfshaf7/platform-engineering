"""Filesystem publication and independent scheduler witnesses; no live claims."""
from datetime import datetime, timedelta, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import console_observation_refresh as refresh


class ObservationRefreshTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="observation-refresh-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.now = datetime(2026, 10, 28, 1, 0, tzinfo=timezone.utc)
        self.calls = []

    def runner(self, command):
        self.calls.append(command)
        return subprocess.CompletedProcess(command, 0,
            json.dumps({"spec": {"replicas": 1}, "status": {"readyReplicas": 1}}), "")

    def publish(self, runner=None):
        return refresh.refresh(self.root, operator="mfshaf7", now=self.now, runner=runner or self.runner)

    def test_existing_admitted_set_publishes_both_consumers_and_expires_without_retimestamping(self):
        self.publish()
        root, runtime_path, health_path, receipt_path = refresh.paths(self.root)
        runtime = json.loads(runtime_path.read_text())
        health = json.loads(health_path.read_text())
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(6, len(self.calls))
        self.assertTrue(all(command[:2] == ["k3s", "kubectl"] and "get" in command for command in self.calls))
        self.assertEqual(runtime["source"]["reference"], health["source"]["runtimeObservationRef"])
        self.assertEqual(refresh.observations.digest(health), receipt["projection_digest"])
        for product in health["products"]:
            if not product["evidence"]:
                self.assertEqual("unknown", product["availability"]["state"])
                self.assertEqual("no_runtime_observation_admitted", product["availability"]["reasonCode"])
        for path in (runtime_path, health_path, receipt_path):
            self.assertEqual(0o600, path.stat().st_mode & 0o777)
        self.assertEqual(0o700, root.stat().st_mode & 0o777)
        before = runtime_path.read_bytes()
        run = lambda command, **kwargs: subprocess.CompletedProcess(command, 0, "", "")
        self.assertTrue(refresh.status(self.root, run=run, now=self.now)["timer_active"])
        with self.assertRaisesRegex(refresh.observations.ObservationError, "stale"):
            refresh.status(self.root, run=run, now=self.now + timedelta(seconds=121))
        self.assertEqual(before, runtime_path.read_bytes())

    def test_collection_failure_preserves_old_bytes_and_next_refresh_recovers(self):
        self.publish()
        files = refresh.paths(self.root)[1:]
        before = [path.read_bytes() for path in files]
        def denied(command):
            return subprocess.CompletedProcess(command, 1, "", "synthetic unavailable API")
        self.now += timedelta(seconds=30)
        with self.assertRaises(refresh.observations.ObservationError):
            self.publish(denied)
        self.assertEqual(before, [path.read_bytes() for path in files])
        self.publish()
        self.assertNotEqual(before, [path.read_bytes() for path in files])

    def test_nonoverlap_denies_before_collection_and_timeout_is_bounded(self):
        self.publish()
        self.calls.clear()
        with (refresh.paths(self.root)[0] / "refresh.lock").open("r+") as owner:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(refresh.observations.ObservationError, "already running"):
                self.publish()
        self.assertEqual([], self.calls)
        with patch.object(refresh.subprocess, "run", side_effect=subprocess.TimeoutExpired("k3s", 10)) as command:
            with self.assertRaisesRegex(refresh.observations.ObservationError, "timed out"):
                refresh.bounded_runner(["k3s", "kubectl", "get", "deployment"])
        self.assertEqual(10, command.call_args.kwargs["timeout"])

    def test_atomic_write_failure_never_leaves_partial_json(self):
        self.publish()
        runtime_path = refresh.paths(self.root)[1]
        before = runtime_path.read_bytes()
        self.now += timedelta(seconds=30)
        with patch.object(refresh.observations.json, "dump", side_effect=OSError("synthetic disk failure")):
            with self.assertRaises(OSError):
                self.publish()
        self.assertEqual(before, runtime_path.read_bytes())
        self.assertEqual([], list(runtime_path.parent.glob(".runtime.json.*")))

    def test_timer_has_own_bounded_service_without_credential_refresh(self):
        units = self.root / "units"
        calls = []
        repo_root = Path(refresh.__file__).resolve().parents[3]
        refresh.install(repo_root=repo_root, state_root=self.root, unit_root=units,
            run=lambda command: calls.append(command))
        service = (units / refresh.SERVICE).read_text()
        timer = (units / refresh.TIMER).read_text()
        self.assertIn("refresh-observations", service)
        self.assertNotIn("refresh-credentials", service)
        self.assertIn("TimeoutStartSec=80", service)
        self.assertIn("MemoryMax=256M", service)
        self.assertIn("OnUnitInactiveSec=30s", timer)
        self.assertIn(["systemctl", "--user", "enable", "--now", refresh.TIMER], calls)


if __name__ == "__main__":
    unittest.main()
