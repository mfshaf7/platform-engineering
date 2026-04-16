#!/usr/bin/env python3
import argparse
from pathlib import Path


SHARED_SCRIPT_FILES = {
    "README.md",
    "bootstrap_operator_access.sh",
    "bootstrap_vault.sh",
    "dispatch_github_workflow_from_k3s_secret.sh",
    "migrate_k8s_secret_to_vault.py",
    "validate_governance_docs.py",
    "validate_operational_docs.py",
    "validate_repo_structure.py",
}

SHARED_RUNBOOK_FILES = {
    "README.md",
    "access-grafana.md",
    "access-platform-uis.md",
    "bootstrap-k3s.md",
    "bootstrap-transit-vault-temporary-trust.md",
    "bootstrap-transit-vault.md",
    "bootstrap-vault.md",
    "bootstrap-windows-rooted-vault-auto-unseal.md",
    "bootstrap-wsl-distro.md",
    "bootstrap.md",
    "deploy.md",
    "host-runtime-drift-recovery.md",
    "host-stack-rollout.md",
    "incident-hotfix.md",
    "migrate-to-platform-core.md",
    "platform-naming-audit.md",
    "restart-validation.md",
    "rollback.md",
    "vault-auto-unseal.md",
    "vault-backup-restore.md",
    "vault-recovery.md",
    "vault-secret-rotation.md",
}

ALLOWED_RUNBOOK_SUBDIRS: set[str] = set()

REQUIRED_PRODUCT_FILES = {
    "AGENTS.md",
    "README.md",
    "dependencies.md",
    "runtime-contract.md",
    "visibility-and-operations.md",
}

REQUIRED_COMPONENT_DIRS = {
    "argo-cd",
    "vault",
    "observability",
    "external-secrets",
    "platform-postgresql",
}

REQUIRED_COMPONENT_FILES = {
    "README.md",
    "architecture.md",
    "access.md",
    "operations.md",
}

REQUIRED_GITHUB_FILES = {
    "CODEOWNERS",
    "pull_request_template.md",
}

REQUIRED_STANDARD_FILES = {
    "README.md",
    "enterprise-workflow-model.md",
    "review-and-approval-model.md",
}

REQUIRED_WORKFLOW_DOC_FILES = {
    "README.md",
    "TEMPLATE.md",
}


def check_exact_files(errors: list[str], directory: Path, expected_files: set[str]) -> None:
    actual_files = {path.name for path in directory.iterdir() if path.is_file()}
    missing = sorted(expected_files - actual_files)
    unexpected = sorted(actual_files - expected_files)
    if missing:
        errors.append(f"{directory}: missing expected files: {', '.join(missing)}")
    if unexpected:
        errors.append(f"{directory}: unexpected files in shared path: {', '.join(unexpected)}")


def check_runbooks_dir(errors: list[str], directory: Path) -> None:
    check_exact_files(errors, directory, SHARED_RUNBOOK_FILES)
    actual_dirs = {path.name for path in directory.iterdir() if path.is_dir()}
    unexpected_dirs = sorted(actual_dirs - ALLOWED_RUNBOOK_SUBDIRS)
    if unexpected_dirs:
        errors.append(
            f"{directory}: unexpected subdirectories in shared runbooks path: {', '.join(unexpected_dirs)}"
        )


def check_product_directory(errors: list[str], product_dir: Path) -> None:
    actual_files = {path.name for path in product_dir.iterdir() if path.is_file()}
    missing = sorted(REQUIRED_PRODUCT_FILES - actual_files)
    if missing:
        errors.append(f"{product_dir}: missing required product files: {', '.join(missing)}")

    scripts_dir = product_dir / "scripts"
    if scripts_dir.exists() and not (scripts_dir / "README.md").exists():
        errors.append(f"{scripts_dir}: missing README.md")

    runbooks_dir = product_dir / "runbooks"
    if runbooks_dir.exists() and not (runbooks_dir / "README.md").exists():
        errors.append(f"{runbooks_dir}: missing README.md")


def check_components_dir(errors: list[str], components_dir: Path) -> None:
    if not components_dir.exists():
        errors.append(f"{components_dir}: missing shared components docs directory")
        return

    if not (components_dir / "README.md").exists():
        errors.append(f"{components_dir}: missing README.md")

    actual_dirs = {path.name for path in components_dir.iterdir() if path.is_dir()}
    missing = sorted(REQUIRED_COMPONENT_DIRS - actual_dirs)
    if missing:
        errors.append(f"{components_dir}: missing required component directories: {', '.join(missing)}")

    template_dir = components_dir / "_template"
    if not template_dir.exists():
        errors.append(f"{template_dir}: missing shared component template directory")
    else:
        actual_template_files = {path.name for path in template_dir.iterdir() if path.is_file()}
        missing_template_files = sorted(REQUIRED_COMPONENT_FILES - actual_template_files)
        if missing_template_files:
            errors.append(
                f"{template_dir}: missing required component template files: {', '.join(missing_template_files)}"
            )

    for component_name in sorted(REQUIRED_COMPONENT_DIRS & actual_dirs):
        component_dir = components_dir / component_name
        actual_files = {path.name for path in component_dir.iterdir() if path.is_file()}
        missing_files = sorted(REQUIRED_COMPONENT_FILES - actual_files)
        if missing_files:
            errors.append(f"{component_dir}: missing required component files: {', '.join(missing_files)}")


def check_governance_dirs(errors: list[str], repo_root: Path) -> None:
    decisions_dir = repo_root / "docs" / "decisions"
    adr_dir = decisions_dir / "adr"
    records_dir = repo_root / "docs" / "records"
    change_records_dir = records_dir / "change-records"

    if not (decisions_dir / "README.md").exists():
        errors.append(f"{decisions_dir}: missing README.md")
    if not (adr_dir / "README.md").exists():
        errors.append(f"{adr_dir}: missing README.md")
    if not (adr_dir / "TEMPLATE.md").exists():
        errors.append(f"{adr_dir}: missing TEMPLATE.md")

    if not (records_dir / "README.md").exists():
        errors.append(f"{records_dir}: missing README.md")
    if not (change_records_dir / "README.md").exists():
        errors.append(f"{change_records_dir}: missing README.md")
    if not (change_records_dir / "TEMPLATE.md").exists():
        errors.append(f"{change_records_dir}: missing TEMPLATE.md")


def check_github_dir(errors: list[str], repo_root: Path) -> None:
    github_dir = repo_root / ".github"
    if not github_dir.exists():
        errors.append(f"{github_dir}: missing .github directory")
        return
    actual_files = {path.name for path in github_dir.iterdir() if path.is_file()}
    missing = sorted(REQUIRED_GITHUB_FILES - actual_files)
    if missing:
        errors.append(f"{github_dir}: missing required governance files: {', '.join(missing)}")


def check_standards_dir(errors: list[str], repo_root: Path) -> None:
    standards_dir = repo_root / "docs" / "standards"
    actual_files = {path.name for path in standards_dir.iterdir() if path.is_file()}
    missing = sorted(REQUIRED_STANDARD_FILES - actual_files)
    if missing:
        errors.append(f"{standards_dir}: missing required standards files: {', '.join(missing)}")


def check_workflows_dir(errors: list[str], repo_root: Path) -> None:
    workflows_dir = repo_root / "docs" / "workflows"
    if not workflows_dir.exists():
        errors.append(f"{workflows_dir}: missing workflows docs directory")
        return

    actual_files = {path.name for path in workflows_dir.iterdir() if path.is_file()}
    missing = sorted(REQUIRED_WORKFLOW_DOC_FILES - actual_files)
    if missing:
        errors.append(f"{workflows_dir}: missing required workflow doc files: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate that platform-engineering keeps shared paths product-neutral."
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="platform-engineering repository root",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    errors: list[str] = []

    scripts_dir = repo_root / "scripts"
    runbooks_dir = repo_root / "docs" / "runbooks"
    components_dir = repo_root / "docs" / "components"
    products_dir = repo_root / "products"

    check_exact_files(errors, scripts_dir, SHARED_SCRIPT_FILES)
    check_runbooks_dir(errors, runbooks_dir)
    check_components_dir(errors, components_dir)
    check_governance_dirs(errors, repo_root)
    check_github_dir(errors, repo_root)
    check_standards_dir(errors, repo_root)
    check_workflows_dir(errors, repo_root)

    for product_dir in sorted(path for path in products_dir.iterdir() if path.is_dir()):
        check_product_directory(errors, product_dir)

    if errors:
        raise SystemExit("\n".join(errors))

    print(
        "platform-engineering structure valid: "
        f"shared_scripts={len(SHARED_SCRIPT_FILES)} "
        f"shared_runbooks={len(SHARED_RUNBOOK_FILES)} "
        f"products={len([path for path in products_dir.iterdir() if path.is_dir()])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
