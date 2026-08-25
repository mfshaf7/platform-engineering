#!/usr/bin/env python3
from __future__ import annotations

import copy
import unittest

from validate_catalog_control import load_contract, validate_contract


class CatalogControlContractTest(unittest.TestCase):
    def test_repository_contract_is_valid(self) -> None:
        self.assertEqual([], validate_contract(load_contract()))

    def test_request_item_must_use_exact_mutation_route(self) -> None:
        contract = copy.deepcopy(load_contract())
        request_item = next(
            item for item in contract["items"] if item["console_capability"] == "request"
        )
        request_item["backend_route"] = "/v1/general-admin"
        errors = validate_contract(contract)
        self.assertTrue(any("request capability must use" in error for error in errors))

    def test_read_only_source_cannot_become_requestable(self) -> None:
        contract = copy.deepcopy(load_contract())
        static_item = next(item for item in contract["items"] if item["source"]["kind"] == "static")
        static_item["console_capability"] = "request"
        static_item["backend_route"] = f"/v1/delivery-catalog/{static_item['catalog_item_id']}/mutations"
        errors = validate_contract(contract)
        self.assertTrue(any("request capability uses read-only source" in error for error in errors))

    def test_catalog_vocabulary_cannot_silently_drop_an_item(self) -> None:
        contract = copy.deepcopy(load_contract())
        contract["items"].pop()
        errors = validate_contract(contract)
        self.assertTrue(any("Catalog vocabulary mismatch" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
