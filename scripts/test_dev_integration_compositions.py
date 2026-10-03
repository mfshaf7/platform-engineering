#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

import yaml

from test_dev_integration_preflight import CompositionPreflightTests


MODULE_PATH = Path(__file__).with_name("dev_integration_compositions.py")
SPEC = importlib.util.spec_from_file_location("dev_integration_compositions", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
COMPOSITIONS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPOSITIONS)


def registry() -> dict:
    profiles = {
        profile_id: {
            "lifecycle": "active",
            "runtime_owner": "platform-engineering",
        }
        for profile_id in ("root", "context", "gateway")
    }
    return {
        "profiles": profiles,
        "runtime_compositions": {
            "example": {
                "owner_repo": "platform-engineering",
                "root_profile_id": "root",
                "profiles": {
                    profile_id: {"required_lifecycle": "active"}
                    for profile_id in profiles
                },
                "dependencies": [
                    {
                        "consumer_profile_id": "root",
                        "provider_profile_id": "context",
                        "endpoint_projections": [
                            {
                                "environment_variable": "CONTEXT_URL",
                                "scheme": "http",
                                "service_name": "context-api",
                                "service_port": 8080,
                            }
                        ],
                    },
                    {
                        "consumer_profile_id": "root",
                        "provider_profile_id": "gateway",
                        "endpoint_projections": [
                            {
                                "environment_variable": "GATEWAY_URL",
                                "scheme": "http",
                                "service_name": "gateway-api",
                                "service_port": 8081,
                            }
                        ],
                    },
                ],
                "caller_bindings": {
                    "context-caller": {
                        "owner_repo": "platform-engineering",
                        "caller_id": "root-service",
                        "consumer_profile_id": "root",
                        "provider_profile_id": "context",
                        "consumer_environment_variable": "CONTEXT_CALLER_ID",
                        "provider_environment_variable": "CONTEXT_ALLOWED_CALLERS",
                    }
                },
                "credential_bindings": {
                    "caller": {
                        "owner_repo": "platform-engineering",
                        "value_source": "runtime-generated",
                        "retention": "composition-lifetime",
                        "projections": [
                            {
                                "profile_id": "root",
                                "environment_variable": "CALLER_SECRET",
                            },
                            {
                                "profile_id": "context",
                                "environment_variable": "SHARED_SECRET",
                            },
                        ],
                    }
                },
                "profile_bindings": {
                    "feature-enabled": {
                        "owner_repo": "platform-engineering",
                        "profile_id": "root",
                        "environment_variable": "FEATURE_ENABLED",
                        "source": {"kind": "literal", "value": "true"},
                    },
                    "root-service": {
                        "owner_repo": "platform-engineering",
                        "profile_id": "root",
                        "environment_variable": "ROOT_SERVICE_URL",
                        "source": {
                            "kind": "profile-service",
                            "address_format": "url",
                            "scheme": "http",
                            "service_name": "root-api",
                            "service_port": 8082,
                        },
                    },
                    "operator-namespace": {
                        "owner_repo": "platform-engineering",
                        "profile_id": "root",
                        "environment_variable": "OPERATOR_NAMESPACE",
                        "source": {
                            "kind": "operator-template",
                            "template": "governance-{operator}",
                        },
                    },
                    "context-namespace": {
                        "owner_repo": "platform-engineering",
                        "profile_id": "root",
                        "environment_variable": "CONTEXT_NAMESPACE",
                        "source": {
                            "kind": "profile-namespace",
                            "source_profile_id": "context",
                        },
                    },
                },
            }
        },
    }


class RuntimeCompositionTests(unittest.TestCase):
    def composition(self) -> tuple[dict, list[str]]:
        return COMPOSITIONS.resolve_runtime_composition(registry(), "example")

    def test_dependency_order_starts_providers_before_root(self) -> None:
        _, order = self.composition()
        self.assertEqual(order, ["context", "gateway", "root"])

    def test_unknown_and_inactive_profiles_fail_closed(self) -> None:
        payload = registry()
        payload["runtime_compositions"]["example"]["profiles"]["missing"] = {
            "required_lifecycle": "active"
        }
        with self.assertRaisesRegex(COMPOSITIONS.CompositionError, "not registered"):
            COMPOSITIONS.resolve_runtime_composition(payload, "example")

        payload = registry()
        payload["profiles"]["context"]["lifecycle"] = "suspended"
        with self.assertRaisesRegex(COMPOSITIONS.CompositionError, "requires lifecycle"):
            COMPOSITIONS.resolve_runtime_composition(payload, "example")

    def test_dependency_cycle_fails_closed(self) -> None:
        payload = registry()
        payload["runtime_compositions"]["example"]["dependencies"].append(
            {
                "consumer_profile_id": "context",
                "provider_profile_id": "root",
                "endpoint_projections": [],
            }
        )
        with self.assertRaisesRegex(COMPOSITIONS.CompositionError, "dependency cycle"):
            COMPOSITIONS.resolve_runtime_composition(payload, "example")

    def test_endpoint_and_credential_projection_is_profile_bounded(self) -> None:
        composition, _ = self.composition()
        environments = COMPOSITIONS.build_profile_environments(
            composition,
            namespaces={
                "root": "root-ns",
                "context": "context-ns",
                "gateway": "gateway-ns",
            },
            credential_values={"caller": "private-value"},
            operator="MF Shaf7",
        )
        self.assertEqual(
            environments["root"],
            {
                "CONTEXT_URL": "http://context-api.context-ns.svc.cluster.local:8080",
                "GATEWAY_URL": "http://gateway-api.gateway-ns.svc.cluster.local:8081",
                "CONTEXT_CALLER_ID": "root-service",
                "CALLER_SECRET": "private-value",
                "FEATURE_ENABLED": "true",
                "ROOT_SERVICE_URL": "http://root-api.root-ns.svc.cluster.local:8082",
                "OPERATOR_NAMESPACE": "governance-mf-shaf7",
                "CONTEXT_NAMESPACE": "context-ns",
            },
        )
        self.assertEqual(
            environments["context"],
            {
                "CONTEXT_ALLOWED_CALLERS": "root-service",
                "SHARED_SECRET": "private-value",
            },
        )
        self.assertEqual(environments["gateway"], {})

        gateway_environment = COMPOSITIONS.bounded_child_environment(
            composition,
            base_environment={
                "PATH": "/usr/bin",
                "CALLER_SECRET": "ambient-secret",
                "CONTEXT_URL": "http://ambient.invalid",
                "CONTEXT_ALLOWED_CALLERS": "ambient-caller",
                "FEATURE_ENABLED": "false",
            },
            profile_environment=environments["gateway"],
        )
        self.assertEqual(gateway_environment, {"PATH": "/usr/bin"})

    def test_standalone_environment_removes_all_composition_bindings(self) -> None:
        bounded = COMPOSITIONS.bounded_standalone_environment(
            registry(),
            base_environment={
                "PATH": "/usr/bin",
                "CONTEXT_URL": "stale",
                "CALLER_SECRET": "stale",
                "DEVINT_COMPOSITION_ID": "stale",
                "DEVINT_COMPOSITION_ROOT_PROFILE_ID": "root",
                "UNRELATED": "preserved",
            },
        )
        self.assertEqual(
            bounded,
            {"PATH": "/usr/bin", "UNRELATED": "preserved"},
        )

    def test_host_port_projection_omits_scheme(self) -> None:
        payload = registry()
        projection = payload["runtime_compositions"]["example"]["dependencies"][1][
            "endpoint_projections"
        ][0]
        projection.pop("scheme")
        projection["address_format"] = "host-port"
        composition, _ = COMPOSITIONS.resolve_runtime_composition(payload, "example")
        environments = COMPOSITIONS.build_profile_environments(
            composition,
            namespaces={
                "root": "root-ns",
                "context": "context-ns",
                "gateway": "gateway-ns",
            },
            credential_values={"caller": "private-value"},
            operator="operator",
        )
        self.assertEqual(
            environments["root"]["GATEWAY_URL"],
            "gateway-api.gateway-ns.svc.cluster.local:8081",
        )

    def test_binding_and_endpoint_contracts_fail_closed(self) -> None:
        payload = registry()
        payload["runtime_compositions"]["example"]["caller_bindings"][
            "context-caller"
        ].update(
            {
                "consumer_profile_id": "context",
                "provider_profile_id": "gateway",
            }
        )
        with self.assertRaisesRegex(
            COMPOSITIONS.CompositionError,
            "does not match a declared dependency edge",
        ):
            COMPOSITIONS.resolve_runtime_composition(payload, "example")

        payload = registry()
        payload["runtime_compositions"]["example"]["caller_bindings"][
            "context-caller"
        ]["consumer_profile_id"] = ["root"]
        with self.assertRaisesRegex(
            COMPOSITIONS.CompositionError,
            "invalid owner, profile, or caller",
        ):
            COMPOSITIONS.resolve_runtime_composition(payload, "example")

        payload = registry()
        payload["runtime_compositions"]["example"]["profile_bindings"][
            "feature-enabled"
        ]["environment_variable"] = "CONTEXT_URL"
        with self.assertRaisesRegex(COMPOSITIONS.CompositionError, "repeated projection"):
            COMPOSITIONS.resolve_runtime_composition(payload, "example")

        payload = registry()
        projection = payload["runtime_compositions"]["example"]["dependencies"][0][
            "endpoint_projections"
        ][0]
        projection["address_format"] = "host-port"
        with self.assertRaisesRegex(COMPOSITIONS.CompositionError, "must not declare a scheme"):
            COMPOSITIONS.resolve_runtime_composition(payload, "example")

    def test_operator_template_contract_fails_closed(self) -> None:
        invalid_templates = (
            "governance-operator",
            "governance-{operator}-{operator}",
            "governance-{profile}",
            "governance-{operator.upper}",
            "governance_{operator}",
        )
        for template in invalid_templates:
            with self.subTest(template=template):
                payload = registry()
                payload["runtime_compositions"]["example"]["profile_bindings"][
                    "operator-namespace"
                ]["source"]["template"] = template
                with self.assertRaises(COMPOSITIONS.CompositionError):
                    COMPOSITIONS.resolve_runtime_composition(payload, "example")

        payload = registry()
        payload["runtime_compositions"]["example"]["profile_bindings"][
            "operator-namespace"
        ]["source"]["extra"] = "not-allowed"
        with self.assertRaisesRegex(COMPOSITIONS.CompositionError, "invalid operator template"):
            COMPOSITIONS.resolve_runtime_composition(payload, "example")

    def test_profile_namespace_contract_fails_closed(self) -> None:
        for source in (
            {"kind": "profile-namespace", "source_profile_id": "missing"},
            {"kind": "profile-namespace"},
            {
                "kind": "profile-namespace",
                "source_profile_id": "context",
                "extra": "not-allowed",
            },
        ):
            with self.subTest(source=source):
                payload = registry()
                payload["runtime_compositions"]["example"]["profile_bindings"][
                    "context-namespace"
                ]["source"] = source
                with self.assertRaisesRegex(
                    COMPOSITIONS.CompositionError,
                    "invalid namespace source",
                ):
                    COMPOSITIONS.resolve_runtime_composition(payload, "example")

    def test_profile_namespace_projects_runner_computed_namespace(self) -> None:
        composition, _ = self.composition()
        environments = COMPOSITIONS.build_profile_environments(
            composition,
            namespaces={
                "root": "root-namespace",
                "context": "runner-bounded-context-namespace",
                "gateway": "gateway-namespace",
            },
            credential_values={},
            operator="operator",
        )
        self.assertEqual(
            environments["root"]["CONTEXT_NAMESPACE"],
            "runner-bounded-context-namespace",
        )

    def test_runtime_credential_is_private_and_reused(self) -> None:
        composition, _ = self.composition()
        with tempfile.TemporaryDirectory(prefix="devint-composition-") as temp_dir:
            state_root = Path(temp_dir) / "state"
            first, created = COMPOSITIONS.load_or_create_credentials(
                composition,
                state_root=state_root,
                create=True,
            )
            second, created_again = COMPOSITIONS.load_or_create_credentials(
                composition,
                state_root=state_root,
                create=True,
            )
            credential_path = state_root / "credentials/caller.secret"
            self.assertTrue(created)
            self.assertFalse(created_again)
            self.assertEqual(first, second)
            self.assertEqual(credential_path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(credential_path.stat().st_uid, os.getuid())

    def test_profile_smoke_context_reuses_active_composition_without_writing(self) -> None:
        payload = registry()
        composition, order = COMPOSITIONS.resolve_runtime_composition(payload, "example")
        namespaces = {profile_id: f"{profile_id}-ns" for profile_id in order}
        with tempfile.TemporaryDirectory(prefix="devint-composition-") as temp_dir:
            workspace_root = Path(temp_dir)
            state_root = COMPOSITIONS.composition_state_root(
                workspace_root,
                "example",
                "operator",
            )
            self.assertEqual(
                COMPOSITIONS.execute_composition(
                    action="up",
                    composition_id="example",
                    composition=composition,
                    profile_order=order,
                    namespaces=namespaces,
                    operator="operator",
                    state_root=state_root,
                    dispatch=lambda *_: 0,
                ),
                0,
            )
            state_path = state_root / "current-composition.yaml"
            credential_path = state_root / "credentials/caller.secret"
            state_before = state_path.read_bytes()
            credential_before = credential_path.read_bytes()
            state_mtime = state_path.stat().st_mtime_ns
            credential_mtime = credential_path.stat().st_mtime_ns

            context = COMPOSITIONS.resolve_active_profile_composition_context(
                payload,
                profile_id="root",
                operator="operator",
                workspace_root=workspace_root,
                namespaces={"example": namespaces},
            )

            self.assertIsNotNone(context)
            self.assertEqual(context["composition_id"], "example")
            self.assertEqual(context["profile_environment"]["FEATURE_ENABLED"], "true")
            self.assertEqual(
                context["profile_environment"]["CALLER_SECRET"],
                credential_before.decode().strip(),
            )
            self.assertEqual(state_path.read_bytes(), state_before)
            self.assertEqual(credential_path.read_bytes(), credential_before)
            self.assertEqual(state_path.stat().st_mtime_ns, state_mtime)
            self.assertEqual(credential_path.stat().st_mtime_ns, credential_mtime)

    def test_profile_smoke_context_fails_on_ambiguous_active_compositions(self) -> None:
        payload = registry()
        payload["runtime_compositions"]["another"] = copy.deepcopy(
            payload["runtime_compositions"]["example"]
        )
        with tempfile.TemporaryDirectory(prefix="devint-composition-") as temp_dir:
            workspace_root = Path(temp_dir)
            all_namespaces = {}
            for composition_id in ("example", "another"):
                composition, order = COMPOSITIONS.resolve_runtime_composition(
                    payload,
                    composition_id,
                )
                namespaces = {profile_id: f"{profile_id}-ns" for profile_id in order}
                all_namespaces[composition_id] = namespaces
                self.assertEqual(
                    COMPOSITIONS.execute_composition(
                        action="up",
                        composition_id=composition_id,
                        composition=composition,
                        profile_order=order,
                        namespaces=namespaces,
                        operator="operator",
                        state_root=COMPOSITIONS.composition_state_root(
                            workspace_root,
                            composition_id,
                            "operator",
                        ),
                        dispatch=lambda *_: 0,
                    ),
                    0,
                )
            with self.assertRaisesRegex(
                COMPOSITIONS.CompositionError,
                "more than one active composition",
            ):
                COMPOSITIONS.resolve_active_profile_composition_context(
                    payload,
                    profile_id="root",
                    operator="operator",
                    workspace_root=workspace_root,
                    namespaces=all_namespaces,
                )

    def test_unsafe_credential_permissions_fail_closed(self) -> None:
        composition, _ = self.composition()
        with tempfile.TemporaryDirectory(prefix="devint-composition-") as temp_dir:
            state_root = Path(temp_dir) / "state"
            COMPOSITIONS.load_or_create_credentials(
                composition,
                state_root=state_root,
                create=True,
            )
            credential_path = state_root / "credentials/caller.secret"
            credential_path.chmod(0o644)
            with self.assertRaisesRegex(COMPOSITIONS.CompositionError, "not a private"):
                COMPOSITIONS.load_or_create_credentials(
                    composition,
                    state_root=state_root,
                    create=False,
                )

    def test_active_status_fails_when_credential_is_missing(self) -> None:
        composition, order = self.composition()
        with tempfile.TemporaryDirectory(prefix="devint-composition-") as temp_dir:
            state_root = Path(temp_dir) / "state"
            COMPOSITIONS._write_private_yaml(
                state_root / "current-composition.yaml",
                {
                    "composition_id": "example",
                    "operator": "operator",
                    "lifecycle": "active",
                },
            )
            with self.assertRaisesRegex(COMPOSITIONS.CompositionError, "is missing"):
                COMPOSITIONS.execute_composition(
                    action="status",
                    composition_id="example",
                    composition=composition,
                    profile_order=order,
                    namespaces={profile_id: f"{profile_id}-ns" for profile_id in order},
                    operator="operator",
                    state_root=state_root,
                    dispatch=lambda *_: 0,
                )

    def test_failed_status_projects_degraded_without_removing_credential(self) -> None:
        composition, order = self.composition()
        with tempfile.TemporaryDirectory(prefix="devint-composition-") as temp_dir:
            state_root = Path(temp_dir) / "state"
            arguments = {
                "composition_id": "example",
                "composition": composition,
                "profile_order": order,
                "namespaces": {profile_id: f"{profile_id}-ns" for profile_id in order},
                "operator": "operator",
                "state_root": state_root,
            }
            self.assertEqual(
                COMPOSITIONS.execute_composition(
                    action="up",
                    dispatch=lambda *_: 0,
                    **arguments,
                ),
                0,
            )
            self.assertEqual(
                COMPOSITIONS.execute_composition(
                    action="status",
                    dispatch=lambda _action, profile_id, _environment: int(
                        profile_id == "gateway"
                    ),
                    **arguments,
                ),
                1,
            )
            state = yaml.safe_load(
                (state_root / "current-composition.yaml").read_text()
            )
            self.assertEqual(state["lifecycle"], "degraded")
            self.assertTrue((state_root / "credentials/caller.secret").is_file())

    def test_up_replays_and_down_uses_reverse_order_without_secret_in_state(self) -> None:
        composition, order = self.composition()
        calls: list[tuple[str, str]] = []

        def dispatch(action: str, profile_id: str, _environment: dict) -> int:
            calls.append((action, profile_id))
            return 0

        with tempfile.TemporaryDirectory(prefix="devint-composition-") as temp_dir:
            state_root = Path(temp_dir) / "state"
            arguments = {
                "composition_id": "example",
                "composition": composition,
                "profile_order": order,
                "namespaces": {profile_id: f"{profile_id}-ns" for profile_id in order},
                "operator": "operator",
                "state_root": state_root,
                "dispatch": dispatch,
            }
            self.assertEqual(COMPOSITIONS.execute_composition(action="up", **arguments), 0)
            first_secret = (state_root / "credentials/caller.secret").read_text()
            self.assertEqual(COMPOSITIONS.execute_composition(action="up", **arguments), 0)
            self.assertEqual(
                (state_root / "credentials/caller.secret").read_text(),
                first_secret,
            )
            self.assertEqual(COMPOSITIONS.execute_composition(action="down", **arguments), 0)
            self.assertEqual(
                calls[-3:],
                [("down", "root"), ("down", "gateway"), ("down", "context")],
            )
            state_text = (state_root / "current-composition.yaml").read_text()
            self.assertNotIn(first_secret, state_text)
            self.assertEqual(yaml.safe_load(state_text)["lifecycle"], "suspended")
            self.assertFalse((state_root / "credentials/caller.secret").exists())

    def test_failed_up_rolls_back_started_profiles(self) -> None:
        composition, order = self.composition()
        calls: list[tuple[str, str]] = []

        def dispatch(action: str, profile_id: str, _environment: dict) -> int:
            calls.append((action, profile_id))
            return 1 if action == "up" and profile_id == "gateway" else 0

        with tempfile.TemporaryDirectory(prefix="devint-composition-") as temp_dir:
            state_root = Path(temp_dir) / "state"
            returncode = COMPOSITIONS.execute_composition(
                action="up",
                composition_id="example",
                composition=composition,
                profile_order=order,
                namespaces={profile_id: f"{profile_id}-ns" for profile_id in order},
                operator="operator",
                state_root=state_root,
                dispatch=dispatch,
            )
            self.assertEqual(returncode, 1)
            self.assertEqual(
                calls,
                [
                    ("up", "context"),
                    ("up", "gateway"),
                    ("down", "gateway"),
                    ("down", "context"),
                ],
            )
            self.assertFalse((state_root / "credentials/caller.secret").exists())
            state = yaml.safe_load(
                (state_root / "current-composition.yaml").read_text()
            )
            self.assertEqual(state["lifecycle"], "degraded")
            self.assertEqual(
                state["rollback_completed_profile_ids"],
                ["gateway", "context"],
            )
            self.assertEqual(state["rollback_failed_profile_ids"], [])

    def test_cleanup_rejects_foreign_composition_state(self) -> None:
        composition, order = self.composition()
        with tempfile.TemporaryDirectory(prefix="devint-composition-") as temp_dir:
            state_root = Path(temp_dir) / "state"
            COMPOSITIONS._write_private_yaml(
                state_root / "current-composition.yaml",
                {
                    "composition_id": "another-composition",
                    "operator": "operator",
                    "lifecycle": "active",
                },
            )
            with self.assertRaisesRegex(
                COMPOSITIONS.CompositionError,
                "different composition or operator",
            ):
                COMPOSITIONS.execute_composition(
                    action="down",
                    composition_id="example",
                    composition=composition,
                    profile_order=order,
                    namespaces={profile_id: f"{profile_id}-ns" for profile_id in order},
                    operator="operator",
                    state_root=state_root,
                    dispatch=lambda *_: 0,
                )


if __name__ == "__main__":
    unittest.main()
