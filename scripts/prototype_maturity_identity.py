#!/usr/bin/env python3
"""Commission and project the bounded Prototype Maturity runtime identity."""

from __future__ import annotations

from pathlib import Path

import prototype_workflow_identity as workflow


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "security/prototype-maturity-identity.yaml"

Contract = workflow.Contract
RuntimeInputs = workflow.RuntimeInputs
deployment_patch = workflow.deployment_patch
deployment_revoke_patch = workflow.deployment_revoke_patch
deployment_suspend_patch = workflow.deployment_suspend_patch
load_contract = workflow.load_contract
validate_definition = workflow.validate_definition


def main(argv: list[str] | None = None) -> int:
    return workflow.main(
        argv,
        default_contract=DEFAULT_CONTRACT,
        json_errors=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
