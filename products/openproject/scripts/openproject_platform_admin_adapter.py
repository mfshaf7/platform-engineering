#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import uuid
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
PRODUCT_DIR = SCRIPT_DIR.parent
CONTRACT_PATH = PRODUCT_DIR / "openproject-platform-admin-surface.json"
OPENPROJECT_POD_LABEL_SELECTOR = (
    "app.kubernetes.io/component=web,app.kubernetes.io/name=openproject"
)


def load_contract() -> dict[str, object]:
    with CONTRACT_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def kubectl_base() -> list[str]:
    return shlex.split(os.environ.get("KUBECTL", "k3s kubectl"))


def openproject_namespace() -> str:
    return os.environ.get("OPENPROJECT_NAMESPACE", "openproject")


def run(command: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def openproject_pod() -> str:
    result = run(
        [
            *kubectl_base(),
            "-n",
            openproject_namespace(),
            "get",
            "pod",
            "-l",
            OPENPROJECT_POD_LABEL_SELECTOR,
            "-o",
            "jsonpath={.items[0].metadata.name}",
        ],
        capture_output=True,
    )
    pod_name = result.stdout.strip()
    if not pod_name:
        raise RuntimeError("failed to resolve the OpenProject web pod")
    return pod_name


def find_operation(contract: dict[str, object], operation_id: str) -> dict[str, object]:
    for entry in contract["shell_surfaces"]:
        if entry.get("operation_id") == operation_id:
            return entry
    raise RuntimeError(f"operation {operation_id!r} is not defined in the platform-admin contract")


def copy_to_pod(pod_name: str, local_path: Path, remote_path: str) -> None:
    run(
        [
            *kubectl_base(),
            "-n",
            openproject_namespace(),
            "cp",
            str(local_path),
            f"{pod_name}:{remote_path}",
        ]
    )


def ensure_remote_directory(pod_name: str, remote_dir: str) -> None:
    run(
        [
            *kubectl_base(),
            "-n",
            openproject_namespace(),
            "exec",
            pod_name,
            "--",
            "mkdir",
            "-p",
            remote_dir,
        ]
    )


def cleanup_remote_directory(pod_name: str, remote_dir: str) -> None:
    subprocess.run(
        [
            *kubectl_base(),
            "-n",
            openproject_namespace(),
            "exec",
            pod_name,
            "--",
            "rm",
            "-rf",
            remote_dir,
        ],
        check=False,
        text=True,
        capture_output=True,
    )


def exec_runner(pod_name: str, remote_runner_path: str, pass_env: list[str]) -> int:
    env_pairs = [
        f"{key}={os.environ.get(key, '')}"
        for key in pass_env
    ]
    command = [
        *kubectl_base(),
        "-n",
        openproject_namespace(),
        "exec",
        pod_name,
        "--",
        "env",
        *env_pairs,
        "sh",
        "-ceu",
        'bundle exec rails runner "$1"',
        "sh",
        remote_runner_path,
    ]
    completed = subprocess.run(command, text=True)
    return completed.returncode


def run_operation(operation_id: str) -> int:
    contract = load_contract()
    operation = find_operation(contract, operation_id)
    runner_files = [SCRIPT_DIR / name for name in operation.get("internal_runner_files", [])]
    support_files = [SCRIPT_DIR / name for name in operation.get("support_files", [])]
    if len(runner_files) != 1:
        raise RuntimeError(
            f"operation {operation_id!r} must declare exactly one internal runner file"
        )
    missing = [path for path in [*runner_files, *support_files] if not path.exists()]
    if missing:
        raise RuntimeError(
            f"operation {operation_id!r} references missing files: {', '.join(str(path) for path in missing)}"
        )

    pod_name = openproject_pod()
    remote_dir = f"/tmp/openproject-platform-admin-{operation_id}-{uuid.uuid4().hex[:8]}"
    ensure_remote_directory(pod_name, remote_dir)
    try:
        for local_path in [*runner_files, *support_files]:
            copy_to_pod(pod_name, local_path, f"{remote_dir}/{local_path.name}")
        return exec_runner(
            pod_name,
            f"{remote_dir}/{runner_files[0].name}",
            [str(key) for key in operation.get("pass_env", [])],
        )
    finally:
        cleanup_remote_directory(pod_name, remote_dir)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a contract-defined OpenProject platform-admin operation inside the web pod."
    )
    parser.add_argument(
        "--operation",
        required=True,
        help="operation id declared in openproject-platform-admin-surface.json",
    )
    args = parser.parse_args()
    return run_operation(args.operation)


if __name__ == "__main__":
    raise SystemExit(main())

