"""Produce and verify case-specific evidence for the isolated project runtime."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

from console_project_runtime_rehearsal import REPO_ROOT, exercise
from agent_source_identity import write_json_atomic
from agent_source_instance import digest, invalid_constant, strict_object
from console_cross_domain_activation import ActivationError, ensure_private_directory
from console_project_runtime_snapshot import bounded_file, directory_fd


RECEIPT_ROOT = Path.home() / ".local/state/platform-engineering/project-runtime/rehearsal-receipts"
ARTIFACT_TYPE = "platform-project-runtime-rehearsal/v1"
REVIEWED_BROKER_REVISION = "de3df94439f1741954087ec5f5718b098d10cf12"
COMMIT = re.compile(r"[a-f0-9]{40}")
MAX_RECEIPT_BYTES = 32768
OBSERVATIONS = {
    "run-update": {
        "paired": {
            "servedSameProjectFrontendAndApi": True,
            "previousPairRetired": True,
            "readBackExactRun": True,
            "reusedApprovedDependencyCache": True,
        },
    },
    "failed-update": {
        "failed_update": {
            "failedUpdateKeptPreviousFrontendAndApi": True,
            "failedUpdateHasNoReadyInstance": True,
        },
        "retained_data": {
            "interruptedStopReadAsUnknown": True,
            "failedUpdateRetainedData": True,
            "resumeReusedOriginalArtifactAndSetup": True,
        },
    },
    "retained-data": {
        "retained_data": {
            "stopReleasedBothPods": True,
            "originalStopReadBackAfterOwnerRestart": True,
            "resumeReusedOriginalArtifactAndSetup": True,
            "pairedApiReadSameData": True,
            "scratchDisposed": True,
            "resumeWorkedWithoutBuildCache": True,
            "unconfirmedResetHttp": 409,
            "resetAttemptLeftStateAndDataUntouched": True,
            "volumeUidPreserved": True,
        },
    },
    "isolation-capacity": {
        "paired": {
            "foreignNamespaceWithPermittingIngressDenied": True,
            "protectedServicesDenied": True,
            "noInheritedAccess": True,
        },
        "capacity": {
            "nativeCpuQuotaRefusedConcurrentTransfer": True,
            "overBudgetRunState": "failed",
            "previousPairStayedReady": True,
            "strayPods": 0,
        },
    },
}


class EvidenceError(ValueError):
    """The owner could not prove an operating case."""


def source_identity(platform_head: str, broker_head: str) -> dict[str, str]:
    if any(COMMIT.fullmatch(value) is None for value in (platform_head, broker_head)):
        raise EvidenceError("Operating evidence requires exact Platform and Broker commits.")
    return {"platform-engineering": platform_head, "operator-orchestration-service": broker_head}


def git_output(repo: Path, *arguments: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "--no-replace-objects", "-C", str(repo), *arguments],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=12,
        ).strip()
    except (OSError, subprocess.SubprocessError) as error:
        raise EvidenceError("The exact source checkout could not be verified.") from error


def require_checkout(repo: Path, head: str, *, clean: bool = False) -> None:
    if git_output(repo, "rev-parse", "HEAD") != head:
        raise EvidenceError("The checkout belongs to a different source revision.")
    if clean and git_output(repo, "status", "--porcelain"):
        raise EvidenceError("Run the rehearsal from a clean exact source checkout.")


def require_observations(case: str, scenarios: dict) -> None:
    for scenario, required in OBSERVATIONS[case].items():
        observed = scenarios.get(scenario)
        if not isinstance(observed, dict) or observed.get("disposableNamespacesRemoved") is not True:
            raise EvidenceError(f"The rehearsal for {scenario} is missing or its cleanup is unconfirmed.")
        for field, expected in required.items():
            value = observed.get(field)
            if type(value) is not type(expected) or value != expected:
                raise EvidenceError(f"The rehearsal for {scenario} did not prove {field}.")


def receipt_name(source: dict[str, str]) -> str:
    return f"{digest(source).removeprefix('sha256:')}.json"


def require_private(info: os.stat_result) -> None:
    if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise EvidenceError("The operating evidence is outside Platform's private receipt custody.")


def write_rehearsal(root: Path, source: dict[str, str], state: str, scenarios: dict) -> Path:
    payload = {
        "artifact_type": ARTIFACT_TYPE,
        "source_revisions": source,
        "observed_at": datetime.now(UTC).isoformat(),
        "state": state,
        "scenarios": scenarios,
    }
    ensure_private_directory(root)
    target = root / receipt_name(source)
    write_json_atomic(target, {**payload, "content_digest": digest(payload)})
    return target


def record_rehearsal(root: Path, source: dict[str, str], scenarios: dict) -> Path:
    for case in OBSERVATIONS:
        require_observations(case, scenarios)
    return write_rehearsal(root, source, "completed", scenarios)


def verify_case(root: Path, source: dict[str, str], case: str) -> str:
    try:
        with directory_fd(root) as directory:
            require_private(os.fstat(directory))
            with bounded_file(directory, receipt_name(source), MAX_RECEIPT_BYTES) as (stream, size):
                require_private(os.fstat(stream.fileno()))
                raw = stream.read(MAX_RECEIPT_BYTES + 1)
        if len(raw) != size:
            raise EvidenceError("The rehearsal receipt changed during readback.")
        receipt = json.loads(raw, object_pairs_hook=strict_object, parse_constant=invalid_constant)
    except FileNotFoundError as error:
        raise EvidenceError("Run the isolated rehearsal for these exact source revisions.") from error
    except (OSError, UnicodeError, ValueError) as error:
        if isinstance(error, EvidenceError):
            raise
        raise EvidenceError("The existing rehearsal receipt could not be verified.") from error
    if not isinstance(receipt, dict) or receipt.get("artifact_type") != ARTIFACT_TYPE:
        raise EvidenceError("The file is missing the Platform rehearsal receipt identity.")
    seal = receipt.pop("content_digest", None)
    if seal != digest(receipt):
        raise EvidenceError("The rehearsal receipt has changed since the owner recorded it.")
    if receipt.get("source_revisions") != source:
        raise EvidenceError("The rehearsal receipt belongs to different source revisions.")
    if receipt.get("state") != "completed":
        raise EvidenceError("The exact isolated rehearsal has not completed successfully.")
    scenarios = receipt.get("scenarios")
    if not isinstance(scenarios, dict):
        raise EvidenceError("The rehearsal receipt has no recorded observations.")
    require_observations(case, scenarios)
    return seal


def run_rehearsal(source: dict[str, str], broker: Path) -> Path:
    ensure_private_directory(RECEIPT_ROOT)
    handle = os.open(RECEIPT_ROOT / ".rehearsal.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(handle, "a") as lock:
        require_private(os.fstat(lock.fileno()))
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise EvidenceError("An isolated project runtime rehearsal is already running.") from error
        write_rehearsal(RECEIPT_ROOT, source, "running", {})
        scenarios = {}
        try:
            for name, options in (
                ("paired", {}),
                ("retained_data", {"retained_data": True}),
                ("failed_update", {"failed_update": True}),
                ("capacity", {"capacity": True}),
            ):
                print(f"Running {name.replace('_', ' ')}", flush=True)
                scenarios[name] = exercise(broker, **options)
            require_checkout(REPO_ROOT, source['platform-engineering'], clean=True)
            require_checkout(broker, REVIEWED_BROKER_REVISION, clean=True)
            return record_rehearsal(RECEIPT_ROOT, source, scenarios)
        except (AssertionError, OSError, ValueError, subprocess.SubprocessError):
            write_rehearsal(RECEIPT_ROOT, source, "failed", scenarios)
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    verify = commands.add_parser("verify", help="Read back a named case for the exact reviewed revision.")
    verify.add_argument("case", choices=OBSERVATIONS)
    rehearse = commands.add_parser("rehearse", help="Exercise the paired runtime in disposable namespaces.")
    rehearse.add_argument("--broker-checkout", type=Path, required=True)
    for command in (verify, rehearse):
        command.add_argument("--platform-head", required=True)
    args = parser.parse_args()

    try:
        source = source_identity(args.platform_head, REVIEWED_BROKER_REVISION)
        require_checkout(REPO_ROOT, args.platform_head, clean=args.action == "rehearse")
        if args.action == "verify":
            seal = verify_case(RECEIPT_ROOT, source, args.case)
            print(json.dumps({"case": args.case, "source_revisions": source, "receipt_digest": seal}))
            return 0
        if os.environ.get("OOS_DELIVERY_ART_EVIDENCE_MODE") == "verification-only":
            raise EvidenceError("Run the disposable rehearsal before requesting evidence in the Console.")
        broker = args.broker_checkout.resolve()
        require_checkout(broker, REVIEWED_BROKER_REVISION, clean=True)
        print(run_rehearsal(source, broker))
        return 0
    except (EvidenceError, ActivationError) as error:
        print(f"Project runtime evidence unavailable. {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
