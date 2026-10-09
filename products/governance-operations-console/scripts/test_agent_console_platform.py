from __future__ import annotations

import importlib.util
from pathlib import Path
import signal
import unittest
from unittest.mock import Mock, call, patch


SCRIPT = Path(__file__).with_name("agent_console_platform.py")
SPEC = importlib.util.spec_from_file_location("agent_console_platform", SCRIPT)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class AgentConsolePlatformTests(unittest.TestCase):
    def test_policy_matches_the_resolved_governed_profile(self) -> None:
        policy = module.load_policy()
        resolved = module.validate_policy(policy)

        self.assertEqual(resolved["profile_id"], "agent-console-assistant-v1")
        self.assertEqual(
            resolved["allowed_callers"],
            ["operator-orchestration-service/agent-console"],
        )
        self.assertTrue(resolved["activation_eligible"])

    def test_partial_or_parallel_activation_fails_closed(self) -> None:
        policy = module.load_policy()
        policy["activation"]["composition_id"] = "agent-console-parallel"
        with self.assertRaisesRegex(
            module.AgentConsolePlatformError, "reuse refinement-catalog"
        ):
            module.validate_policy(policy)

        policy = module.load_policy()
        policy["model"]["caller_id"] = "operator-orchestration-service/refinement-assist"
        with self.assertRaisesRegex(
            module.AgentConsolePlatformError, "model binding is not exact"
        ):
            module.validate_policy(policy)

    def test_security_review_set_cannot_omit_an_owner(self) -> None:
        policy = module.load_policy()
        policy["security"]["exact_revision_repos"].remove("context-governance-gateway")
        with self.assertRaisesRegex(
            module.AgentConsolePlatformError, "review set is incomplete"
        ):
            module.validate_policy(policy)

    def test_port_forward_terminates_the_complete_process_group(self) -> None:
        process = Mock(pid=42)
        process.wait.return_value = 0
        with (
            patch.object(module.subprocess, "Popen", return_value=process) as popen,
            patch.object(
                module.os,
                "killpg",
                side_effect=[None, ProcessLookupError],
            ) as killpg,
        ):
            with module.port_forward("namespace", "service", 38180):
                pass

        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        self.assertEqual(
            killpg.call_args_list,
            [call(42, signal.SIGTERM), call(42, 0)],
        )
        process.wait.assert_called_once_with(timeout=5)


if __name__ == "__main__":
    unittest.main()
