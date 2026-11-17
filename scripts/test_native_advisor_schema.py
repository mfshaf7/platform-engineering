from pathlib import Path
import copy
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "dev-integration/profiles/governed-ai-gateway/runtime"))
from strict_output_schema import validate_supported_schema, validate_output, OutputSchemaError


class NativeAdvisorSchemaTests(unittest.TestCase):
    def test_actual_provider_contracts_require_native_structure(self):
        canonical = json.loads((ROOT / "security/schemas/advisor-draft-reply.schema.json").read_text())
        body = {k: v for k, v in canonical.items() if k not in {"$schema", "$id", "title"}}
        for name in ["agent-console-response.schema.json", "delivery-work-design-advice.schema.json"]:
            schema = json.loads((ROOT / "security/schemas" / name).read_text())
            validate_supported_schema(schema)
            self.assertIn("draft_reply", schema["required"])
            self.assertEqual(schema["properties"]["draft_reply"], body)

    def test_native_reply_rejects_the_observed_missing_intent_and_patch_array(self):
        schema = json.loads((ROOT / "security/schemas/advisor-draft-reply.schema.json").read_text())
        answer = {"intent": "answer", "message": "Explain without changing the draft", "edits": []}
        validate_output(answer, schema)
        bad = copy.deepcopy(answer); del bad["intent"]
        with self.assertRaises(OutputSchemaError): validate_output(bad, schema)
        bad = {"intent": "draft", "message": "Wrong patch type", "edits": [{"field": "board", "value_type": "board", "text_value": None, "tree_patch": None, "board_patch": [{"op": "add"}]}]}
        with self.assertRaises(OutputSchemaError): validate_output(bad, schema)

    def test_text_cannot_hide_a_draft_from_either_actual_provider_contract(self):
        native = {"intent": "answer", "message": "An explanation without edits", "edits": []}
        for name in ["agent-console-response.schema.json", "delivery-work-design-advice.schema.json"]:
            schema = json.loads((ROOT / "security/schemas" / name).read_text())
            output = {"text": json.dumps({"intent": "draft", "message": "Legacy nested envelope", "edits": []})}
            if name.startswith("delivery-"):
                output.update(confidence="medium", required_operator_action="review", affected_node_id=None, patch_proposal=None)
            with self.assertRaises(OutputSchemaError): validate_output(output, schema)
            output["draft_reply"] = native
            validate_output(output, schema)
            for malformed in [None, {"message": "Missing intent", "edits": []}, "Plain advice instead of structure"]:
                output["draft_reply"] = malformed
                with self.assertRaises(OutputSchemaError): validate_output(output, schema)


if __name__ == "__main__": unittest.main()
