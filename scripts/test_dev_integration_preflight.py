#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import dev_integration_preflight as PREFLIGHT


class CompositionPreflightTests(unittest.TestCase):
    def fixture(self, root: Path):
        runtime_dir = root / "runtime"
        runtime_dir.mkdir(mode=0o700)
        owner = root / "owner"
        owner.mkdir()
        (owner / "package.json").write_text('{"name":"owner"}\n')
        (owner / "package-lock.json").write_text(
            '{"name":"owner","lockfileVersion":3,"packages":{}}\n'
        )
        unit_path = root / "config/systemd/user/profile.service"
        profile = PREFLIGHT.CompositionPreflightProfile(
            profile_id="root-profile",
            profile={
                "runtime": {
                    "state_model": "persistent",
                    "resume_policy": "operator-login",
                },
                "host_services": [{"id": "source-service"}],
            },
            owner_repo_root=owner,
            auto_resume_unit_path=unit_path,
        )
        environment = {
            "PATH": os.environ["PATH"],
            "XDG_RUNTIME_DIR": str(runtime_dir),
            "DEVINT_KUBECONFIG": str(root / "kubeconfig"),
        }
        return profile, environment

    def runner(self, *, npm_returncode=0, systemd_returncode=0, helm_output="[]"):
        calls = []

        def run(command, **kwargs):
            calls.append((command, kwargs))
            executable = Path(command[0]).name
            if executable == "npm":
                return subprocess.CompletedProcess(
                    command,
                    npm_returncode,
                    stdout="{}" if npm_returncode == 0 else '{"problems":["missing"]}',
                    stderr="",
                )
            if executable == "systemctl":
                return subprocess.CompletedProcess(
                    command,
                    systemd_returncode,
                    stdout="" if systemd_returncode == 0 else "manager unavailable",
                    stderr="",
                )
            if executable == "helm":
                return subprocess.CompletedProcess(command, 0, stdout=helm_output, stderr="")
            raise AssertionError(f"unexpected command: {command}")

        return calls, run

    def test_preflight_proves_every_prerequisite_without_writing(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-preflight-") as temp_dir:
            root = Path(temp_dir)
            profile, environment = self.fixture(root)
            before = sorted(path.relative_to(root) for path in root.rglob("*"))
            calls, runner = self.runner()

            result = PREFLIGHT.run_composition_preflight(
                [profile],
                environment=environment,
                command_runner=runner,
            )

            after = sorted(path.relative_to(root) for path in root.rglob("*"))
            self.assertEqual(before, after)
            self.assertEqual(result["source_dependency_profile_ids"], ["root-profile"])
            self.assertEqual(result["auto_resume_profile_ids"], ["root-profile"])
            self.assertEqual(result["pending_helm_operations"], 0)
            self.assertEqual(
                [Path(command[0]).name for command, _ in calls],
                ["npm", "systemctl", "helm"],
            )

    def test_unready_source_dependencies_fail_before_later_checks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-preflight-") as temp_dir:
            profile, environment = self.fixture(Path(temp_dir))
            calls, runner = self.runner(npm_returncode=1)
            with self.assertRaisesRegex(
                PREFLIGHT.CompositionPreflightError,
                "production source dependencies are not ready",
            ):
                PREFLIGHT.run_composition_preflight(
                    [profile],
                    environment=environment,
                    command_runner=runner,
                )
            self.assertEqual([Path(command[0]).name for command, _ in calls], ["npm"])

    def test_unsafe_runtime_directory_fails_before_commands(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-preflight-") as temp_dir:
            root = Path(temp_dir)
            profile, environment = self.fixture(root)
            Path(environment["XDG_RUNTIME_DIR"]).chmod(0o755)
            calls, runner = self.runner()
            with self.assertRaisesRegex(
                PREFLIGHT.CompositionPreflightError,
                "operator runtime directory must be a private directory",
            ):
                PREFLIGHT.run_composition_preflight(
                    [profile],
                    environment=environment,
                    command_runner=runner,
                )
            self.assertEqual(calls, [])

    def test_unreachable_user_systemd_fails_before_helm_check(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-preflight-") as temp_dir:
            profile, environment = self.fixture(Path(temp_dir))
            calls, runner = self.runner(systemd_returncode=1)
            with self.assertRaisesRegex(
                PREFLIGHT.CompositionPreflightError,
                "user systemd is not ready",
            ):
                PREFLIGHT.run_composition_preflight(
                    [profile],
                    environment=environment,
                    command_runner=runner,
                )
            self.assertEqual(
                [Path(command[0]).name for command, _ in calls],
                ["npm", "systemctl"],
            )

    def test_pending_helm_operation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-preflight-") as temp_dir:
            profile, environment = self.fixture(Path(temp_dir))
            _, runner = self.runner(
                helm_output=(
                    '[{"name":"temporal","namespace":"devint-temporal",'
                    '"status":"pending-upgrade"}]'
                )
            )
            with self.assertRaisesRegex(
                PREFLIGHT.CompositionPreflightError,
                "devint-temporal/temporal=pending-upgrade",
            ):
                PREFLIGHT.run_composition_preflight(
                    [profile],
                    environment=environment,
                    command_runner=runner,
                )


if __name__ == "__main__":
    unittest.main()
