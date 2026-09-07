#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


import dev_integration_auto_resume as AUTO_RESUME


class DevIntegrationAutoResumeTest(unittest.TestCase):
    def profile(self, policy: str = "operator-login", state_model: str = "persistent") -> dict:
        return {
            "runtime": {
                "resume_policy": policy,
                "state_model": state_model,
            }
        }

    def build_spec(self, root: Path, profile: dict | None = None):
        platform_root = root / "platform-engineering"
        runner = platform_root / "scripts/dev_integration.py"
        runner.parent.mkdir(parents=True)
        runner.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
        workspace_root = root / "workspace"
        return AUTO_RESUME.build_auto_resume_spec(
            config_home=root / "config",
            operator="Test Operator",
            platform_runner=runner,
            profile=profile or self.profile(),
            profile_id="accepted-idea-delivery",
            python_executable="/usr/bin/python3",
            repo_paths={
                "operator-orchestration-service": workspace_root / "operator-orchestration-service",
                "platform-engineering": platform_root,
            },
            workspace_root=workspace_root,
        )

    def test_manual_is_the_default_policy(self) -> None:
        self.assertEqual(AUTO_RESUME.resolve_resume_policy({"runtime": {}}), "manual")

    def test_operator_login_requires_persistent_state(self) -> None:
        with self.assertRaisesRegex(
            AUTO_RESUME.AutoResumeError,
            "requires state_model persistent",
        ):
            AUTO_RESUME.resolve_resume_policy(
                self.profile(state_model="disposable")
            )

    def test_unit_replays_the_exact_profile_and_source_paths_without_secrets(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-auto-resume-") as temp_dir:
            spec = self.build_spec(Path(temp_dir))

        self.assertEqual(
            spec.unit_name,
            "workspace-devint-accepted-idea-delivery-test-operator.service",
        )
        self.assertIn("Environment=DEVINT_AUTO_RESUME=1", spec.unit_content)
        self.assertIn("WorkingDirectory=/", spec.unit_content)
        self.assertNotIn('WorkingDirectory="', spec.unit_content)
        self.assertIn('"up" "--profile" "accepted-idea-delivery"', spec.unit_content)
        self.assertIn('"--operator" "Test Operator"', spec.unit_content)
        self.assertIn(
            '"--repo-path" "operator-orchestration-service=',
            spec.unit_content,
        )
        self.assertNotIn("SECRET", spec.unit_content)

    def test_enable_and_disable_manage_one_user_unit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-auto-resume-") as temp_dir:
            spec = self.build_spec(Path(temp_dir))
            calls: list[tuple[str, ...]] = []

            def systemctl(arguments, *, check=True):
                calls.append(tuple(arguments))
                if arguments[0] == "is-enabled":
                    return subprocess.CompletedProcess(arguments, 0, stdout="enabled\n")
                return subprocess.CompletedProcess(arguments, 0, stdout="")

            with patch.object(AUTO_RESUME, "_run_systemctl", side_effect=systemctl):
                enabled = AUTO_RESUME.enable_auto_resume(spec)
                self.assertTrue(enabled["enabled"])
                self.assertTrue(spec.unit_path.is_file())
                self.assertEqual(spec.unit_path.stat().st_mode & 0o777, 0o600)
                disabled = AUTO_RESUME.disable_auto_resume(spec)

            self.assertFalse(disabled["enabled"])
            self.assertFalse(spec.unit_path.exists())
            self.assertIn(("enable", spec.unit_name), calls)
            self.assertIn(("disable", "--now", spec.unit_name), calls)


if __name__ == "__main__":
    unittest.main()
