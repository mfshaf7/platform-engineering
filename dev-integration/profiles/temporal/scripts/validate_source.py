#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
import tempfile

import yaml


DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def docs(path: Path) -> list[dict]:
    return [item for item in yaml.safe_load_all(path.read_text(encoding="utf-8")) if item]


def resource(items: list[dict], kind: str, name: str) -> dict:
    for item in items:
        if item.get("kind") == kind and item.get("metadata", {}).get("name") == name:
            return item
    raise KeyError(f"missing {kind}/{name}")


def validate_rendered_chart(path: Path, errors: list[str]) -> None:
    items = docs(path)
    for item in items:
        kind = item.get("kind")
        spec = item.get("spec") or {}
        if kind == "Ingress":
            errors.append(f"{path}: public ingress resource is forbidden")
        if kind == "Service" and spec.get("type", "ClusterIP") != "ClusterIP":
            errors.append(
                f"{path}: Service/{item.get('metadata', {}).get('name')} is not ClusterIP"
            )
        template = spec.get("template", {}).get("spec", {})
        containers = template.get("initContainers", []) + template.get("containers", [])
        for container in containers:
            image = container.get("image", "")
            if image and "@sha256:" not in image:
                errors.append(
                    f"{path}: {kind}/{item.get('metadata', {}).get('name')} "
                    f"container {container.get('name')} is not digest pinned"
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Temporal profile source.")
    parser.add_argument(
        "--profile-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument("--rendered-chart", type=Path)
    args = parser.parse_args()

    profile_root = args.profile_root.resolve()
    owner_repo_root = profile_root.parents[2]
    runtime_root = profile_root / "runtime"
    scripts_root = profile_root / "scripts"
    errors: list[str] = []

    profile = load_yaml(profile_root / "profile.yaml")
    lock = load_yaml(runtime_root / "artifact-lock.yaml")
    boundary = load_yaml(runtime_root / "boundary-contract.yaml")

    require(profile.get("profile_id") == "temporal", "profile_id must be temporal", errors)
    require(
        profile.get("runtime", {}).get("state_model") == "persistent",
        "runtime.state_model must be persistent",
        errors,
    )
    require(
        profile.get("testing", {}).get("smoke", {}).get("mutation_mode") == "read-only",
        "persistent profile smoke must be read-only",
        errors,
    )
    for command in (
        "up",
        "status",
        "access",
        "smoke",
        "down",
        "reset",
        "backup",
        "restore",
        "promote_check",
    ):
        command_path_value = profile.get("commands", {}).get(command)
        require(bool(command_path_value), f"missing command {command}", errors)
        if command_path_value:
            command_path = owner_repo_root / command_path_value
            require(command_path.is_file(), f"command {command} path is missing", errors)
            require(
                command_path.suffix in {".sh", ".py"} or command_path.stat().st_mode & 0o111,
                f"command {command} path is not dispatchable",
                errors,
            )

    chart = lock.get("chart", {})
    require(chart.get("name") == "temporal", "chart.name must be temporal", errors)
    require(bool(chart.get("version")), "chart.version must be pinned", errors)
    require(
        bool(SHA256_RE.fullmatch(str(chart.get("sha256", "")))),
        "chart.sha256 must be a SHA-256 checksum",
        errors,
    )
    images = lock.get("images", {})
    for image_name in (
        "temporal_server",
        "temporal_admin_tools",
        "temporal_ui",
        "postgresql",
    ):
        entry = images.get(image_name, {})
        require(bool(entry.get("repository")), f"{image_name} repository missing", errors)
        require(bool(entry.get("tag")), f"{image_name} tag missing", errors)
        require(
            bool(DIGEST_RE.fullmatch(str(entry.get("digest", "")))),
            f"{image_name} digest must be immutable SHA-256",
            errors,
        )

    identities = boundary.get("identities", {})
    service_accounts = [entry.get("service_account") for entry in identities.values()]
    require(
        len(service_accounts) == len(set(service_accounts)),
        "identity service accounts must be unique",
        errors,
    )
    require(
        boundary.get("runtime", {}).get("public_ingress") is False,
        "public ingress must be denied",
        errors,
    )
    require(
        boundary.get("runtime", {}).get("direct_console_access") is False,
        "direct Console access must be denied",
        errors,
    )
    require(
        boundary.get("queue_policy", {}).get("cross_owner_consumption_allowed") is False,
        "cross-owner queue consumption must be denied",
        errors,
    )
    database_identities = boundary.get("database_identities", {})
    require(
        database_identities.get("postgresql_administration", {}).get(
            "exposed_to_temporal_server"
        )
        is False,
        "PostgreSQL administration credentials must not reach Temporal server pods",
        errors,
    )
    require(
        database_identities.get("temporal_application", {}).get("superuser") is False,
        "Temporal database application identity must not be a superuser",
        errors,
    )
    task_queues = boundary.get("task_queues", [])
    queue_names = [
        entry.get("name") or entry.get("name_prefix") for entry in task_queues
    ]
    require(len(queue_names) == len(set(queue_names)), "task queue names must be unique", errors)
    require(
        {
            "validation-readiness-run",
            "generation-start-registry",
            "delivery-refinement-apply",
        }
        <= {entry.get("id") for entry in task_queues},
        "initial workflow task queues are incomplete",
        errors,
    )
    validation_queue = next(
        (
            entry
            for entry in task_queues
            if entry.get("id") == "validation-readiness-run"
        ),
        {},
    )
    validation_generation = validation_queue.get("generation", {})
    registry_queue = next(
        (
            entry
            for entry in task_queues
            if entry.get("id") == "generation-start-registry"
        ),
        {},
    )
    registry_generation = registry_queue.get("generation", {})
    require(
        validation_queue.get("name") is None
        and validation_queue.get("name_prefix")
        == "oos.validation-readiness-run.v1",
        "validation-readiness workflow queue must use the admitted generated prefix",
        errors,
    )
    require(
        validation_generation.get("source")
        == "activation-evidence-manifest-digest"
        and validation_generation.get("suffix_encoding") == "sha256-hex",
        "validation-readiness workflow queue must bind the activation manifest digest",
        errors,
    )
    require(
        validation_generation.get("active_restart_reuses_generation") is True
        and validation_generation.get("revoked_digest_reuse_allowed") is False,
        "activation queue generations must be restart-stable and revocation-final",
        errors,
    )
    require(
        registry_queue.get("name") is None
        and registry_queue.get("name_prefix")
        == "oos.generation-start-registry.v1"
        and registry_queue.get("owner_repo")
        == "operator-orchestration-service"
        and registry_generation.get("source")
        == "activation-evidence-manifest-digest"
        and registry_generation.get("suffix_encoding") == "sha256-hex"
        and registry_generation.get("polling_mode")
        == "continuous-with-business-worker",
        "generation start registry must use its OOS-owned continuously polled digest-bound queue",
        errors,
    )
    fresh_activation = validation_generation.get("fresh_activation", {})
    require(
        fresh_activation.get("initial_activation_requires_retirement_receipt")
        is False
        and fresh_activation.get(
            "prior_generation_retirement_receipt_required"
        )
        is True
        and fresh_activation.get("prior_digest_must_differ") is True,
        "fresh activation must require the prior retirement receipt and a new digest",
        errors,
    )
    require(
        boundary.get("queue_policy", {}).get(
            "generated_workflow_queue_pattern"
        )
        == "{name-prefix}.{activation-manifest-digest-hex}",
        "generated workflow queue pattern must remain activation-bound",
        errors,
    )
    retirement = boundary.get("generation_retirement", {})
    retirement_manifest = retirement.get("manifest", {})
    retirement_preconditions = retirement.get("preconditions", {})
    start_ingress = retirement_preconditions.get("start_ingress", {})
    ordinary_poller = retirement_preconditions.get(
        "ordinary_workflow_poller", {}
    )
    start_registry = retirement.get("start_registry", {})
    one_shot_worker = retirement.get("one_shot_worker", {})
    retirement_receipt = retirement.get("receipt", {})
    unexpected_revocation = retirement.get("unexpected_revocation", {})
    require(
        retirement.get("owner_repo") == "platform-engineering"
        and retirement.get("applies_to_queue") == "validation-readiness-run",
        "generation retirement must remain a Platform-owned queue lifecycle control",
        errors,
    )
    require(
        unexpected_revocation.get("ordinary_worker_behavior")
        == "immediate-fail-stop-unfenced"
        and unexpected_revocation.get("automatic_retirement_claim_allowed")
        is False,
        "unexpected revocation must fail-stop without claiming clean retirement",
        errors,
    )
    require(
        retirement_manifest.get("issuer") == "platform-engineering"
        and retirement_manifest.get("schema_owner_repo")
        == "operator-orchestration-service"
        and retirement_manifest.get("schema_ref")
        == "contracts/orchestration/generation-retirement-manifest.schema.json"
        and retirement_manifest.get("digest_pin_required") is True
        and retirement_manifest.get("bounded_lifetime_required") is True
        and retirement_manifest.get("maximum_lifetime_seconds") == 900
        and retirement_manifest.get("activation_manifest_binding_required") is True
        and retirement_manifest.get("generated_queue_binding_required") is True
        and retirement_manifest.get("start_registry_binding_required") is True,
        "retirement manifest must be exact, digest-pinned, and generation-bound",
        errors,
    )
    require(
        retirement_manifest.get("receipt_verifier_binding_required") is True
        and retirement_manifest.get(
            "sealed_registry_resume_requires_exact_seal_authorization"
        )
        is True,
        (
            "retirement manifest must pin receipt verification and the exact "
            "seal authorization"
        ),
        errors,
    )
    require(
        start_ingress.get("required_state") == "drained"
        and start_ingress.get("active_replicas") == 0
        and start_ingress.get("in_flight_starts") == 0
        and start_ingress.get("maximum_observation_age_seconds") == 300
        and start_ingress.get("observation_age_reference")
        == "one-shot-worker-start"
        and start_ingress.get("evidence_ref_required") is True,
        "retirement must prove drained zero-replica start ingress",
        errors,
    )
    require(
        ordinary_poller.get("required_state") == "drained"
        and ordinary_poller.get("active_replicas") == 0
        and ordinary_poller.get("maximum_observation_age_seconds") == 300
        and ordinary_poller.get("observation_age_reference")
        == "one-shot-worker-start"
        and ordinary_poller.get("evidence_ref_required") is True,
        "retirement must prove zero ordinary workflow pollers",
        errors,
    )
    require(
        start_registry.get("owner_repo") == "operator-orchestration-service"
        and start_registry.get("workflow_type") == "generationStartRegistryV1"
        and start_registry.get("workflow_id_pattern")
        == "oos:generation-start-registry:v1:{activation-manifest-digest-hex}"
        and start_registry.get("task_queue_pattern")
        == "oos.generation-start-registry.v1.{activation-manifest-digest-hex}"
        and start_registry.get("register_before_business_start_required") is True
        and start_registry.get("registration_mechanism")
        == "temporal-update-with-start"
        and start_registry.get("maximum_registration_count") == 512
        and start_registry.get("rejected_update_recorded_in_history") is False
        and start_registry.get("continuous_registry_poller_required") is True
        and start_registry.get("seal_after_start_ingress_drain_required") is True
        and start_registry.get("exact_workflow_id_reconciliation_required") is True
        and start_registry.get("invalid_registration_count_allowed") == 0
        and start_registry.get("visibility_authoritative_for_retirement") is False,
        "generation retirement must use the exact durable OOS start registry",
        errors,
    )
    require(
        one_shot_worker.get("owner_repo")
        == "operator-orchestration-service"
        and one_shot_worker.get("registry_seal_before_reconciliation_required")
        is True
        and one_shot_worker.get("cancellation_before_polling_required") is True
        and one_shot_worker.get("terminal_projection_verification_required")
        is True
        and one_shot_worker.get("authorization_recheck")
        == [
            "immediately-before-registry-worker-run",
            "immediately-before-registry-seal",
            "immediately-before-business-worker-run",
        ],
        "one-shot retirement must seal, reconcile, cancel, and reauthorize before polling",
        errors,
    )
    receipt_attestation = retirement_receipt.get("attestation", {})
    require(
        retirement_receipt.get("schema_owner_repo")
        == "operator-orchestration-service"
        and retirement_receipt.get("schema_ref")
        == "contracts/orchestration/generation-retirement-receipt.schema.json"
        and retirement_receipt.get("accepted_outcome") == "retired"
        and retirement_receipt.get("exact_registry_reconciliation_required") is True
        and retirement_receipt.get("registry_result_digest_required") is True
        and retirement_receipt.get("registry_seal_ref_binding_required") is True
        and retirement_receipt.get(
            "registry_seal_authorization_digest_required"
        )
        is True
        and receipt_attestation.get("algorithm") == "Ed25519"
        and receipt_attestation.get("issuer")
        == "operator-orchestration-service"
        and receipt_attestation.get(
            "manifest_pins_key_id_and_public_key_digest"
        )
        is True
        and receipt_attestation.get("private_key_owner_repo")
        == "operator-orchestration-service"
        and receipt_attestation.get("verified_before_fresh_activation") is True
        and retirement_receipt.get("start_timestamp_required") is True
        and retirement_receipt.get("future_recorded_at_allowed") is False
        and retirement_receipt.get("required_before_fresh_activation") is True
        and retirement_receipt.get("retained_with_platform_evidence") is True,
        "fresh activation must be gated by a retained retirement receipt",
        errors,
    )
    require(
        boundary.get("visibility", {}).get("workflow_history_retention") == "7d"
        and boundary.get("visibility", {}).get("retirement_authority")
        == "diagnostics-only",
        "Visibility must remain diagnostic while workflow history retention stays 7d",
        errors,
    )
    require(
        boundary.get("observability", {}).get("metrics", {}).get(
            "payload_bodies_allowed"
        )
        is False,
        "metrics must deny payload bodies",
        errors,
    )
    require(
        boundary.get("observability", {}).get("logs", {}).get("payload_bodies_allowed")
        is False,
        "logs must deny payload bodies",
        errors,
    )

    with tempfile.TemporaryDirectory(prefix="temporal-source-") as raw_temp:
        rendered_root = Path(raw_temp)
        subprocess.run(
            [
                sys.executable,
                str(scripts_root / "render_runtime.py"),
                "--profile-root",
                str(profile_root),
                "--output-dir",
                str(rendered_root),
                "--namespace",
                "devint-temporal-validator",
                "--operator",
                "validator",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        postgresql = docs(rendered_root / "postgresql.yaml")
        network = docs(rendered_root / "network-boundaries.yaml")
        values = load_yaml(rendered_root / "temporal-values.yaml")

        statefulset = resource(postgresql, "StatefulSet", "temporal-postgresql")
        postgres_container = statefulset["spec"]["template"]["spec"]["containers"][0]
        postgres_image = postgres_container["image"]
        require("@sha256:" in postgres_image, "PostgreSQL image is not digest pinned", errors)
        postgres_env = {
            entry["name"]: entry.get("valueFrom", {}).get("secretKeyRef", {}).get("key")
            for entry in postgres_container.get("env", [])
            if entry.get("name")
        }
        require(
            postgres_env.get("POSTGRES_USER") == "admin_username"
            and postgres_env.get("POSTGRES_PASSWORD") == "admin_password",
            "PostgreSQL bootstrap identity must use dedicated admin secret keys",
            errors,
        )
        require(
            postgres_env.get("TEMPORAL_APP_USER") == "username"
            and postgres_env.get("TEMPORAL_APP_PASSWORD") == "password",
            "Temporal persistence must use separate application secret keys",
            errors,
        )
        storage = statefulset["spec"]["volumeClaimTemplates"][0]["spec"]["resources"][
            "requests"
        ]["storage"]
        require(storage == "10Gi", "PostgreSQL storage must remain 10Gi", errors)
        init_config = resource(
            postgresql, "ConfigMap", "temporal-postgresql-init"
        ).get("data", {})
        require(
            "00-create-databases.sh" in init_config
            and "CREATE ROLE" in init_config["00-create-databases.sh"],
            "PostgreSQL init must create the bounded Temporal application role",
            errors,
        )

        policy_names = {
            item.get("metadata", {}).get("name")
            for item in network
            if item.get("kind") == "NetworkPolicy"
        }
        require(
            {
                "temporal-default-deny",
                "temporal-server-mesh",
                "temporal-postgresql-access",
                "temporal-support-frontend",
                "temporal-support-egress",
                "temporal-schema-job-egress",
                "temporal-admitted-worker-egress",
                "temporal-admitted-worker-frontend",
            }
            <= policy_names,
            "network policy set is incomplete",
            errors,
        )
        service_account_names = {
            item.get("metadata", {}).get("name")
            for item in network
            if item.get("kind") == "ServiceAccount"
        }
        require(
            {
                "temporal-runtime",
                "temporal-oos-worker",
                "temporal-wgcf-activity",
                "temporal-diagnostic",
            }
            <= service_account_names,
            "runtime identity ServiceAccount set is incomplete",
            errors,
        )
        require(
            values.get("serviceAccount", {}).get("create") is False,
            "Temporal chart must use the predeclared runtime ServiceAccount",
            errors,
        )
        require(
            values.get("web", {}).get("ingress", {}).get("enabled") is False,
            "Temporal UI ingress must remain disabled",
            errors,
        )
        require(
            values.get("web", {}).get("service", {}).get("type") == "ClusterIP",
            "Temporal UI service must remain ClusterIP",
            errors,
        )
        require(
            values.get("server", {}).get("frontend", {}).get("service", {}).get("type")
            == "ClusterIP",
            "Temporal frontend service must remain ClusterIP",
            errors,
        )
        require(
            values["server"]["config"]["namespaces"]["namespace"][0]["retention"] == "7d",
            "rendered namespace retention must remain 7d",
            errors,
        )
        stores = values["server"]["config"]["persistence"]["datastores"]
        require(
            stores["default"]["sql"].get("existingSecret") == "temporal-postgresql"
            and stores["visibility"]["sql"].get("existingSecret")
            == "temporal-postgresql",
            "Temporal persistence must reference the namespace-scoped PostgreSQL Secret",
            errors,
        )
        rendered_text = (rendered_root / "temporal-values.yaml").read_text(
            encoding="utf-8"
        )
        require(
            "@sha256:" in rendered_text,
            "Temporal chart values must use digest-pinned images",
            errors,
        )
        require(
            "password:" not in rendered_text,
            "Temporal values must not contain a database password value",
            errors,
        )

    persistence_source = (scripts_root / "lib" / "persistence.sh").read_text(
        encoding="utf-8"
    )
    restore_source = (scripts_root / "restore.sh").read_text(encoding="utf-8")
    require(
        "pg_dumpall" not in persistence_source
        and "pg_dump --clean" in persistence_source,
        "Temporal backups must exclude PostgreSQL global role state",
        errors,
    )
    require(
        '"role_passwords_included": False' in persistence_source,
        "Temporal backup manifests must deny role-password content",
        errors,
    )
    require(
        "--from-literal" not in persistence_source,
        "PostgreSQL secret values must not be exposed through command arguments",
        errors,
    )
    require(
        'manifest.get("role_passwords_included") is not False' in restore_source,
        "Temporal restore must reject backups that may contain role passwords",
        errors,
    )

    if args.rendered_chart:
        validate_rendered_chart(args.rendered_chart.resolve(), errors)

    if errors:
        raise SystemExit("\n".join(f"- {error}" for error in errors))
    print("temporal dev-integration profile source valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
