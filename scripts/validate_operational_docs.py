#!/usr/bin/env python3
import argparse
import copy
import re
from pathlib import Path
import subprocess
import tempfile

import yaml


DATE_PATTERNS = {
    Path("docs/architecture/current-platform-topology.md"): re.compile(
        r"Last validated against the live local cluster on `\d{4}-\d{2}-\d{2}`\."
    ),
    Path("docs/runbooks/access-platform-uis.md"): re.compile(
        r"Last access verification update: `\d{4}-\d{2}-\d{2}`\."
    ),
}
DOC_TRUTH_MARKERS = {
    Path("docs/architecture/overview.md"): (
        "target architecture surface",
        "not an observed live-state snapshot",
    ),
    Path("docs/architecture/current-platform-topology.md"): (
        "observed live-state surface",
        "not the target steady-state architecture",
    ),
    Path("docs/runbooks/access-platform-uis.md"): (
        "observed operator-access surface",
        "not the target steady-state architecture",
    ),
    Path("products/openclaw/runtime-contract.md"): (
        "intended steady-state and governed lifecycle contract",
        "not a snapshot of what is live today",
    ),
}

WORKFLOW_REQUIRED_HEADINGS = {
    "## Purpose",
    "## Trigger",
    "## Inputs Or Parameters",
    "## Permissions And Approval Surface",
    "## Outputs And Side Effects",
    "## Operator Evidence",
}
LEGACY_MIGRATION_TARGETS = (
    "capture-cutover-evidence",
    "render-cutover-command-inventory",
    "render-cutover-record",
    "render-runtime-container-verification",
    "render-runtime-reachability",
    "render-windows-cutover-inventory",
    "capture-windows-task-evidence",
)
LEGACY_MIGRATION_LEGACY_TARGETS = tuple(f"legacy-{entry}" for entry in LEGACY_MIGRATION_TARGETS)
LEGACY_PLAYBOOKS = (
    "capture-cutover-evidence.yml",
    "capture-windows-task-evidence.yml",
    "render-cutover-command-inventory.yml",
    "render-cutover-record.yml",
    "render-runtime-container-verification.yml",
    "render-runtime-reachability-checklist.yml",
    "render-windows-cutover-inventory.yml",
)
LEGACY_TEMPLATES = (
    "cutover-command-inventory.md.j2",
    "cutover-evidence.md.j2",
    "cutover-record.md.j2",
    "runtime-container-verification.md.j2",
    "runtime-reachability-checklist.md.j2",
    "windows-cutover-inventory.md.j2",
    "windows-task-evidence.md.j2",
)
BUILTIN_NAMESPACES = {
    "default",
    "kube-node-lease",
    "kube-public",
    "kube-system",
}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_make_help_targets(makefile_text: str) -> list[str]:
    targets: list[str] = []
    for line in makefile_text.splitlines():
        marker = '@printf "  '
        if marker not in line:
            continue
        after = line.split(marker, 1)[1]
        target = after.split(" ", 1)[0].strip()
        if target and target not in {"\\n", "make"}:
            targets.append(target)
    return targets


def validate_wsl_host_bootstrap_contract(errors: list[str], repo_root: Path) -> None:
    defaults_path = repo_root / "ansible" / "roles" / "wsl_host_stack" / "defaults" / "main.yml"
    runbook_path = repo_root / "docs" / "runbooks" / "bootstrap-wsl-distro.md"
    legacy_path = "{{ openclaw_host_bridge_root }}/scripts/start-openclaw-host-stack-tmux.sh"
    required_supervisors = (
        "{{ openclaw_host_bridge_root }}/scripts/run-openclaw-host-bridge-supervisor.sh",
        "{{ openclaw_host_bridge_root }}/scripts/run-openclaw-host-recovery-supervisor.sh",
    )

    if not defaults_path.exists():
        errors.append(f"{defaults_path}: missing WSL host stack defaults")
        return
    defaults = yaml.safe_load(read_text(defaults_path)) or {}
    required_packages = defaults.get("openclaw_wsl_required_packages") or []
    required_paths = defaults.get("openclaw_host_bridge_required_paths") or []
    if "tmux" in required_packages:
        errors.append(
            f"{defaults_path}: supported WSL bootstrap must not install legacy tmux by default"
        )
    if legacy_path in required_paths:
        errors.append(
            f"{defaults_path}: supported WSL bootstrap must not require legacy tmux stack path {legacy_path}"
        )
    for required_path in required_supervisors:
        if required_path not in required_paths:
            errors.append(
                f"{defaults_path}: missing supported WSL bootstrap required path {required_path}"
            )

    if not runbook_path.exists():
        errors.append(f"{runbook_path}: missing WSL bootstrap runbook")
        return
    runbook_text = read_text(runbook_path)
    if legacy_path in runbook_text:
        errors.append(
            f"{runbook_path}: supported WSL bootstrap runbook must not list legacy tmux stack path {legacy_path}"
        )
    for required_path in required_supervisors:
        if required_path not in runbook_text:
            errors.append(
                f"{runbook_path}: missing supported WSL bootstrap path {required_path}"
            )
    product_runbook_link = "../../products/openclaw/runbooks/host-stack-rollout.md"
    if product_runbook_link not in runbook_text:
        errors.append(
            f"{runbook_path}: shared WSL bootstrap runbook must point to the OpenClaw host-stack rollout runbook at {product_runbook_link}"
        )


def validate_windows_portproxy_reconciliation(errors: list[str], repo_root: Path) -> None:
    template_path = (
        repo_root
        / "ansible"
        / "roles"
        / "wsl_host_stack"
        / "templates"
        / "openclaw-host-stack-windows-bootstrap.ps1.j2"
    )
    group_vars_path = repo_root / "ansible" / "group_vars" / "all" / "main.yml"
    if not template_path.exists():
        errors.append(f"{template_path}: missing Windows bootstrap template")
        return

    template = read_text(template_path)
    required_snippets = (
        "function Remove-PortProxyEntriesByListenPort",
        "[regex]::Matches($output, $rowPattern)",
        "$parsedListenPort = [int]$match.Groups['port'].Value",
        "Remove-PortProxyEntriesByListenPort -ListenPort $port",
        "Remove-PortProxyEntriesByListenPort -ListenPort $rule.ListenPort",
        "Remove-PortProxyEntriesByListenPort -ListenPort $TransitVaultProxyPort",
    )
    for snippet in required_snippets:
        if snippet not in template:
            errors.append(
                f"{template_path}: missing exact listen-port reconciliation contract: {snippet}"
            )

    forbidden_snippets = (
        "foreach ($part in $parts[1..",
        "Remove-ItemProperty",
        "SYSTEM\\CurrentControlSet\\Services\\PortProxy",
        "ListenAddressAliases",
    )
    for snippet in forbidden_snippets:
        if snippet in template:
            errors.append(
                f"{template_path}: unsafe or obsolete portproxy behavior remains: {snippet}"
            )

    if group_vars_path.exists() and "listen_address_aliases:" in read_text(group_vars_path):
        errors.append(
            f"{group_vars_path}: listen-address aliases are obsolete when reconciliation is owned by exact listen port"
        )


def validate_legacy_operator_separation(errors: list[str], repo_root: Path) -> None:
    makefile_path = repo_root / "Makefile"
    runbooks_dir = repo_root / "docs" / "runbooks"
    playbooks_dir = repo_root / "ansible" / "playbooks"
    legacy_playbooks_dir = playbooks_dir / "legacy"
    templates_dir = repo_root / "ansible" / "roles" / "wsl_host_stack" / "templates"
    legacy_templates_dir = templates_dir / "legacy"
    legacy_runbook_path = runbooks_dir / "legacy" / "migrate-to-platform-core.md"
    legacy_readme_path = runbooks_dir / "legacy" / "README.md"
    current_runbook_path = runbooks_dir / "migrate-to-platform-core.md"
    current_docs = (
        runbooks_dir / "bootstrap-wsl-distro.md",
        runbooks_dir / "deploy.md",
        runbooks_dir / "rollback.md",
    )

    if current_runbook_path.exists():
        errors.append(
            f"{current_runbook_path}: legacy migration runbook must not remain in the current runbooks root"
        )
    if not legacy_runbook_path.exists():
        errors.append(f"{legacy_runbook_path}: missing legacy migration runbook")
    if not legacy_readme_path.exists():
        errors.append(f"{legacy_readme_path}: missing legacy runbooks README")
    if not (legacy_playbooks_dir / "README.md").exists():
        errors.append(f"{legacy_playbooks_dir / 'README.md'}: missing legacy playbooks README")
    if not (legacy_templates_dir / "README.md").exists():
        errors.append(f"{legacy_templates_dir / 'README.md'}: missing legacy templates README")

    for path in current_docs:
        text = read_text(path)
        if "migrate-to-platform-core.md" in text:
            errors.append(f"{path}: current operator runbook must not route directly to legacy migration docs")

    for relative_name in LEGACY_PLAYBOOKS:
        current_path = playbooks_dir / relative_name
        legacy_path = legacy_playbooks_dir / relative_name
        if current_path.exists():
            errors.append(f"{current_path}: legacy migration playbook must not remain in the active playbooks root")
        if not legacy_path.exists():
            errors.append(f"{legacy_path}: missing legacy migration playbook")

    for relative_name in LEGACY_TEMPLATES:
        current_path = templates_dir / relative_name
        legacy_path = legacy_templates_dir / relative_name
        if current_path.exists():
            errors.append(f"{current_path}: legacy migration template must not remain in the active templates root")
        if not legacy_path.exists():
            errors.append(f"{legacy_path}: missing legacy migration template")

    if not makefile_path.exists():
        errors.append(f"{makefile_path}: missing Makefile")
        return

    makefile_text = read_text(makefile_path)
    for target in LEGACY_MIGRATION_TARGETS:
        if f".PHONY: {target}" in makefile_text:
            errors.append(
                f"{makefile_path}: legacy migration helper {target} must not stay in the current top-level target surface"
            )
    for target in LEGACY_MIGRATION_LEGACY_TARGETS:
        if f".PHONY: {target}" not in makefile_text:
            errors.append(
                f"{makefile_path}: missing explicit legacy-prefixed migration helper {target}"
            )


def validate_readme_operator_surface(errors: list[str], repo_root: Path) -> None:
    makefile_path = repo_root / "Makefile"
    readme_path = repo_root / "README.md"
    if not makefile_path.exists():
        errors.append(f"{makefile_path}: missing Makefile")
        return
    if not readme_path.exists():
        errors.append(f"{readme_path}: missing repo README")
        return

    help_targets = extract_make_help_targets(read_text(makefile_path))
    readme_text = read_text(readme_path)
    for target in help_targets:
        if target.startswith("legacy-"):
            continue
        if not re.search(rf"`make {re.escape(target)}(?:[^`]*)`", readme_text):
            errors.append(
                f"{readme_path}: missing documented operator entrypoint for make target {target}"
            )


def validate_component_index_coverage(errors: list[str], repo_root: Path) -> None:
    manifest_path = repo_root / "repo-structure-manifest.yaml"
    repo_readme_path = repo_root / "README.md"
    components_readme_path = repo_root / "docs" / "components" / "README.md"
    if not manifest_path.exists():
        errors.append(f"{manifest_path}: missing repo structure manifest")
        return
    if not repo_readme_path.exists():
        errors.append(f"{repo_readme_path}: missing repo README")
        return
    if not components_readme_path.exists():
        errors.append(f"{components_readme_path}: missing shared components README")
        return

    manifest = yaml.safe_load(read_text(manifest_path)) or {}
    required_components = sorted((manifest.get("components") or {}).get("required_directories", {}).keys())
    repo_readme_text = read_text(repo_readme_path)
    components_readme_text = read_text(components_readme_path)

    for component in required_components:
        repo_marker = f"docs/components/{component}/README.md"
        components_marker = f"{component}/README.md"
        if repo_marker not in repo_readme_text:
            errors.append(
                f"{repo_readme_path}: shared component map must include {repo_marker}"
            )
        if components_marker not in components_readme_text:
            errors.append(
                f"{components_readme_path}: shared components index must include {components_marker}"
            )


def validate_product_runbook_separation(errors: list[str], repo_root: Path) -> None:
    shared_runbook = repo_root / "docs" / "runbooks" / "host-stack-rollout.md"
    product_runbook = repo_root / "products" / "openclaw" / "runbooks" / "host-stack-rollout.md"
    product_runbook_readme = repo_root / "products" / "openclaw" / "runbooks" / "README.md"
    host_integration_path = repo_root / "products" / "openclaw" / "host-integration.md"

    if shared_runbook.exists():
        errors.append(
            f"{shared_runbook}: product-specific host-stack rollout must not remain in shared runbooks"
        )
    if not product_runbook.exists():
        errors.append(f"{product_runbook}: missing OpenClaw host-stack rollout runbook")
    if product_runbook_readme.exists():
        readme_text = read_text(product_runbook_readme)
        if "host-stack-rollout.md" not in readme_text:
            errors.append(
                f"{product_runbook_readme}: must list host-stack-rollout.md as an OpenClaw runbook"
            )
    if host_integration_path.exists():
        host_integration_text = read_text(host_integration_path)
        if "runbooks/host-stack-rollout.md" not in host_integration_text:
            errors.append(
                f"{host_integration_path}: must point operators to runbooks/host-stack-rollout.md"
            )


def run_kubectl(*args: str) -> str:
    result = subprocess.run(
        ["k3s", "kubectl", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def extract_section(text: str, heading: str) -> str:
    marker = f"## {heading}\n"
    if marker not in text:
        return ""
    after = text.split(marker, 1)[1]
    return after.split("\n## ", 1)[0]


def extract_bulleted_code_items(section_text: str) -> set[str]:
    items: set[str] = set()
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        items.update(re.findall(r"`([^`]+)`", stripped))
    return items


def extract_namespace_rows(section_text: str) -> set[str]:
    namespaces: set[str] = set()
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("| `"):
            continue
        first_cell = stripped.split("|", 2)[1].strip()
        if first_cell.startswith("`") and first_cell.endswith("`"):
            namespaces.add(first_cell.strip("`"))
    return namespaces


def validate_live_cluster_topology(errors: list[str], repo_root: Path) -> None:
    topology_path = repo_root / "docs" / "architecture" / "current-platform-topology.md"
    if not topology_path.exists():
        errors.append(f"{topology_path}: missing current-platform-topology doc")
        return

    try:
        app_lines = run_kubectl("-n", "argocd", "get", "applications.argoproj.io", "-o", "name").splitlines()
        namespace_lines = run_kubectl("get", "ns", "-o", "name").splitlines()
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        errors.append(f"{topology_path}: failed to query live cluster inventory for topology validation: {exc}")
        return

    live_apps = {line.split("/", 1)[1] for line in app_lines if "/" in line}
    live_namespaces = {
        line.split("/", 1)[1]
        for line in namespace_lines
        if "/" in line
        and line.split("/", 1)[1] not in BUILTIN_NAMESPACES
        and not line.split("/", 1)[1].startswith("devint-")
    }

    text = read_text(topology_path)
    documented_apps = extract_bulleted_code_items(extract_section(text, "Current Live Argo Applications"))
    documented_namespaces = extract_namespace_rows(extract_section(text, "Namespace Inventory"))

    missing_apps = sorted(live_apps - documented_apps)
    stale_apps = sorted(documented_apps - live_apps)
    if missing_apps:
        errors.append(f"{topology_path}: missing live Argo applications from topology doc: {', '.join(missing_apps)}")
    if stale_apps:
        errors.append(f"{topology_path}: stale Argo applications still documented as live: {', '.join(stale_apps)}")

    missing_namespaces = sorted(live_namespaces - documented_namespaces)
    stale_namespaces = sorted(documented_namespaces - live_namespaces)
    if missing_namespaces:
        errors.append(
            f"{topology_path}: missing live namespaces from topology doc: {', '.join(missing_namespaces)}"
        )
    if stale_namespaces:
        errors.append(
            f"{topology_path}: stale namespaces still documented as live inventory: {', '.join(stale_namespaces)}"
        )


def validate_date_markers(errors: list[str], repo_root: Path) -> None:
    for relative_path, pattern in DATE_PATTERNS.items():
        path = repo_root / relative_path
        if not path.exists():
            errors.append(f"{path}: missing required operational doc")
            continue
        text = read_text(path)
        if not pattern.search(text):
            errors.append(f"{path}: missing required freshness marker")


def validate_doc_truth_markers(errors: list[str], repo_root: Path) -> None:
    for relative_path, required_markers in DOC_TRUTH_MARKERS.items():
        path = repo_root / relative_path
        if not path.exists():
            errors.append(f"{path}: missing required doc for truth-model validation")
            continue
        text = read_text(path)
        missing = [marker for marker in required_markers if marker not in text]
        if missing:
            errors.append(f"{path}: missing required truth-model markers: {', '.join(missing)}")


def validate_workflow_docs(errors: list[str], repo_root: Path) -> None:
    workflow_dir = repo_root / ".github" / "workflows"
    docs_dir = repo_root / "docs" / "workflows"

    if not workflow_dir.exists():
        errors.append(f"{workflow_dir}: missing workflow directory")
        return
    if not docs_dir.exists():
        errors.append(f"{docs_dir}: missing workflow docs directory")
        return

    for workflow_path in sorted(workflow_dir.glob("*.yaml")):
        doc_path = docs_dir / f"{workflow_path.stem}.md"
        if not doc_path.exists():
            errors.append(f"{doc_path}: missing workflow doc for {workflow_path.name}")
            continue

        text = read_text(doc_path)
        missing = sorted(heading for heading in WORKFLOW_REQUIRED_HEADINGS if heading not in text)
        if missing:
            errors.append(f"{doc_path}: missing workflow doc headings: {', '.join(missing)}")


def validate_openproject_platform_admin_surface(errors: list[str], repo_root: Path) -> None:
    validator = (
        repo_root
        / "products"
        / "openproject"
        / "scripts"
        / "validate_openproject_platform_admin_surface.py"
    )
    if not validator.exists():
        errors.append(f"{validator}: missing OpenProject platform-admin surface validator")
        return
    completed = subprocess.run(
        ["python3", str(validator), "--repo-root", str(repo_root)],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        errors.append(
            f"{validator}: OpenProject platform-admin surface contract invalid\n{detail}"
        )


def validate_openproject_catalog_control(errors: list[str], repo_root: Path) -> None:
    validator = (
        repo_root
        / "products"
        / "openproject"
        / "catalog-control"
        / "validate_catalog_control.py"
    )
    if not validator.exists():
        errors.append(f"{validator}: missing OpenProject Catalog control validator")
        return
    completed = subprocess.run(
        ["python3", str(validator)],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        errors.append(f"{validator}: OpenProject Catalog control contract invalid\n{detail}")


def validate_runtime_drill_profiles(errors: list[str], repo_root: Path) -> None:
    profiles_root = repo_root / "environments" / "shared" / "runtime-drills"
    required_profile = profiles_root / "temporal-component-commissioning-proof.yaml"
    if not required_profile.exists():
        errors.append(f"{required_profile}: missing Temporal commissioning drill profile")
    profile_paths = sorted(
        path
        for path in profiles_root.glob("*.yaml")
        if not path.name.endswith("-evidence-template.yaml")
    )
    if not profile_paths:
        errors.append(f"{profiles_root}: no runtime-drill profiles found")
        return
    validator = repo_root / "scripts" / "platform_drill.py"
    for profile_path in profile_paths:
        completed = subprocess.run(
            [
                "python3",
                str(validator),
                "plan",
                "--profile-path",
                str(profile_path),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            errors.append(f"{profile_path}: runtime-drill profile invalid\n{detail}")
    if required_profile.exists():
        temporal_profile = yaml.safe_load(required_profile.read_text(encoding="utf-8")) or {}
        generic_profile = copy.deepcopy(temporal_profile)
        generic_profile["id"] = "example-component-commissioning-proof"
        generic_profile["title"] = "Example component commissioning proof"
        generic_profile["sourceEnablement"]["implementationWorkItemRef"] = (
            "openproject://work_packages/999"
        )
        generic_profile["authorization"]["targetProfileId"] = (
            "example-component-dev-integration"
        )
        generic_profile["authorization"]["securityReviewRef"] = (
            "security://reviews/example-component-commissioning-proof"
        )
        for source_role in ("permitIssuer", "executor"):
            generic_profile["authorization"][source_role] = {
                "ownerRepo": "example-component-owner",
                "sourceReviewWorkItemRef": "openproject://work_packages/999",
                "mergedSourceRequiredBeforeSecurityAuthorization": True,
            }
        with tempfile.TemporaryDirectory(prefix="generic-commissioning-profile-") as temp_dir:
            generic_profile_path = Path(temp_dir) / "example-component-commissioning-proof.yaml"
            generic_profile_path.write_text(
                yaml.safe_dump(generic_profile, sort_keys=False),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    "python3",
                    str(validator),
                    "plan",
                    "--profile-path",
                    str(generic_profile_path),
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout).strip()
                errors.append(
                    "component-commissioning-proof generic source binding is invalid\n"
                    + detail
                )

            generic_profile["sourceEnablement"]["status"] = "source-reviewed"
            generic_profile["sourceEnablement"]["snapshotAllowed"] = True
            generic_profile_path.write_text(
                yaml.safe_dump(generic_profile, sort_keys=False),
                encoding="utf-8",
            )
            with tempfile.TemporaryDirectory(
                prefix="generic-commissioning-denial-"
            ) as output_root:
                completed = subprocess.run(
                    [
                        "python3",
                        str(validator),
                        "snapshot",
                        "--profile-path",
                        str(generic_profile_path),
                        "--run-id",
                        "generic-source-reviewed-validation",
                        "--operator",
                        "validator",
                        "--authorization-ref",
                        "artifact://controlled-proof/validation-only",
                        "--authorization-digest",
                        "sha256:" + "a" * 64,
                        "--output-root",
                        output_root,
                    ],
                    capture_output=True,
                    text=True,
                )
                detail = (completed.stderr or completed.stdout).strip()
                if (
                    completed.returncode == 0
                    or "permit artifact validation and atomic consumption are not source-reviewed"
                    not in detail
                ):
                    errors.append(
                        "generic commissioning snapshot must fail closed without a permit validator and consumer"
                    )
                if any(Path(output_root).iterdir()):
                    errors.append(
                        "denied generic commissioning snapshot created local state"
                    )

        with tempfile.TemporaryDirectory(prefix="temporal-proof-denial-") as output_root:
            completed = subprocess.run(
                [
                    "python3",
                    str(validator),
                    "snapshot",
                    "--profile-path",
                    str(required_profile),
                    "--run-id",
                    "source-reviewed-validation",
                    "--operator",
                    "validator",
                    "--authorization-ref",
                    "artifact://controlled-proof/validation-only",
                    "--authorization-digest",
                    "sha256:" + "a" * 64,
                    "--output-root",
                    output_root,
                ],
                capture_output=True,
                text=True,
            )
            detail = (completed.stderr or completed.stdout).strip()
            if (
                completed.returncode == 0
                or "controlled commissioning snapshot requires" not in detail
            ):
                errors.append(
                    f"{required_profile}: commissioning snapshot must require every reviewed permit artifact"
                )
            if any(Path(output_root).iterdir()):
                errors.append(
                    f"{required_profile}: denied commissioning snapshot created local state"
                )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate workflow docs coverage and operational doc freshness markers."
    )
    parser.add_argument(
        "--repo-root",
        default=Path(__file__).resolve().parents[1],
        type=Path,
        help="platform-engineering repository root",
    )
    parser.add_argument(
        "--check-live-cluster",
        action="store_true",
        help="Also compare current-platform-topology.md against the live local k3s app and namespace inventory.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    errors: list[str] = []

    validate_date_markers(errors, repo_root)
    validate_doc_truth_markers(errors, repo_root)
    validate_workflow_docs(errors, repo_root)
    validate_openproject_platform_admin_surface(errors, repo_root)
    validate_openproject_catalog_control(errors, repo_root)
    validate_runtime_drill_profiles(errors, repo_root)
    validate_wsl_host_bootstrap_contract(errors, repo_root)
    validate_windows_portproxy_reconciliation(errors, repo_root)
    validate_legacy_operator_separation(errors, repo_root)
    validate_readme_operator_surface(errors, repo_root)
    validate_component_index_coverage(errors, repo_root)
    validate_product_runbook_separation(errors, repo_root)
    if args.check_live_cluster:
        validate_live_cluster_topology(errors, repo_root)

    if errors:
        raise SystemExit("\n".join(errors))

    print("platform-engineering operational docs valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
