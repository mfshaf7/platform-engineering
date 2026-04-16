#!/usr/bin/env python3
import argparse
from pathlib import Path

import yaml


MANIFEST_FILE = "repo-structure-manifest.yaml"


def check_exact_files(errors: list[str], directory: Path, expected_files: set[str]) -> None:
    actual_files = {path.name for path in directory.iterdir() if path.is_file()}
    missing = sorted(expected_files - actual_files)
    unexpected = sorted(actual_files - expected_files)
    if missing:
        errors.append(f"{directory}: missing expected files: {', '.join(missing)}")
    if unexpected:
        errors.append(f"{directory}: unexpected files in shared path: {', '.join(unexpected)}")


def load_manifest(repo_root: Path) -> dict:
    manifest_path = repo_root / MANIFEST_FILE
    return yaml.safe_load(manifest_path.read_text())


def check_runbooks_dir(errors: list[str], directory: Path, config: dict) -> None:
    check_exact_files(errors, directory, set(config["exact_files"]))
    actual_dirs = {path.name for path in directory.iterdir() if path.is_dir()}
    unexpected_dirs = sorted(actual_dirs - set(config.get("allowed_subdirectories", [])))
    if unexpected_dirs:
        errors.append(
            f"{directory}: unexpected subdirectories in shared runbooks path: {', '.join(unexpected_dirs)}"
        )


def check_product_directory(errors: list[str], product_dir: Path, config: dict) -> None:
    actual_files = {path.name for path in product_dir.iterdir() if path.is_file()}
    missing = sorted(set(config["required_files"]) - actual_files)
    if missing:
        errors.append(f"{product_dir}: missing required product files: {', '.join(missing)}")

    for subdir_name, subdir_config in config.get("optional_subdirectories", {}).items():
        subdir = product_dir / subdir_name
        if not subdir.exists():
            continue
        actual_subdir_files = {path.name for path in subdir.iterdir() if path.is_file()}
        missing_subdir_files = sorted(set(subdir_config["required_files"]) - actual_subdir_files)
        if missing_subdir_files:
            errors.append(
                f"{subdir}: missing required files: {', '.join(missing_subdir_files)}"
            )


def check_components_dir(errors: list[str], components_dir: Path, config: dict) -> None:
    if not components_dir.exists():
        errors.append(f"{components_dir}: missing shared components docs directory")
        return

    for required_file in config["required_root_files"]:
        if not (components_dir / required_file).exists():
            errors.append(f"{components_dir}: missing {required_file}")

    actual_dirs = {path.name for path in components_dir.iterdir() if path.is_dir()}
    required_component_dirs = set(config["required_directories"])
    missing = sorted(required_component_dirs - actual_dirs)
    if missing:
        errors.append(f"{components_dir}: missing required component directories: {', '.join(missing)}")

    template_dir = components_dir / config["template_directory"]
    if not template_dir.exists():
        errors.append(f"{template_dir}: missing shared component template directory")
    else:
        actual_template_files = {path.name for path in template_dir.iterdir() if path.is_file()}
        missing_template_files = sorted(set(config["template_required_files"]) - actual_template_files)
        if missing_template_files:
            errors.append(
                f"{template_dir}: missing required component template files: {', '.join(missing_template_files)}"
            )

    for component_name in sorted(required_component_dirs & actual_dirs):
        component_dir = components_dir / component_name
        actual_files = {path.name for path in component_dir.iterdir() if path.is_file()}
        missing_files = sorted(
            set(config["required_directories"][component_name]["required_files"]) - actual_files
        )
        if missing_files:
            errors.append(f"{component_dir}: missing required component files: {', '.join(missing_files)}")


def check_required_files_map(errors: list[str], repo_root: Path, required_files_map: dict) -> None:
    for rel_dir, required_files in required_files_map.items():
        target_dir = repo_root / rel_dir
        if not target_dir.exists():
            errors.append(f"{target_dir}: missing required directory")
            continue
        actual_files = {path.name for path in target_dir.iterdir() if path.is_file()}
        missing = sorted(set(required_files) - actual_files)
        if missing:
            errors.append(f"{target_dir}: missing required files: {', '.join(missing)}")


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
    manifest = load_manifest(repo_root)
    errors: list[str] = []

    scripts_dir = repo_root / "scripts"
    runbooks_dir = repo_root / "docs" / "runbooks"
    components_dir = repo_root / manifest["components"]["root"]
    products_dir = repo_root / manifest["products"]["root"]

    check_exact_files(errors, scripts_dir, set(manifest["shared_paths"]["scripts"]["exact_files"]))
    check_runbooks_dir(errors, runbooks_dir, manifest["shared_paths"]["docs/runbooks"])
    check_components_dir(errors, components_dir, manifest["components"])
    check_required_files_map(errors, repo_root, manifest["governance"]["required_files"])

    for product_dir in sorted(path for path in products_dir.iterdir() if path.is_dir()):
        check_product_directory(errors, product_dir, manifest["products"])

    if errors:
        raise SystemExit("\n".join(errors))

    print(
        "platform-engineering structure valid: "
        f"shared_scripts={len(manifest['shared_paths']['scripts']['exact_files'])} "
        f"shared_runbooks={len(manifest['shared_paths']['docs/runbooks']['exact_files'])} "
        f"products={len([path for path in products_dir.iterdir() if path.is_dir()])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
