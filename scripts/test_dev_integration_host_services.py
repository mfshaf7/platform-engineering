#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

import yaml

import dev_integration_host_services as HOST_SERVICES


class DevIntegrationHostServiceTests(unittest.TestCase):
    def create_script(self, root: Path, name: str, source: str) -> Path:
        path = root / name
        path.write_text(f"#!/usr/bin/env bash\nset -euo pipefail\n{source}\n", encoding="utf-8")
        path.chmod(0o700)
        return path

    def profile(self, command: str, readiness: dict | None = None) -> dict:
        return {
            "host_services": [
                {
                    "id": "test-service",
                    "command": command,
                    "readiness": readiness or {"mode": "process"},
                }
            ]
        }

    def test_declared_service_survives_reconcile_and_stops_deterministically(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-host-service-") as temp_dir:
            root = Path(temp_dir)
            owner = root / "owner"
            state_root = root / "state"
            owner.mkdir()
            self.create_script(owner, "service.sh", 'trap "exit 0" TERM INT\nwhile true; do sleep 0.1; done')
            self.create_script(owner, "ready.sh", 'kill -0 "${DEVINT_HOST_SERVICE_PID}"')
            specs = HOST_SERVICES.resolve_host_services(
                self.profile(
                    "service.sh",
                    {
                        "mode": "command",
                        "command": "ready.sh",
                        "timeout_seconds": 2,
                        "interval_seconds": 0.05,
                        "probe_timeout_seconds": 1,
                    },
                ),
                owner,
            )
            first = HOST_SERVICES.reconcile_host_services(
                specs,
                state_root=state_root,
                cwd=owner,
                env=dict(os.environ),
            )
            pid = first[0]["pid"]
            try:
                self.assertTrue(first[0]["healthy"])
                self.assertIsNotNone(HOST_SERVICES._process_start_ticks(pid))
                second = HOST_SERVICES.reconcile_host_services(
                    specs,
                    state_root=state_root,
                    cwd=owner,
                    env=dict(os.environ),
                )
                self.assertEqual(second[0]["pid"], pid)
                state_file = state_root / "host-services/test-service/service.yaml"
                state = yaml.safe_load(state_file.read_text(encoding="utf-8"))
                self.assertEqual(state["command_digest"], specs[0].command_digest)
                self.assertRegex(state["command_digest"], r"^sha256:[0-9a-f]{64}$")
                self.assertEqual(state_file.stat().st_mode & 0o777, 0o600)
                stopped = HOST_SERVICES.stop_host_services(specs, state_root=state_root)
                self.assertEqual(stopped[0]["status"], "stopped")
                deadline = time.monotonic() + 2
                while HOST_SERVICES._process_start_ticks(pid) is not None and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertIsNone(HOST_SERVICES._process_start_ticks(pid))
            finally:
                if HOST_SERVICES._process_start_ticks(pid) is not None:
                    os.killpg(pid, signal.SIGKILL)

    def test_failed_readiness_does_not_leave_a_service_running(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-host-service-fail-") as temp_dir:
            root = Path(temp_dir)
            owner = root / "owner"
            state_root = root / "state"
            owner.mkdir()
            self.create_script(owner, "service.sh", 'trap "exit 0" TERM INT\nwhile true; do sleep 0.1; done')
            self.create_script(owner, "not-ready.sh", "exit 1")
            specs = HOST_SERVICES.resolve_host_services(
                self.profile(
                    "service.sh",
                    {
                        "mode": "command",
                        "command": "not-ready.sh",
                        "timeout_seconds": 0.2,
                        "interval_seconds": 0.05,
                        "probe_timeout_seconds": 0.1,
                    },
                ),
                owner,
            )
            with self.assertRaisesRegex(HOST_SERVICES.HostServiceError, "did not become ready"):
                HOST_SERVICES.reconcile_host_services(
                    specs,
                    state_root=state_root,
                    cwd=owner,
                    env=dict(os.environ),
                )
            state = yaml.safe_load(
                (state_root / "host-services/test-service/service.yaml").read_text(encoding="utf-8")
            )
            self.assertEqual(state["status"], "failed")
            self.assertIsNone(state["pid"])

    def test_process_readiness_rejects_command_that_cannot_exec(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-host-service-exec-") as temp_dir:
            root = Path(temp_dir)
            owner = root / "owner"
            state_root = root / "state"
            owner.mkdir()
            command = owner / "service"
            command.write_text("not an executable format\n", encoding="utf-8")
            command.chmod(0o700)
            specs = HOST_SERVICES.resolve_host_services(self.profile("service"), owner)
            with self.assertRaisesRegex(HOST_SERVICES.HostServiceError, "launcher failed"):
                HOST_SERVICES.reconcile_host_services(
                    specs,
                    state_root=state_root,
                    cwd=owner,
                    env=dict(os.environ),
                )

    def test_changed_command_replaces_the_recorded_process(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-host-service-change-") as temp_dir:
            root = Path(temp_dir)
            owner = root / "owner"
            state_root = root / "state"
            owner.mkdir()
            command = self.create_script(
                owner,
                "service.sh",
                'trap "exit 0" TERM INT\nwhile true; do sleep 0.1; done',
            )
            first_specs = HOST_SERVICES.resolve_host_services(self.profile("service.sh"), owner)
            first = HOST_SERVICES.reconcile_host_services(
                first_specs,
                state_root=state_root,
                cwd=owner,
                env=dict(os.environ),
            )[0]
            first_pid = first["pid"]
            try:
                command.write_text(
                    '#!/usr/bin/env bash\nset -euo pipefail\ntrap "exit 0" TERM INT\nwhile true; do sleep 0.2; done\n',
                    encoding="utf-8",
                )
                second_specs = HOST_SERVICES.resolve_host_services(self.profile("service.sh"), owner)
                second = HOST_SERVICES.reconcile_host_services(
                    second_specs,
                    state_root=state_root,
                    cwd=owner,
                    env=dict(os.environ),
                )[0]
                self.assertNotEqual(second["pid"], first_pid)
                self.assertNotEqual(second_specs[0].command_digest, first_specs[0].command_digest)
                self.assertIsNone(HOST_SERVICES._process_start_ticks(first_pid))
                HOST_SERVICES.stop_host_services(second_specs, state_root=state_root)
            finally:
                for pid in (first_pid, locals().get("second", {}).get("pid")):
                    if isinstance(pid, int) and HOST_SERVICES._process_start_ticks(pid) is not None:
                        os.killpg(pid, signal.SIGKILL)

    def test_source_revision_change_replaces_the_recorded_process(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-host-service-source-") as temp_dir:
            root = Path(temp_dir)
            owner = root / "owner"
            state_root = root / "state"
            owner.mkdir()
            self.create_script(owner, "service.sh", 'trap "exit 0" TERM INT\nwhile true; do sleep 0.1; done')
            first_specs = HOST_SERVICES.resolve_host_services(
                self.profile("service.sh"),
                owner,
                {"owner": {"head_sha": "a" * 40, "working_tree_sha256": None}},
            )
            first = HOST_SERVICES.reconcile_host_services(
                first_specs,
                state_root=state_root,
                cwd=owner,
                env=dict(os.environ),
            )[0]
            first_pid = first["pid"]
            try:
                second_specs = HOST_SERVICES.resolve_host_services(
                    self.profile("service.sh"),
                    owner,
                    {"owner": {"head_sha": "b" * 40, "working_tree_sha256": None}},
                )
                second = HOST_SERVICES.reconcile_host_services(
                    second_specs,
                    state_root=state_root,
                    cwd=owner,
                    env=dict(os.environ),
                )[0]
                self.assertNotEqual(second["pid"], first_pid)
                self.assertNotEqual(second_specs[0].command_digest, first_specs[0].command_digest)
                HOST_SERVICES.stop_host_services(second_specs, state_root=state_root)
            finally:
                for pid in (first_pid, locals().get("second", {}).get("pid")):
                    if isinstance(pid, int) and HOST_SERVICES._process_start_ticks(pid) is not None:
                        os.killpg(pid, signal.SIGKILL)

    def test_concurrent_reconcile_creates_one_owned_process(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-host-service-lock-") as temp_dir:
            root = Path(temp_dir)
            owner = root / "owner"
            state_root = root / "state"
            owner.mkdir()
            self.create_script(owner, "service.sh", 'trap "exit 0" TERM INT\nwhile true; do sleep 0.1; done')
            specs = HOST_SERVICES.resolve_host_services(self.profile("service.sh"), owner)
            child_source = """
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, sys.argv[1])
import dev_integration_host_services as host_services

owner = Path(sys.argv[2])
state_root = Path(sys.argv[3])
profile = {
    "host_services": [
        {
            "id": "test-service",
            "command": "service.sh",
            "readiness": {"mode": "process"},
        }
    ]
}
specs = host_services.resolve_host_services(profile, owner)
projection = host_services.reconcile_host_services(
    specs,
    state_root=state_root,
    cwd=owner,
    env=dict(os.environ),
)[0]
print(json.dumps(projection))
"""
            child_command = [
                sys.executable,
                "-c",
                child_source,
                str(Path(__file__).resolve().parent),
                str(owner),
                str(state_root),
            ]
            children = [
                subprocess.Popen(
                    child_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                for _ in range(2)
            ]
            outputs = [child.communicate(timeout=10) for child in children]
            for child, (_, stderr) in zip(children, outputs, strict=True):
                self.assertEqual(child.returncode, 0, stderr)
            first, second = [json.loads(stdout) for stdout, _ in outputs]
            pid = first["pid"]
            try:
                self.assertEqual(second["pid"], pid)
                self.assertTrue(first["healthy"])
                self.assertTrue(second["healthy"])
                HOST_SERVICES.stop_host_services(specs, state_root=state_root)
            finally:
                if HOST_SERVICES._process_start_ticks(pid) is not None:
                    os.killpg(pid, signal.SIGKILL)

    def test_removed_declaration_is_reported_and_stopped_from_recorded_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-host-service-removed-") as temp_dir:
            root = Path(temp_dir)
            owner = root / "owner"
            state_root = root / "state"
            owner.mkdir()
            self.create_script(owner, "service.sh", 'trap "exit 0" TERM INT\nwhile true; do sleep 0.1; done')
            specs = HOST_SERVICES.resolve_host_services(self.profile("service.sh"), owner)
            running = HOST_SERVICES.reconcile_host_services(
                specs,
                state_root=state_root,
                cwd=owner,
                env=dict(os.environ),
            )[0]
            pid = running["pid"]
            try:
                undeclared = HOST_SERVICES.inspect_host_services(
                    [],
                    state_root=state_root,
                    cwd=owner,
                    env=dict(os.environ),
                )
                self.assertEqual(undeclared[0]["status"], "undeclared")
                stopped = HOST_SERVICES.stop_host_services([], state_root=state_root)
                self.assertEqual(stopped[0]["status"], "stopped")
                self.assertIsNone(HOST_SERVICES._process_start_ticks(pid))
                self.assertEqual(
                    HOST_SERVICES.inspect_host_services(
                        [],
                        state_root=state_root,
                        cwd=owner,
                        env=dict(os.environ),
                    ),
                    [],
                )
                self.assertEqual(
                    HOST_SERVICES.reconcile_host_services(
                        [],
                        state_root=state_root,
                        cwd=owner,
                        env=dict(os.environ),
                    ),
                    [],
                )
            finally:
                if HOST_SERVICES._process_start_ticks(pid) is not None:
                    os.killpg(pid, signal.SIGKILL)

    def test_stop_escalates_when_service_ignores_term(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-host-service-kill-") as temp_dir:
            root = Path(temp_dir)
            owner = root / "owner"
            state_root = root / "state"
            owner.mkdir()
            self.create_script(owner, "service.sh", "trap '' TERM\nwhile true; do sleep 0.1; done")
            specs = HOST_SERVICES.resolve_host_services(self.profile("service.sh"), owner)
            running = HOST_SERVICES.reconcile_host_services(
                specs,
                state_root=state_root,
                cwd=owner,
                env=dict(os.environ),
            )[0]
            pid = running["pid"]
            try:
                stopped = HOST_SERVICES.stop_host_services(specs, state_root=state_root)
                self.assertEqual(stopped[0]["status"], "stopped")
                self.assertIsNone(HOST_SERVICES._process_start_ticks(pid))
            finally:
                if HOST_SERVICES._process_start_ticks(pid) is not None:
                    os.killpg(pid, signal.SIGKILL)

    def test_identity_mismatch_never_kills_an_unrelated_process(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-host-service-identity-") as temp_dir:
            root = Path(temp_dir)
            owner = root / "owner"
            state_root = root / "state"
            owner.mkdir()
            self.create_script(owner, "service.sh", "sleep 30")
            specs = HOST_SERVICES.resolve_host_services(self.profile("service.sh"), owner)
            unrelated = subprocess.Popen(["sleep", "30"], start_new_session=True)
            try:
                state_file = state_root / "host-services/test-service/service.yaml"
                state_file.parent.mkdir(parents=True)
                state_file.write_text(
                    yaml.safe_dump(
                        {
                            "schema_version": 1,
                            "service_id": "test-service",
                            "status": "running",
                            "pid": unrelated.pid,
                            "process_start_ticks": "not-the-real-start-time",
                            "boot_id": HOST_SERVICES._boot_id(),
                            "command_digest": specs[0].command_digest,
                            "state_file": str(state_file),
                            "log_path": str(state_file.with_name("service.log")),
                        },
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )
                with self.assertRaisesRegex(HOST_SERVICES.HostServiceError, "different process"):
                    HOST_SERVICES.stop_host_services(specs, state_root=state_root)
                self.assertIsNone(unrelated.poll())
            finally:
                os.killpg(unrelated.pid, signal.SIGKILL)
                unrelated.wait()

    def test_prior_boot_state_never_kills_a_current_process(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-host-service-boot-") as temp_dir:
            root = Path(temp_dir)
            owner = root / "owner"
            state_root = root / "state"
            owner.mkdir()
            self.create_script(owner, "service.sh", "sleep 30")
            specs = HOST_SERVICES.resolve_host_services(self.profile("service.sh"), owner)
            unrelated = subprocess.Popen(["sleep", "30"], start_new_session=True)
            try:
                state_file = state_root / "host-services/test-service/service.yaml"
                state_file.parent.mkdir(parents=True)
                state_file.write_text(
                    yaml.safe_dump(
                        {
                            "schema_version": 1,
                            "service_id": "test-service",
                            "status": "running",
                            "pid": unrelated.pid,
                            "process_start_ticks": HOST_SERVICES._process_start_ticks(unrelated.pid),
                            "boot_id": "00000000-0000-0000-0000-000000000000",
                            "command_digest": specs[0].command_digest,
                            "state_file": str(state_file),
                            "log_path": str(state_file.with_name("service.log")),
                        },
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )
                stopped = HOST_SERVICES.stop_host_services(specs, state_root=state_root)
                self.assertEqual(stopped[0]["status"], "stopped")
                self.assertIsNone(unrelated.poll())
            finally:
                os.killpg(unrelated.pid, signal.SIGKILL)
                unrelated.wait()

    def test_profile_contract_rejects_duplicate_and_escaped_declarations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-host-service-contract-") as temp_dir:
            root = Path(temp_dir)
            owner = root / "owner"
            owner.mkdir()
            self.create_script(owner, "service.sh", "sleep 1")
            duplicate = self.profile("service.sh")
            duplicate["host_services"].append(duplicate["host_services"][0].copy())
            with self.assertRaisesRegex(HOST_SERVICES.HostServiceError, "duplicate host service"):
                HOST_SERVICES.resolve_host_services(duplicate, owner)
            with self.assertRaisesRegex(HOST_SERVICES.HostServiceError, "owner-relative"):
                HOST_SERVICES.resolve_host_services(self.profile("/bin/sleep"), owner)


if __name__ == "__main__":
    unittest.main()
