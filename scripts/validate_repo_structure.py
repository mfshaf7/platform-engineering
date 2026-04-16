#!/usr/bin/env python3
import argparse
from pathlib import Path


SHARED_SCRIPT_FILES = {
    "README.md",
    "bootstrap_operator_access.sh",
    "bootstrap_vault.sh",
    "dispatch_github_workflow_from_k3s_secret.sh",
    "migrate_k8s_secret_to_vault.py",
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
    "openproject-backup-restore.md",
    "platform-naming-audit.md",
    "restart-validation.md",
    "rollback.md",
    "vault-auto-unseal.md",
    "vault-backup-restore.md",
    "vault-recovery.md",
    "vault-secret-rotation.md",
}

ALLOWED_RUNBOOK_SUBDIRS = {"change-records"}

REQUIRED_PRODUCT_FILES = {
    "AGENTS.md",
    "README.md",
    "dependencies.md",
    "runtime-contract.md",
    "visibility-and-operations.md",
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
    products_dir = repo_root / "products"

    check_exact_files(errors, scripts_dir, SHARED_SCRIPT_FILES)
    check_runbooks_dir(errors, runbooks_dir)

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
