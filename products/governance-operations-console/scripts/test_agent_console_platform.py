from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


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


if __name__ == "__main__":
    unittest.main()
