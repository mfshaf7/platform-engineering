"""Bounded independent refresh of the existing admitted observation projections."""
from __future__ import annotations

import fcntl
import os
from pathlib import Path
import shutil
import subprocess
import sys

import console_runtime_observations as observations

SERVICE = "governance-console-observations.service"
TIMER = "governance-console-observations.timer"


def enabled(policy):
    return policy.get("runtime_observations", {}).get("enabled") is True


def paths(state_root):
    root = state_root / "private/runtime-observations"
    return root, root / "runtime.json", root / "product-health.json", root / "product-health.receipt.json"


def activation_environment(state_root):
    _, runtime, health, receipt = paths(state_root)
    return {"GOVERNANCE_CONSOLE_RUNTIME_OBSERVATION_PATH": str(runtime),
            "GOVERNANCE_CONSOLE_PRODUCT_HEALTH_PROJECTION_PATH": str(health),
            "GOVERNANCE_CONSOLE_PRODUCT_HEALTH_RECEIPT_PATH": str(receipt)}


def bounded_runner(command):
    try:
        return subprocess.run(command, text=True, capture_output=True, check=False, timeout=10)
    except subprocess.TimeoutExpired:
        raise observations.ObservationError("Admitted workload observation timed out.") from None


def refresh(state_root, *, operator, runner=bounded_runner, now=None):
    root, runtime_path, health_path, receipt_path = paths(state_root)
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if root.is_symlink() or not root.is_dir() or root.stat().st_uid != os.geteuid():
        raise observations.ObservationError("Runtime observation custody is invalid.")
    root.chmod(0o700)
    fd = os.open(root / "refresh.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        if os.fstat(fd).st_uid != os.geteuid() or os.fstat(fd).st_mode & 0o077:
            raise observations.ObservationError("Runtime observation lock custody is invalid.")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise observations.ObservationError("Runtime observation refresh is already running.") from None
        policy = observations.load_policy()
        # Complete collection and validate both projections before any published
        # file changes. A failed collection leaves the previous evidence to
        # expire naturally; it never manufactures another healthy timestamp.
        runtime = observations.build_projection(policy, operator=operator, runner=runner, now=now)
        observations.validate_projection(runtime)
        health = observations.build_product_health_projection(policy, runtime, now=now)
        receipt = observations.create_product_health_receipt(policy, health, now=now)
        observations.write_private_json(runtime_path, runtime)
        observations.write_private_json(health_path, health)
        observations.write_private_json(receipt_path, receipt)
        # Each replacement is atomic. A read spanning the health/receipt
        # replacements fails the existing exact-digest reader until coherent.
        return {"runtime": observations.projection_summary(runtime, now=now), "product_health": receipt}
    finally:
        os.close(fd)


def install(*, repo_root, state_root, unit_root, run):
    python = shutil.which("python3")
    if not python:
        raise observations.ObservationError("Observation refresh requires the validated Python runtime.")
    # Use the same systemd argument quoting as the existing retained lifecycle.
    sys.path.insert(0, str(repo_root / "scripts"))
    try:
        from dev_integration_auto_resume import _systemd_quote, _systemd_path_value
    finally:
        sys.path.pop(0)
    command = [python, str(repo_root / "products/governance-operations-console/scripts/console_complete_runtime.py"),
               "refresh-observations"]
    unit_root.mkdir(parents=True, exist_ok=True)
    service = f"""[Unit]
Description=Refresh admitted Governance Console runtime observations
After=network.target
ConditionPathExists={_systemd_path_value(state_root / 'active.json')}

[Service]
Type=oneshot
WorkingDirectory={_systemd_path_value(repo_root)}
ExecStart={' '.join(_systemd_quote(value) for value in command)}
TimeoutStartSec=80
MemoryAccounting=true
MemoryHigh=192M
MemoryMax=256M
NoNewPrivileges=true
PrivateTmp=true
"""
    timer = f"""[Unit]
Description=Maintain fresh Governance Console runtime observations

[Timer]
OnActiveSec=5s
OnUnitInactiveSec=30s
AccuracySec=1s
Unit={SERVICE}

[Install]
WantedBy=timers.target
"""
    for name, content in ((SERVICE, service), (TIMER, timer)):
        path = unit_root / name
        if path.is_symlink():
            raise observations.ObservationError("Observation service path must not be a symlink.")
        path.write_text(content)
    run(["systemctl", "--user", "daemon-reload"])
    run(["systemctl", "--user", "enable", "--now", TIMER])


def status(state_root, *, run, now=None):
    if run(["systemctl", "--user", "is-active", "--quiet", TIMER], check=False).returncode:
        raise observations.ObservationError("Independent runtime observation timer is inactive.")
    _, runtime_path, health_path, receipt_path = paths(state_root)
    runtime = observations.load_json(runtime_path, "runtime observation projection")
    health = observations.load_json(health_path, "product health projection")
    receipt = observations.load_json(receipt_path, "product health receipt")
    observations.validate_product_health_projection(health, runtime_projection=runtime, policy=observations.load_policy())
    current = observations.create_product_health_receipt(observations.load_policy(), health, now=now)
    # Its stored freshness records publication time; current freshness comes
    # from the source validity window, without rewriting any source timestamp.
    if any(receipt.get(key) != value for key, value in current.items() if key not in {"freshness", "counts"}):
        raise observations.ObservationError("Product health receipt does not bind the published projection.")
    summary = observations.projection_summary(runtime, now=now)
    if summary["freshness"] != "current" or current["freshness"] != "current":
        raise observations.ObservationError("Admitted runtime observations are stale.")
    return {"timer_active": True, "runtime": summary, "product_health": current}
