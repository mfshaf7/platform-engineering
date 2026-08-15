#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError


SCRIPT_DIR = Path(__file__).resolve().parent
PRODUCT_DIR = SCRIPT_DIR.parent
CONTRACT_PATH = PRODUCT_DIR / "openproject-platform-admin-surface.json"
PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH = PRODUCT_DIR / "proposal-workflow-state.schema.json"
MAKEFILE_PATH = PRODUCT_DIR.parents[1] / "Makefile"


def load_contract(path: Path | None = None) -> dict[str, object]:
    path = path or CONTRACT_PATH
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


CONTRACT = load_contract()
ALLOWED_SHELL_SURFACE_CLASSES = {
    "broker-projection-adapter",
    "product-runtime",
    "platform-admin",
    "internal-helper",
}
ALLOWED_PYTHON_SURFACE_CLASSES = {
    "broker-projection-adapter-internal",
    "platform-admin-adapter",
    "platform-admin-internal",
    "platform-admin-validator",
}
ALLOWED_RUNNER_STATUSES = {
    "active-platform-admin-internal",
    "residual-retirement-candidate",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_make_targets(makefile_text: str) -> set[str]:
    return set(re.findall(r"^\.PHONY: ([A-Za-z0-9_.-]+)$", makefile_text, re.MULTILINE))


def find_inventory_files(scripts_dir: Path) -> dict[str, set[str]]:
    files = {path.name for path in scripts_dir.iterdir() if path.is_file()}
    return {
        "shell": {name for name in files if name.endswith(".sh")},
        "python": {name for name in files if name.endswith(".py")},
        "runners": {name for name in files if name.endswith("_runner.rb")},
        "support": {name for name in files if name.endswith("_support.rb")},
        "all": files,
    }


def validate_unique_names(errors: list[str], entries: list[dict[str, object]], key: str, label: str) -> None:
    seen: set[str] = set()
    for entry in entries:
        value = str(entry[key])
        if value in seen:
            errors.append(f"{CONTRACT_PATH}: duplicate {label} entry {value}")
        seen.add(value)


def validate_doc_markers(errors: list[str], repo_root: Path, contract: dict[str, object]) -> None:
    for entry in contract["doc_surfaces"]:
        path = PRODUCT_DIR / str(entry["path"])
        if not path.exists():
            errors.append(f"{path}: contract-referenced documentation surface is missing")
            continue
        text = read_text(path)
        missing = [marker for marker in entry["required_markers"] if marker not in text]
        if missing:
            errors.append(
                f"{path}: missing required platform-admin contract markers: {', '.join(missing)}"
            )


def validate_proposal_workflow_state(errors: list[str]) -> None:
    if not PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH.exists():
        errors.append(f"{PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH}: Proposal workflow-state schema is missing")
        return

    try:
        schema = json.loads(read_text(PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH))
    except json.JSONDecodeError as exc:
        errors.append(f"{PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH}: invalid JSON: {exc}")
        return

    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        errors.append(f"{PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH}: invalid JSON Schema: {exc.message}")
        return

    expected_required = {
        "schema_version",
        "route",
        "handoff",
        "last_accepted_command",
        "receipt_refs",
        "updated_at",
    }
    if set(schema.get("required", [])) != expected_required:
        errors.append(
            f"{PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH}: required fields must be "
            f"{', '.join(sorted(expected_required))}"
        )
    if schema.get("properties", {}).get("schema_version", {}).get("const") != 1:
        errors.append(f"{PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH}: schema_version must be fixed at 1")
    if schema.get("additionalProperties") is not False:
        errors.append(f"{PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH}: unknown top-level fields must fail closed")

    validator = Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
    valid_initial_state = {
        "schema_version": 1,
        "route": None,
        "handoff": {
            "state": "not-requested",
            "packet_ref": None,
            "target_receipt_ref": None,
            "target_record_ref": None,
        },
        "last_accepted_command": None,
        "receipt_refs": [],
        "updated_at": "2026-08-16T00:00:00Z",
    }
    if not validator.is_valid(valid_initial_state):
        errors.append(f"{PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH}: canonical initial state must validate")
    if validator.is_valid({**valid_initial_state, "schema_version": 2}):
        errors.append(f"{PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH}: unversioned state must fail validation")
    if validator.is_valid({**valid_initial_state, "unexpected": True}):
        errors.append(f"{PROPOSAL_WORKFLOW_STATE_SCHEMA_PATH}: unknown state fields must fail validation")

    runner_path = SCRIPT_DIR / "openproject_configure_idea_backlog_runner.rb"
    runner_text = read_text(runner_path)
    field_spec_match = re.search(
        r'\{\s*name: "Proposal Workflow State",(?P<body>.*?)\n\s*\}',
        runner_text,
        re.DOTALL,
    )
    if field_spec_match is None:
        errors.append(f'{runner_path}: missing "Proposal Workflow State" custom-field spec')
        return

    field_spec = field_spec_match.group("body")
    required_runner_markers = [
        'field_format: "text"',
        "searchable: false",
        "is_filter: false",
        "max_length: 32_768",
    ]
    missing = [marker for marker in required_runner_markers if marker not in field_spec]
    if missing:
        errors.append(
            f"{runner_path}: missing Proposal workflow-state provisioning markers: "
            f"{', '.join(missing)}"
        )
    if "proposal-workflow-state.schema.json" not in runner_text:
        errors.append(f"{runner_path}: provisioning does not load the Proposal workflow-state schema")


def validate_shell_surfaces(
    errors: list[str], repo_root: Path, contract: dict[str, object], make_targets: set[str]
) -> None:
    shell_surfaces = contract["shell_surfaces"]
    validate_unique_names(errors, shell_surfaces, "script", "shell surface")
    seen_operation_ids: set[str] = set()
    for entry in shell_surfaces:
        script = str(entry["script"])
        surface_class = str(entry["surface_class"])
        if surface_class not in ALLOWED_SHELL_SURFACE_CLASSES:
            errors.append(f"{CONTRACT_PATH}: {script} has unsupported shell surface class {surface_class}")
        path = SCRIPT_DIR / script
        if not path.exists():
            errors.append(f"{path}: shell surface declared in contract is missing")
        operation_id = entry.get("operation_id")
        if operation_id:
            operation_id = str(operation_id)
            if operation_id in seen_operation_ids:
                errors.append(
                    f"{CONTRACT_PATH}: duplicate operation id {operation_id} declared for shell surfaces"
                )
            seen_operation_ids.add(operation_id)
        for make_target in entry.get("make_targets", []):
            if make_target not in make_targets:
                errors.append(
                    f"{MAKEFILE_PATH}: missing make target {make_target} declared for {script}"
                )
        for runbook in entry.get("runbooks", []):
            runbook_path = PRODUCT_DIR / str(runbook)
            if not runbook_path.exists():
                errors.append(f"{runbook_path}: runbook declared for {script} is missing")
        for runner_file in entry.get("internal_runner_files", []):
            runner_path = SCRIPT_DIR / str(runner_file)
            if not runner_path.exists():
                errors.append(
                    f"{runner_path}: shell surface {script} references a missing internal runner"
                )
        for support_file in entry.get("support_files", []):
            support_path = SCRIPT_DIR / str(support_file)
            if not support_path.exists():
                errors.append(
                    f"{support_path}: shell surface {script} references a missing support file"
                )


def validate_python_tools(errors: list[str], contract: dict[str, object]) -> None:
    tools = contract["python_tools"]
    validate_unique_names(errors, tools, "script", "python tool")
    for entry in tools:
        script = str(entry["script"])
        surface_class = str(entry["surface_class"])
        if surface_class not in ALLOWED_PYTHON_SURFACE_CLASSES:
            errors.append(f"{CONTRACT_PATH}: {script} has unsupported python surface class {surface_class}")
        path = SCRIPT_DIR / script
        if not path.exists():
            errors.append(f"{path}: python tool declared in contract is missing")
        for invoker in entry.get("invoked_by", []):
            invoker_path = SCRIPT_DIR / str(invoker)
            if not invoker_path.exists():
                errors.append(f"{invoker_path}: declared invoker for {script} is missing")


def validate_rails_runners(errors: list[str], contract: dict[str, object]) -> None:
    runners = contract["rails_runners"]
    validate_unique_names(errors, runners, "script", "Rails runner")
    all_script_text = {
        path.name: read_text(path)
        for path in SCRIPT_DIR.iterdir()
        if path.is_file() and path.suffix in {".sh", ".py", ".rb"}
    }
    shell_surface_by_script = {
        str(entry["script"]): entry for entry in contract["shell_surfaces"]
    }
    for entry in runners:
        script = str(entry["script"])
        status = str(entry["status"])
        if status not in ALLOWED_RUNNER_STATUSES:
            errors.append(f"{CONTRACT_PATH}: {script} has unsupported runner status {status}")
        path = SCRIPT_DIR / script
        if not path.exists():
            errors.append(f"{path}: runner declared in contract is missing")
            continue
        invoked_by = [str(value) for value in entry.get("invoked_by", [])]
        if status == "active-platform-admin-internal":
            if not invoked_by:
                errors.append(f"{CONTRACT_PATH}: active runner {script} must declare at least one invoker")
            for invoker in invoked_by:
                invoker_path = SCRIPT_DIR / invoker
                if not invoker_path.exists():
                    errors.append(f"{invoker_path}: declared invoker for active runner {script} is missing")
                    continue
                invoker_text = all_script_text.get(invoker, "")
                shell_surface = shell_surface_by_script.get(invoker) or {}
                operation_id = shell_surface.get("operation_id")
                adapter_invocation = (
                    "openproject_platform_admin_adapter.py" in invoker_text
                    and operation_id
                    and operation_id in invoker_text
                )
                if script not in invoker_text and not adapter_invocation:
                    errors.append(
                        f"{invoker_path}: active runner {script} is declared but not referenced by the invoker"
                    )
        if status == "residual-retirement-candidate":
            if invoked_by:
                errors.append(
                    f"{CONTRACT_PATH}: residual runner {script} must not declare active invokers"
                )
            references = [
                name
                for name, text in all_script_text.items()
                if name != script and script in text
            ]
            if references:
                errors.append(
                    f"{SCRIPT_DIR}: residual runner {script} is still referenced by {', '.join(sorted(references))}"
                )


def validate_support_modules(errors: list[str], contract: dict[str, object]) -> None:
    modules = contract["support_modules"]
    validate_unique_names(errors, modules, "script", "support module")
    for entry in modules:
        script = str(entry["script"])
        path = SCRIPT_DIR / script
        if not path.exists():
            errors.append(f"{path}: support module declared in contract is missing")
        for consumer in entry.get("used_by", []):
            consumer_path = SCRIPT_DIR / str(consumer)
            if not consumer_path.exists():
                errors.append(f"{consumer_path}: declared support-module consumer for {script} is missing")


def validate_inventory_coverage(errors: list[str], repo_root: Path, contract: dict[str, object]) -> None:
    inventory = find_inventory_files(SCRIPT_DIR)
    shell_known = {str(entry["script"]) for entry in contract["shell_surfaces"]}
    python_known = {str(entry["script"]) for entry in contract["python_tools"]}
    runner_known = {str(entry["script"]) for entry in contract["rails_runners"]}
    support_known = {str(entry["script"]) for entry in contract["support_modules"]}
    test_known = {str(name) for name in contract["test_files"]}
    ignored_known = {str(name) for name in contract["ignored_files"]}

    uncovered_shell = sorted(inventory["shell"] - shell_known)
    uncovered_python = sorted(inventory["python"] - python_known - test_known)
    uncovered_runners = sorted(inventory["runners"] - runner_known)
    uncovered_support = sorted(inventory["support"] - support_known)
    uncovered_all = sorted(
        inventory["all"]
        - shell_known
        - python_known
        - runner_known
        - support_known
        - test_known
        - ignored_known
    )

    if uncovered_shell:
        errors.append(
            f"{CONTRACT_PATH}: shell scripts missing from platform-admin contract: {', '.join(uncovered_shell)}"
        )
    if uncovered_python:
        errors.append(
            f"{CONTRACT_PATH}: python scripts missing from platform-admin contract: {', '.join(uncovered_python)}"
        )
    if uncovered_runners:
        errors.append(
            f"{CONTRACT_PATH}: Rails runners missing from platform-admin contract: {', '.join(uncovered_runners)}"
        )
    if uncovered_support:
        errors.append(
            f"{CONTRACT_PATH}: support modules missing from platform-admin contract: {', '.join(uncovered_support)}"
        )
    if uncovered_all:
        errors.append(
            f"{CONTRACT_PATH}: unclassified files remain in products/openproject/scripts: {', '.join(uncovered_all)}"
        )


def validate_contract(repo_root: Path) -> list[str]:
    contract = load_contract()
    make_targets = parse_make_targets(read_text(repo_root / "Makefile"))
    errors: list[str] = []
    validate_doc_markers(errors, repo_root, contract)
    validate_proposal_workflow_state(errors)
    validate_shell_surfaces(errors, repo_root, contract, make_targets)
    validate_python_tools(errors, contract)
    validate_rails_runners(errors, contract)
    validate_support_modules(errors, contract)
    validate_inventory_coverage(errors, repo_root, contract)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the OpenProject platform-admin surface contract against the current product script inventory."
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[3],
        type=Path,
        help="platform-engineering repository root",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    errors = validate_contract(repo_root)
    if errors:
        raise SystemExit("\n".join(errors))

    print("OpenProject platform-admin surface contract valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
