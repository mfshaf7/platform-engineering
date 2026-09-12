"""Negative checks for the inactive Prototype Closure identity boundary."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import unittest

import yaml

from prototype_closure_identity import validate_definition


ROOT = Path(__file__).resolve().parents[1]
DEFINITION = yaml.safe_load((ROOT / "security/prototype-closure-identity.yaml").read_text())
SCHEMA = json.loads((ROOT / "security/schemas/prototype-closure-identity.schema.json").read_text())


class PrototypeClosureIdentityTests(unittest.TestCase):
    def test_definition_is_inactive(self) -> None:
        self.assertEqual([], validate_definition(DEFINITION, SCHEMA))
        self.assertIsNone(DEFINITION["selection"]["app_id"])
        self.assertFalse(DEFINITION["consumer"]["workflow_enabled"])

    def test_cannot_borrow_maturity_identity(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["identity"]["id"] = "prototype-maturity-github-app-v1"
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_cannot_broaden_repository_or_write_paths(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["identity"]["maximum_repository_count"] = 2
        changed["source_boundary"]["allowed_write_paths"].append("prototypes/**")
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_cannot_claim_activation_or_commissioned_credential(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["selection"]["runtime_enabled"] = True
        changed["secret_custody"]["key_commissioned"] = True
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_cannot_drop_provider_or_denial_controls(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["source_boundary"]["provider_enforcement_required"].remove(
            "prototype-closure-app-has-no-bypass"
        )
        changed["source_boundary"]["denied_actions"].remove("prototype-maturity-write")
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_cannot_skip_security_or_cleanup_evidence(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["security_authority"]["normal_availability_gate"] = None
        changed["activation"]["required_evidence"].remove(
            "exact-active-resource-revocation-or-absence-proof"
        )
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_cannot_drop_receipt_binding(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["audit"]["receipt_fields"].remove("security_receipt_ref")
        self.assertTrue(validate_definition(changed, SCHEMA))

    def test_cannot_rewrite_durable_source(self) -> None:
        changed = deepcopy(DEFINITION)
        changed["rollback"]["delete_durable_owner_source"] = True
        self.assertTrue(validate_definition(changed, SCHEMA))


if __name__ == "__main__":
    unittest.main()
