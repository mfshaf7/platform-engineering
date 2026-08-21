#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import yaml


MODULE_PATH = Path(__file__).with_name("dev_integration.py")
SPEC = importlib.util.spec_from_file_location("dev_integration", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
DEV_INTEGRATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DEV_INTEGRATION)
REPO_ROOT = Path(__file__).resolve().parents[1]


class DevIntegrationRunnerTests(unittest.TestCase):
    def manifest(self, execution_id: str, action: str) -> dict:
        return {
            "schema_version": 1,
            "profile_id": "test-profile",
            "session_id": "test-profile-operator-20260809T000000Z",
            "execution_id": execution_id,
            "action": action,
        }

    def test_action_manifests_and_results_do_not_overwrite_each_other(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-") as temp_dir:
            root = Path(temp_dir)
            current = root / "state/current-session.yaml"
            sessions = root / "sessions"

            first_manifest = self.manifest("execution-up", "up")
            first_archive, first_result, first_snapshot = (
                DEV_INTEGRATION.prepare_session_files(
                    manifest=first_manifest,
                    current_manifest=current,
                    sessions_root=sessions,
                )
            )
            DEV_INTEGRATION.write_execution_result(
                manifest_snapshot=first_snapshot,
                manifest_path=first_archive,
                result_path=first_result,
                returncode=0,
            )
            second_manifest = self.manifest("execution-smoke", "smoke")
            second_archive, second_result, second_snapshot = (
                DEV_INTEGRATION.prepare_session_files(
                    manifest=second_manifest,
                    current_manifest=current,
                    sessions_root=sessions,
                )
            )
            DEV_INTEGRATION.write_execution_result(
                manifest_snapshot=second_snapshot,
                manifest_path=second_archive,
                result_path=second_result,
                returncode=2,
            )

            self.assertNotEqual(first_archive, second_archive)
            self.assertTrue(first_archive.is_file())
            self.assertTrue(first_result.is_file())
            self.assertTrue(second_archive.is_file())
            self.assertTrue(second_result.is_file())
            self.assertEqual(
                DEV_INTEGRATION.load_yaml(first_result)["result"],
                "succeeded",
            )
            self.assertEqual(
                DEV_INTEGRATION.load_yaml(second_result)["result"],
                "failed",
            )
            self.assertEqual(
                DEV_INTEGRATION.load_yaml(second_result)["returncode"],
                2,
            )
            self.assertEqual(
                DEV_INTEGRATION.load_yaml(second_result)["source_manifest"],
                second_manifest,
            )
            self.assertEqual(
                DEV_INTEGRATION.load_yaml(current)["execution_id"],
                "execution-smoke",
            )

            with self.assertRaises(FileExistsError):
                DEV_INTEGRATION.write_execution_result(
                    manifest_snapshot=first_snapshot,
                    manifest_path=first_archive,
                    result_path=first_result,
                    returncode=0,
                )

    def test_execution_evidence_is_created_only_after_action(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-evidence-") as temp_dir:
            root = Path(temp_dir)
            manifest = self.manifest("execution-up", "up")
            archive, result, snapshot = DEV_INTEGRATION.prepare_session_files(
                manifest=manifest,
                current_manifest=root / "state/current-session.yaml",
                sessions_root=root / "sessions",
            )
            self.assertFalse(archive.exists())
            self.assertFalse(result.exists())

            DEV_INTEGRATION.write_execution_result(
                manifest_snapshot=snapshot,
                manifest_path=archive,
                result_path=result,
                returncode=0,
            )

            self.assertEqual(archive.read_bytes(), snapshot)
            self.assertEqual(
                DEV_INTEGRATION.load_yaml(result)["source_manifest"],
                manifest,
            )
            self.assertEqual(archive.stat().st_mode & 0o777, 0o400)
            self.assertEqual(result.stat().st_mode & 0o777, 0o400)

    def test_status_action_does_not_create_session_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-status-runner-") as temp_dir:
            root = Path(temp_dir)
            action_files = DEV_INTEGRATION.prepare_action_session_files(
                action="status",
                manifest=self.manifest("execution-status", "status"),
                current_manifest=root / "state/current-session.yaml",
                sessions_root=root / "sessions",
            )
            self.assertIsNone(action_files)
            self.assertEqual(list(root.iterdir()), [])

    def test_temporal_status_script_does_not_create_profile_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="temporal-status-") as temp_dir:
            root = Path(temp_dir)
            state_root = root / "state"
            command_path = (
                REPO_ROOT
                / "dev-integration/profiles/temporal/scripts/status.sh"
            )
            executable_root = root / "bin"
            executable_root.mkdir()
            (executable_root / "python3").symlink_to(sys.executable)
            result = subprocess.run(
                ["/bin/bash", str(command_path)],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": f"{executable_root}:/usr/bin:/bin",
                    "DEVINT_OPERATOR": "status-test",
                    "DEVINT_PROFILE_ID": "temporal",
                    "DEVINT_PROFILE_LIFECYCLE": "build-admitted",
                    "DEVINT_STATE_ROOT": str(state_root),
                },
            )
            self.assertIn("runtime state: cluster-client-unavailable", result.stdout)
            self.assertFalse(state_root.exists())

    def test_governed_ai_status_script_does_not_create_profile_state(self) -> None:
        with tempfile.TemporaryDirectory(prefix="governed-ai-status-") as temp_dir:
            root = Path(temp_dir)
            state_root = root / "state"
            command_path = (
                REPO_ROOT
                / "dev-integration/profiles/governed-ai-gateway/scripts/status.sh"
            )
            result = subprocess.run(
                ["/bin/bash", str(command_path)],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "PATH": "/usr/bin:/bin",
                    "DEVINT_OPERATOR": "status-test",
                    "DEVINT_PROFILE_ID": "governed-ai-gateway",
                    "DEVINT_PROFILE_LIFECYCLE": "build-admitted",
                    "DEVINT_STATE_ROOT": str(state_root),
                },
            )
            self.assertIn("launchable: false", result.stdout)
            self.assertIn("access plane activation allowed: true", result.stdout)
            self.assertIn("model profile: intake-classifier-v1", result.stdout)
            self.assertIn("model environment: dev-integration", result.stdout)
            self.assertIn("model binding: local-ollama-qwen3-8b", result.stdout)
            self.assertIn("model binding status: active", result.stdout)
            self.assertIn(
                "model fallback mode: fail-closed-no-implicit-fallback", result.stdout
            )
            self.assertIn("model activation eligible: true", result.stdout)
            self.assertRegex(
                result.stdout,
                r"model selection ref: model-binding-selection:[0-9a-f]{64}",
            )
            self.assertIn("upstream provider: ollama", result.stdout)
            self.assertIn("provider route: ollama-local-host", result.stdout)
            self.assertIn("upstream model: qwen3:8b", result.stdout)
            self.assertFalse(state_root.exists())

    def test_governed_ai_runtime_requires_both_activation_gates(self) -> None:
        common_source = (
            REPO_ROOT
            / "dev-integration/profiles/governed-ai-gateway/scripts/common.sh"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "GOVERNED_AI_ACCESS_PLANE_ACTIVATION_ALLOWED",
            common_source,
        )
        self.assertIn(
            "if not ACCESS_PLANE_ACTIVATION_ALLOWED:",
            common_source,
        )
        self.assertIn(
            'denial_reasons.append("access-plane-not-active")',
            common_source,
        )
        self.assertIn(
            'denial_reasons.append("binding-not-active")',
            common_source,
        )
        self.assertIn(
            'denial_reasons.append("provider-route-not-active")',
            common_source,
        )
        self.assertIn("def selected_binding_evidence()", common_source)
        self.assertIn(
            'if [[ "${UPSTREAM_PROVIDER}" != "ollama" ]]',
            common_source,
        )
        self.assertIn("require_active_model_binding", common_source)
        self.assertIn(
            'denial_reasons.append("model-selection-not-activation-eligible")',
            common_source,
        )

    def test_governed_ai_runtime_manifest_is_valid_multi_document_yaml(self) -> None:
        with tempfile.TemporaryDirectory(prefix="governed-ai-render-") as temp_dir:
            state_root = Path(temp_dir) / "state"
            common_path = (
                REPO_ROOT
                / "dev-integration/profiles/governed-ai-gateway/scripts/common.sh"
            )
            subprocess.run(
                [
                    "/bin/bash",
                    "-c",
                    f'source "{common_path}"; render_runtime_manifest',
                ],
                check=True,
                capture_output=True,
                text=True,
                env={
                    **os.environ,
                    "DEVINT_OPERATOR": "render-test",
                    "DEVINT_PROFILE_LIFECYCLE": "active",
                    "DEVINT_STATE_ROOT": str(state_root),
                    "DEVINT_GAI_PROVIDER_HOST_IP": "192.0.2.10",
                },
            )
            manifest = state_root / "rendered/governed-ai-gateway-runtime.yaml"
            documents = list(yaml.safe_load_all(manifest.read_text(encoding="utf-8")))
            kinds = [document.get("kind") for document in documents if isinstance(document, dict)]

            self.assertIn("PersistentVolumeClaim", kinds)
            self.assertGreaterEqual(kinds.count("ConfigMap"), 2)
            self.assertIn("NetworkPolicy", kinds)
            gateway_config = next(
                document
                for document in documents
                if isinstance(document, dict)
                and document.get("kind") == "ConfigMap"
                and (document.get("metadata") or {}).get("name")
                == "governed-ai-gateway-app"
            )
            compile(
                gateway_config["data"]["gateway_app.py"],
                "rendered-gateway-app.py",
                "exec",
            )
            gateway = next(
                document
                for document in documents
                if isinstance(document, dict)
                and document.get("kind") == "Deployment"
                and (document.get("metadata") or {}).get("name") == "governed-ai-gateway"
            )
            env = {
                item["name"]: item["value"]
                for item in gateway["spec"]["template"]["spec"]["containers"][0]["env"]
            }
            self.assertRegex(
                env["GOVERNED_AI_PROVIDER_BASE_URL"],
                r"^http://\d{1,3}(?:\.\d{1,3}){3}:11434$",
            )
            self.assertEqual(env["GOVERNED_AI_PROFILE_ID"], "intake-classifier-v1")
            self.assertEqual(env["GOVERNED_AI_MODEL_ENVIRONMENT"], "dev-integration")
            self.assertEqual(env["GOVERNED_AI_BINDING_ID"], "local-ollama-qwen3-8b")
            self.assertEqual(env["GOVERNED_AI_BINDING_STATUS"], "active")
            self.assertEqual(env["GOVERNED_AI_PROVIDER_ROUTE_STATUS"], "active")
            self.assertEqual(
                env["GOVERNED_AI_FALLBACK_MODE"],
                "fail-closed-no-implicit-fallback",
            )
            self.assertEqual(env["GOVERNED_AI_MODEL_ACTIVATION_ELIGIBLE"], "true")
            self.assertRegex(
                env["GOVERNED_AI_BINDING_SELECTION_DIGEST"], r"^sha256:[0-9a-f]{64}$"
            )
            self.assertRegex(
                env["GOVERNED_AI_BINDING_SELECTION_REF"],
                r"^model-binding-selection:[0-9a-f]{64}$",
            )
            selection_receipt = json.loads(
                (state_root / "model-binding-selection.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                selection_receipt["selection_digest"],
                env["GOVERNED_AI_BINDING_SELECTION_DIGEST"],
            )
            self.assertEqual(
                selection_receipt["selection_ref"],
                env["GOVERNED_AI_BINDING_SELECTION_REF"],
            )
            consumer = next(
                document
                for document in documents
                if isinstance(document, dict)
                and document.get("kind") == "Deployment"
                and (document.get("metadata") or {}).get("name")
                == "governed-ai-consumer-probe"
            )
            self.assertEqual(
                [
                    container["name"]
                    for container in consumer["spec"]["template"]["spec"]["containers"]
                ],
                ["probe"],
            )

    def test_owner_files_must_remain_inside_selected_checkout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-owner-file-") as temp_dir:
            root = Path(temp_dir)
            owner_root = root / "owner"
            owner_root.mkdir()
            command = owner_root / "scripts/action.sh"
            command.parent.mkdir()
            command.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

            self.assertEqual(
                DEV_INTEGRATION.resolve_owner_file(
                    owner_root,
                    "scripts/action.sh",
                    description="Profile action",
                ),
                command,
            )
            with self.assertRaisesRegex(SystemExit, "must be owner-relative"):
                DEV_INTEGRATION.resolve_owner_file(
                    owner_root,
                    str(command),
                    description="Profile action",
                )

            outside = root / "outside.sh"
            outside.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (owner_root / "scripts/escaped.sh").symlink_to(outside)
            with self.assertRaisesRegex(SystemExit, "escapes the selected owner checkout"):
                DEV_INTEGRATION.resolve_owner_file(
                    owner_root,
                    "scripts/escaped.sh",
                    description="Profile action",
                )

            with self.assertRaisesRegex(SystemExit, "is unavailable"):
                DEV_INTEGRATION.resolve_owner_file(
                    owner_root,
                    "scripts/missing.sh",
                    description="Profile action",
                )

    def test_dirty_working_tree_digest_binds_changed_and_untracked_bytes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-source-state-") as temp_dir:
            workspace_root = Path(temp_dir)
            repo_root = workspace_root / "owner-repo"
            repo_root.mkdir()
            subprocess.run(["git", "init", "-q", str(repo_root)], check=True)
            subprocess.run(
                ["git", "-C", str(repo_root), "config", "user.email", "test@example.com"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(repo_root), "config", "user.name", "Test Operator"],
                check=True,
            )
            source = repo_root / "source.txt"
            source.write_text("baseline\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo_root), "add", "source.txt"], check=True)
            subprocess.run(
                ["git", "-C", str(repo_root), "commit", "-qm", "baseline"],
                check=True,
            )

            clean = DEV_INTEGRATION.git_state(
                repo_root,
                workspace_root=workspace_root,
            )
            self.assertFalse(clean["dirty"])
            self.assertIsNone(clean["working_tree_sha256"])

            source.write_text("first change\n", encoding="utf-8")
            first = DEV_INTEGRATION.git_state(repo_root, workspace_root=workspace_root)
            source.write_text("second change\n", encoding="utf-8")
            second = DEV_INTEGRATION.git_state(repo_root, workspace_root=workspace_root)
            self.assertTrue(first["dirty"])
            self.assertRegex(first["working_tree_sha256"], r"^[0-9a-f]{64}$")
            self.assertNotEqual(
                first["working_tree_sha256"],
                second["working_tree_sha256"],
            )

            untracked = repo_root / "local-input.txt"
            untracked.write_text("first input\n", encoding="utf-8")
            with_untracked = DEV_INTEGRATION.git_state(
                repo_root,
                workspace_root=workspace_root,
            )
            untracked.write_text("second input\n", encoding="utf-8")
            changed_untracked = DEV_INTEGRATION.git_state(
                repo_root,
                workspace_root=workspace_root,
            )
            self.assertNotEqual(
                with_untracked["working_tree_sha256"],
                changed_untracked["working_tree_sha256"],
            )

    def test_registry_contracts_must_remain_inside_selected_checkout(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-registry-file-") as temp_dir:
            root = Path(temp_dir)
            governance_root = root / "workspace-governance"
            contracts_root = governance_root / "contracts"
            contracts_root.mkdir(parents=True)
            policy_path = contracts_root / "developer-integration-policy.yaml"
            registry_path = contracts_root / "developer-integration-profiles.yaml"
            policy_path.write_text("profile_lifecycle: {}\n", encoding="utf-8")
            registry_path.write_text("profiles: {}\n", encoding="utf-8")

            policy, registry = DEV_INTEGRATION.load_registry(
                root,
                {"workspace-governance": governance_root},
            )
            self.assertEqual(policy, {"profile_lifecycle": {}})
            self.assertEqual(registry, {"profiles": {}})

            outside = root / "outside.yaml"
            outside.write_text("external: true\n", encoding="utf-8")
            policy_path.unlink()
            policy_path.symlink_to(outside)
            with self.assertRaisesRegex(
                SystemExit,
                "Dev-integration lifecycle policy escapes the selected owner checkout",
            ):
                DEV_INTEGRATION.load_registry(
                    root,
                    {"workspace-governance": governance_root},
                )

    def test_dispatch_terminates_background_process_group(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-process-") as temp_dir:
            root = Path(temp_dir)
            pid_file = root / "background.pid"
            command = root / "action.sh"
            command.write_text(
                '#!/usr/bin/env bash\nsleep 30 &\nprintf "%s\\n" "$!" >"$PID_FILE"\n',
                encoding="utf-8",
            )
            command.chmod(0o700)

            returncode = DEV_INTEGRATION.dispatch_command(
                command,
                cwd=root,
                env={**os.environ, "PID_FILE": str(pid_file)},
            )

            self.assertEqual(returncode, 0)
            background_pid = int(pid_file.read_text(encoding="utf-8"))
            deadline = time.monotonic() + 2
            while Path(f"/proc/{background_pid}").exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            if Path(f"/proc/{background_pid}/stat").is_file():
                state = Path(f"/proc/{background_pid}/stat").read_text().split()[2]
                self.assertEqual(state, "Z")

    def test_dispatch_handles_termination_and_restores_signal_handler(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-signal-") as temp_dir:
            root = Path(temp_dir)
            command = root / "action.sh"
            command.write_text(
                '#!/usr/bin/env bash\nkill -TERM "$PPID"\nsleep 30\n',
                encoding="utf-8",
            )
            command.chmod(0o700)
            previous_handler = signal.getsignal(signal.SIGTERM)

            returncode = DEV_INTEGRATION.dispatch_command(
                command,
                cwd=root,
                env=dict(os.environ),
            )

            self.assertEqual(returncode, 128 + signal.SIGTERM)
            self.assertEqual(signal.getsignal(signal.SIGTERM), previous_handler)

    def test_dispatch_skips_launch_when_termination_is_already_pending(self) -> None:
        def install_handler(signum: int, handler: object) -> object:
            if signum == signal.SIGTERM and callable(handler):
                handler(signal.SIGTERM, None)
            return signal.SIG_DFL

        with (
            patch.object(DEV_INTEGRATION.signal, "signal", side_effect=install_handler),
            patch.object(DEV_INTEGRATION.subprocess, "Popen") as popen,
        ):
            returncode = DEV_INTEGRATION.dispatch_command(
                Path("/not-launched.sh"),
                cwd=Path("/not-used"),
                env={},
            )

        self.assertEqual(returncode, 128 + signal.SIGTERM)
        popen.assert_not_called()

    def test_dispatch_keeps_signal_handling_through_result_publication(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-publish-") as temp_dir:
            root = Path(temp_dir)
            command = root / "action.sh"
            command.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
            command.chmod(0o700)
            published: list[int] = []
            previous_handler = signal.getsignal(signal.SIGTERM)

            def publish_result(returncode: int) -> None:
                self.assertNotEqual(signal.getsignal(signal.SIGTERM), previous_handler)
                published.append(returncode)
                os.kill(os.getpid(), signal.SIGTERM)

            returncode = DEV_INTEGRATION.dispatch_command(
                command,
                cwd=root,
                env=dict(os.environ),
                publish_result=publish_result,
            )

            self.assertEqual(published, [0])
            self.assertEqual(returncode, 128 + signal.SIGTERM)
            self.assertEqual(signal.getsignal(signal.SIGTERM), previous_handler)

    def test_repo_override_owns_profile_loading_and_dispatch_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-override-") as temp_dir:
            workspace_root = Path(temp_dir) / "workspace"
            default_owner = workspace_root / "owner-repo"
            selected_owner = Path(temp_dir) / "selected-owner"
            selected_platform = Path(temp_dir) / "selected-platform"
            selected_governance = Path(temp_dir) / "selected-governance"
            profile_relpath = Path("dev-integration/profiles/test/profile.yaml")
            default_profile = default_owner / profile_relpath
            selected_profile = selected_owner / profile_relpath
            default_profile.parent.mkdir(parents=True)
            selected_profile.parent.mkdir(parents=True)
            selected_platform.mkdir()
            selected_governance.mkdir()
            default_profile.write_text("summary: wrong checkout\n", encoding="utf-8")
            selected_profile.write_text(
                "\n".join(
                    [
                        "summary: selected checkout",
                        "runtime:",
                        "  namespace_pattern: devint-{profile}-{operator}",
                        "source_repos:",
                        "  - repo: owner-repo",
                        "stage_handoff:",
                        "  required_checks: []",
                        "commands:",
                        "  up: scripts/up.sh",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            entry = {
                "lifecycle": "active",
                "owner_repo": "owner-repo",
                "profile_path": profile_relpath.as_posix(),
                "runtime_owner": "platform-engineering",
                "security_owner": "security-architecture",
            }
            policy = {"profile_lifecycle": {"self_serve_statuses": ["active"]}}
            registry = {"profiles": {"test-profile": entry}}
            selected_state = {
                "branch": "test",
                "dirty": False,
                "head_sha": "a" * 40,
            }
            selected_platform_state = {
                "branch": "runner",
                "dirty": False,
                "head_sha": "b" * 40,
            }
            selected_governance_state = {
                "branch": "authority",
                "dirty": False,
                "head_sha": "c" * 40,
            }

            with (
                patch.object(
                    DEV_INTEGRATION,
                    "load_registry",
                    return_value=(policy, registry),
                ) as load_registry,
                patch.object(
                    DEV_INTEGRATION,
                    "git_state",
                    side_effect=lambda repo_root, **_: (
                        selected_state
                        if repo_root == selected_owner.resolve()
                        else (
                            selected_platform_state
                            if repo_root == selected_platform.resolve()
                            else selected_governance_state
                        )
                    ),
                ) as git_state,
            ):
                resolved = DEV_INTEGRATION.resolve_profile(
                    action="up",
                    workspace_root=workspace_root,
                    profile_id="test-profile",
                    repo_overrides={
                        "owner-repo": selected_owner,
                        "platform-engineering": selected_platform,
                        "workspace-governance": selected_governance,
                    },
                )

            _, profile, owner_root, profile_path, repo_paths, repo_states = resolved
            load_registry.assert_called_once_with(
                workspace_root,
                {
                    "owner-repo": selected_owner,
                    "platform-engineering": selected_platform,
                    "workspace-governance": selected_governance,
                },
            )
            git_state.assert_any_call(
                selected_owner.resolve(),
                workspace_root=workspace_root,
            )
            git_state.assert_any_call(
                selected_platform.resolve(),
                workspace_root=workspace_root,
            )
            git_state.assert_any_call(
                selected_governance.resolve(),
                workspace_root=workspace_root,
            )
            self.assertEqual(profile["summary"], "selected checkout")
            self.assertEqual(owner_root, selected_owner.resolve())
            self.assertEqual(profile_path, selected_profile.resolve())
            self.assertEqual(repo_paths["owner-repo"], selected_owner.resolve())
            self.assertEqual(repo_states["owner-repo"], selected_state)
            self.assertEqual(
                repo_paths["platform-engineering"],
                selected_platform.resolve(),
            )
            self.assertEqual(
                repo_states["platform-engineering"],
                selected_platform_state,
            )
            self.assertEqual(
                repo_paths["workspace-governance"],
                selected_governance.resolve(),
            )
            self.assertEqual(
                repo_states["workspace-governance"],
                selected_governance_state,
            )

    def test_profile_rejects_a_dirty_selected_platform_runner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-dirty-runner-") as temp_dir:
            root = Path(temp_dir)
            owner_root = root / "owner-repo"
            platform_root = root / "platform-engineering"
            governance_root = root / "workspace-governance"
            for repo_root in (owner_root, platform_root, governance_root):
                repo_root.mkdir()
            profile_path = owner_root / "profile.yaml"
            profile_path.write_text(
                "source_repos:\n  - repo: owner-repo\ncommands:\n  up: action.sh\n",
                encoding="utf-8",
            )
            entry = {
                "lifecycle": "active",
                "owner_repo": "owner-repo",
                "profile_path": "profile.yaml",
            }
            policy = {"profile_lifecycle": {"self_serve_statuses": ["active"]}}

            def selected_state(repo_root: Path, **_: object) -> dict:
                return {
                    "branch": "test",
                    "dirty": repo_root == platform_root.resolve(),
                    "head_sha": "a" * 40,
                }

            with (
                patch.object(
                    DEV_INTEGRATION,
                    "load_registry",
                    return_value=(policy, {"profiles": {"test-profile": entry}}),
                ),
                patch.object(DEV_INTEGRATION, "git_state", side_effect=selected_state),
                self.assertRaisesRegex(SystemExit, "runner checkout must be clean"),
            ):
                DEV_INTEGRATION.resolve_profile(
                    action="up",
                    workspace_root=root,
                    profile_id="test-profile",
                    repo_overrides={
                        "owner-repo": owner_root,
                        "platform-engineering": platform_root,
                        "workspace-governance": governance_root,
                    },
                )

    def test_platform_override_reexecutes_the_selected_runner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-reexec-") as temp_dir:
            selected_root = Path(temp_dir) / "platform-engineering"
            selected_runner = selected_root / "scripts/dev_integration.py"
            selected_runner.parent.mkdir(parents=True)
            selected_runner.write_text("# selected runner\n", encoding="utf-8")

            with (
                patch.object(DEV_INTEGRATION.os, "execv") as execv,
                patch.object(
                    DEV_INTEGRATION.sys,
                    "argv",
                    ["dev_integration.py", "up", "--profile", "test-profile"],
                ),
                self.assertRaisesRegex(RuntimeError, "failed to execute"),
            ):
                DEV_INTEGRATION.reexec_from_selected_platform_checkout(
                    {"platform-engineering": selected_root},
                    workspace_root=Path("/original/workspace"),
                )

            execv.assert_called_once_with(
                DEV_INTEGRATION.sys.executable,
                [
                    DEV_INTEGRATION.sys.executable,
                    str(selected_runner.resolve()),
                    "up",
                    "--profile",
                    "test-profile",
                    "--workspace-root",
                    "/original/workspace",
                ],
            )

    def test_platform_override_rejects_runner_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="devint-runner-reexec-") as temp_dir:
            root = Path(temp_dir)
            selected_root = root / "platform-engineering"
            selected_runner = selected_root / "scripts/dev_integration.py"
            selected_runner.parent.mkdir(parents=True)
            outside_runner = root / "outside-runner.py"
            outside_runner.write_text("# external runner\n", encoding="utf-8")
            selected_runner.symlink_to(outside_runner)

            with self.assertRaisesRegex(
                SystemExit,
                "Selected Platform runner escapes the selected owner checkout",
            ):
                DEV_INTEGRATION.reexec_from_selected_platform_checkout(
                    {"platform-engineering": selected_root},
                    workspace_root=Path("/original/workspace"),
                )


if __name__ == "__main__":
    unittest.main()
