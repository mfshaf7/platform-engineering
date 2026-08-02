from __future__ import annotations

import argparse
import fcntl
import json
import os
import stat
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .authority import (
    ContractSet,
    OWNER_RUNTIME_IMAGES,
    GitSourceResolver,
    LocalBaselineProbe,
    authorization_storage_key,
    assemble_claims,
    capture_baseline,
    claim_execution,
    consumption_receipt_path,
    issue_permit,
    load_contracts,
    prepare_claims,
    validate_authorization,
)
from .execution import ControlledProofExecutor, project_owner_contexts
from .model import (
    ControlledProofError,
    create_json_exclusive,
    read_bounded_json,
    read_bounded_json_with_digest,
)
from .runtime import (
    ControlledRuntimeDriver,
    LocalK3sRuntimeControl,
    RuntimeArtifactBindings,
    validate_runtime_action_binding,
)

DEFAULT_WORKSPACE_ROOT = Path(__file__).resolve().parents[5]


def _path(value: str) -> Path:
    # Preserve the final path component so read_bounded_json can reject symlinks.
    return Path(value).expanduser().absolute()


def _workspace_root(value: str) -> Path:
    root = _path(value).resolve()
    if not root.is_dir():
        raise ControlledProofError(f"workspace root is unavailable: {root}")
    return root


def _canonical_execution_output_root(
    workspace_root: Path,
    authorization: dict[str, object],
) -> Path:
    session = authorization.get("commissioning_session")
    if not isinstance(session, dict):
        raise ControlledProofError("authorization commissioning session is unavailable")
    session_id = session.get("commissioning_session_id")
    if not isinstance(session_id, str) or not session_id:
        raise ControlledProofError("authorization commissioning session id is unavailable")
    return (
        workspace_root
        / "platform-engineering"
        / ".platform-drills"
        / "temporal-component-commissioning-proof"
        / session_id
        / "controlled-proof-output"
    ).absolute()


def _validate_execution_output_root(
    workspace_root: Path,
    authorization: dict[str, object],
    output_root: Path,
) -> None:
    if output_root != _canonical_execution_output_root(workspace_root, authorization):
        raise ControlledProofError(
            "controlled proof output root must equal the canonical Platform run output"
        )


@contextmanager
def _execution_lock(
    platform_root: Path,
    authorization_id: str,
) -> Iterator[None]:
    lock_root = (
        platform_root / ".platform-drills" / "_controlled-proof-execution-locks"
    )
    if lock_root.is_symlink():
        raise ControlledProofError(
            "controlled proof execution lock root must not be a symlink"
        )
    lock_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root_stat = lock_root.stat()
    if (
        not stat.S_ISDIR(root_stat.st_mode)
        or root_stat.st_uid != os.geteuid()
        or root_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
    ):
        raise ControlledProofError(
            "controlled proof execution lock root must be private and operator-owned"
        )
    lock_path = lock_root / f"{authorization_storage_key(authorization_id)}.lock"
    try:
        descriptor = os.open(
            lock_path,
            os.O_RDWR
            | os.O_CREAT
            | os.O_CLOEXEC
            | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
    except OSError as exc:
        raise ControlledProofError(
            "controlled proof execution lock is unavailable"
        ) from exc
    try:
        lock_stat = os.fstat(descriptor)
        if (
            not stat.S_ISREG(lock_stat.st_mode)
            or lock_stat.st_uid != os.geteuid()
            or lock_stat.st_mode & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise ControlledProofError(
                "controlled proof execution lock must be private and operator-owned"
            )
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ControlledProofError(
                "controlled proof execution is already active for this authorization"
            ) from exc
        yield
    finally:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def _add_workspace(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--workspace-root",
        default=str(DEFAULT_WORKSPACE_ROOT),
        help="workspace root containing every permit-bound owner repo",
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Permit-bound Temporal component commissioning controls."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    baseline = subparsers.add_parser("capture-baseline")
    _add_workspace(baseline)
    baseline.add_argument("--baseline-id", required=True)
    baseline.add_argument("--operator", required=True)
    baseline.add_argument("--output", required=True)
    baseline.add_argument("--evidence-root", required=True)

    build_claims = subparsers.add_parser("build-claims")
    _add_workspace(build_claims)
    build_claims.add_argument("--authorization-id", required=True)
    build_claims.add_argument("--session-id", required=True)
    build_claims.add_argument("--review-packet-ref", required=True)
    build_claims.add_argument("--issued-at", required=True)
    build_claims.add_argument("--expires-at", required=True)
    build_claims.add_argument("--baseline", required=True)
    build_claims.add_argument("--baseline-evidence-root", required=True)
    build_claims.add_argument("--oos-api-image-digest", required=True)
    build_claims.add_argument("--oos-worker-image-digest", required=True)
    build_claims.add_argument("--wgcf-worker-image-digest", required=True)
    build_claims.add_argument("--output", required=True)

    claims = subparsers.add_parser("validate-claims")
    claims.add_argument("--claims", required=True)

    issue = subparsers.add_parser("issue-permit")
    _add_workspace(issue)
    issue.add_argument("--claims", required=True)
    issue.add_argument("--operator-approval", required=True)
    issue.add_argument("--security-authorization", required=True)
    issue.add_argument("--baseline", required=True)
    issue.add_argument("--baseline-evidence-root", required=True)
    issue.add_argument("--output", required=True)

    execute = subparsers.add_parser("execute")
    _add_workspace(execute)
    execute.add_argument("--authorization", required=True)
    execute.add_argument("--authorization-digest", required=True)
    execute.add_argument("--operator-approval", required=True)
    execute.add_argument("--security-authorization", required=True)
    execute.add_argument("--baseline", required=True)
    execute.add_argument("--baseline-evidence-root", required=True)
    execute.add_argument("--consumption-receipt", required=True)
    execute.add_argument("--consumption-receipt-digest", required=True)
    execute.add_argument("--output-root", required=True)

    runtime_action = subparsers.add_parser("verify-runtime-action")
    _add_workspace(runtime_action)
    runtime_action.add_argument("--action", required=True)
    runtime_action.add_argument("--authorization", required=True)
    runtime_action.add_argument("--authorization-digest", required=True)
    runtime_action.add_argument("--operator-approval", required=True)
    runtime_action.add_argument("--security-authorization", required=True)
    runtime_action.add_argument("--baseline", required=True)
    runtime_action.add_argument("--baseline-evidence-root", required=True)
    runtime_action.add_argument("--consumption-receipt", required=True)
    runtime_action.add_argument("--consumption-receipt-digest", required=True)
    runtime_action.add_argument("--execution-claim", required=True)
    runtime_action.add_argument("--execution-claim-digest", required=True)
    runtime_action.add_argument("--output-root", required=True)
    runtime_action.add_argument("--kubernetes-namespace", required=True)
    runtime_action.add_argument("--temporal-namespace", required=True)
    runtime_action.add_argument("--state-root", required=True)
    runtime_action.add_argument("--operator-scope", required=True)

    return parser.parse_args(argv)


def capture_baseline_command(args: argparse.Namespace) -> int:
    workspace_root = _workspace_root(args.workspace_root)
    contracts = load_contracts()
    baseline, digest = capture_baseline(
        baseline_id=args.baseline_id,
        operator_id=args.operator,
        output_path=_path(args.output),
        evidence_root=_path(args.evidence_root),
        source_resolver=GitSourceResolver(workspace_root),
        probe=LocalBaselineProbe(workspace_root, args.operator),
        contracts=contracts,
    )
    print(
        json.dumps(
            {
                "baseline_id": baseline["baseline_id"],
                "baseline_path": str(_path(args.output)),
                "baseline_digest": digest,
                "evidence_root": str(_path(args.evidence_root)),
            },
            indent=2,
        )
    )
    return 0


def validate_claims_command(args: argparse.Namespace) -> int:
    claims = read_bounded_json(_path(args.claims))
    _, digest = prepare_claims(claims, contracts=load_contracts())
    print(
        json.dumps(
            {
                "authorization_id": claims["authorization_id"],
                "canonicalization": "rfc8785",
                "canonical_claims_digest": digest,
            },
            indent=2,
        )
    )
    return 0


def build_claims_command(args: argparse.Namespace) -> int:
    workspace_root = _workspace_root(args.workspace_root)
    baseline_path = _path(args.baseline)
    baseline, baseline_digest = read_bounded_json_with_digest(baseline_path)
    owner_image_digests = {
        "ghcr.io/mfshaf7/operator-orchestration-service": (
            args.oos_api_image_digest
        ),
        "ghcr.io/mfshaf7/operator-orchestration-service-worker": (
            args.oos_worker_image_digest
        ),
        "ghcr.io/mfshaf7/workspace-governance-control-fabric-worker": (
            args.wgcf_worker_image_digest
        ),
    }
    if set(owner_image_digests) != OWNER_RUNTIME_IMAGES:
        raise ControlledProofError("controlled proof owner image mapping is invalid")
    claims, claims_digest = assemble_claims(
        authorization_id=args.authorization_id,
        commissioning_session_id=args.session_id,
        review_packet_ref=args.review_packet_ref,
        issued_at=args.issued_at,
        expires_at=args.expires_at,
        baseline=baseline,
        baseline_digest=baseline_digest,
        baseline_evidence_root=_path(args.baseline_evidence_root),
        owner_image_digests=owner_image_digests,
        source_resolver=GitSourceResolver(workspace_root),
        contracts=load_contracts(),
    )
    output = _path(args.output)
    claims_file_digest = create_json_exclusive(output, claims)
    print(
        json.dumps(
            {
                "authorization_id": claims["authorization_id"],
                "claims_path": str(output),
                "claims_file_digest": claims_file_digest,
                "canonical_claims_digest": claims_digest,
            },
            indent=2,
        )
    )
    return 0


def issue_permit_command(args: argparse.Namespace) -> int:
    workspace_root = _workspace_root(args.workspace_root)
    contracts = load_contracts()
    permit = issue_permit(
        claims=read_bounded_json(_path(args.claims)),
        operator_approval_path=_path(args.operator_approval),
        security_approval_path=_path(args.security_authorization),
        baseline_path=_path(args.baseline),
        baseline_evidence_root=_path(args.baseline_evidence_root),
        source_resolver=GitSourceResolver(workspace_root),
        contracts=contracts,
    )
    output = _path(args.output)
    digest = create_json_exclusive(output, permit)
    print(
        json.dumps(
            {
                "authorization_id": permit["authorization_id"],
                "authorization_path": str(output),
                "authorization_digest": digest,
            },
            indent=2,
        )
    )
    return 0


def execute_command(args: argparse.Namespace) -> int:
    workspace_root = _workspace_root(args.workspace_root)
    contracts = load_contracts()
    authorization_path = _path(args.authorization)
    authorization = read_bounded_json(
        authorization_path,
        expected_digest=args.authorization_digest,
    )
    validate_authorization(
        authorization,
        contracts=contracts,
        baseline_path=_path(args.baseline),
        baseline_evidence_root=_path(args.baseline_evidence_root),
        source_resolver=GitSourceResolver(workspace_root),
        operator_approval_path=_path(args.operator_approval),
        security_approval_path=_path(args.security_authorization),
    )
    baseline = read_bounded_json(
        _path(args.baseline),
        expected_digest=authorization["baseline_and_restore"][
            "baseline_snapshot_digest"
        ],
    )
    receipt = read_bounded_json(
        _path(args.consumption_receipt),
        expected_digest=args.consumption_receipt_digest,
    )
    platform_root = workspace_root / "platform-engineering"
    with _execution_lock(platform_root, authorization["authorization_id"]):
        return _execute_authorized_command(
            args=args,
            workspace_root=workspace_root,
            platform_root=platform_root,
            contracts=contracts,
            authorization_path=authorization_path,
            authorization=authorization,
            baseline=baseline,
            receipt=receipt,
        )


def _execute_authorized_command(
    *,
    args: argparse.Namespace,
    workspace_root: Path,
    platform_root: Path,
    contracts: ContractSet,
    authorization_path: Path,
    authorization: dict[str, Any],
    baseline: dict[str, Any],
    receipt: dict[str, Any],
) -> int:
    output_root = _path(args.output_root)
    _validate_execution_output_root(
        workspace_root,
        authorization,
        output_root,
    )
    if output_root.is_symlink():
        raise ControlledProofError("controlled proof output root must not be a symlink")
    consumption_root = (
        platform_root / ".platform-drills" / "_controlled-proof-consumptions"
    )
    expected_receipt_path = consumption_receipt_path(
        authorization["authorization_id"], consumption_root
    )
    if _path(args.consumption_receipt) != expected_receipt_path:
        raise ControlledProofError(
            "execution requires the canonical Platform consumption receipt"
        )
    contexts = project_owner_contexts(
        authorization=authorization,
        authorization_digest=args.authorization_digest,
        consumption_receipt=receipt,
        consumption_receipt_digest=args.consumption_receipt_digest,
        baseline=baseline,
        output_root=output_root / "owner-contexts",
        contracts=contracts,
    )
    execution_claim, execution_claim_path, execution_claim_digest = claim_execution(
        authorization=authorization,
        authorization_digest=args.authorization_digest,
        consumption_receipt=receipt,
        consumption_receipt_digest=args.consumption_receipt_digest,
        output_root=output_root,
        operator_id=baseline["operator_id"],
        execution_root=(
            platform_root / ".platform-drills" / "_controlled-proof-executions"
        ),
        contracts=contracts,
    )
    control = LocalK3sRuntimeControl(
        authorization=authorization,
        baseline=baseline,
        contexts=contexts,
        artifacts=RuntimeArtifactBindings(
            authorization_path=authorization_path,
            authorization_digest=args.authorization_digest,
            operator_approval_path=_path(args.operator_approval),
            security_approval_path=_path(args.security_authorization),
            baseline_path=_path(args.baseline),
            baseline_evidence_root=_path(args.baseline_evidence_root),
            consumption_receipt_path=_path(args.consumption_receipt),
            consumption_receipt_digest=args.consumption_receipt_digest,
            execution_claim_path=execution_claim_path,
            execution_claim_digest=execution_claim_digest,
        ),
        output_root=output_root,
        workspace_root=workspace_root,
    )
    driver = ControlledRuntimeDriver(
        authorization=authorization,
        authorization_digest=args.authorization_digest,
        contracts=contracts,
        control=control,
        output_root=output_root,
    )
    result, result_digest = ControlledProofExecutor(
        authorization=authorization,
        authorization_digest=args.authorization_digest,
        consumption_receipt=receipt,
        consumption_receipt_digest=args.consumption_receipt_digest,
        execution_claim=execution_claim,
        execution_claim_digest=execution_claim_digest,
        baseline=baseline,
        contexts=contexts,
        contracts=contracts,
        driver=driver,
        output_root=output_root,
    ).run()
    print(
        json.dumps(
            {
                "result_id": result["result_id"],
                "result_path": str(output_root / "controlled-proof-result.json"),
                "result_digest": result_digest,
                "outcome": result["outcome"],
                "execution_claim_path": str(execution_claim_path),
                "execution_claim_digest": execution_claim_digest,
            },
            indent=2,
        )
    )
    return 0


def verify_runtime_action_command(args: argparse.Namespace) -> int:
    validate_runtime_action_binding(
        action=args.action,
        workspace_root=_workspace_root(args.workspace_root),
        bindings=RuntimeArtifactBindings(
            authorization_path=_path(args.authorization),
            authorization_digest=args.authorization_digest,
            operator_approval_path=_path(args.operator_approval),
            security_approval_path=_path(args.security_authorization),
            baseline_path=_path(args.baseline),
            baseline_evidence_root=_path(args.baseline_evidence_root),
            consumption_receipt_path=_path(args.consumption_receipt),
            consumption_receipt_digest=args.consumption_receipt_digest,
            execution_claim_path=_path(args.execution_claim),
            execution_claim_digest=args.execution_claim_digest,
        ),
        output_root=_path(args.output_root),
        kubernetes_namespace=args.kubernetes_namespace,
        temporal_namespace=args.temporal_namespace,
        state_root=_path(args.state_root),
        operator_scope=args.operator_scope,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    commands = {
        "capture-baseline": capture_baseline_command,
        "build-claims": build_claims_command,
        "validate-claims": validate_claims_command,
        "issue-permit": issue_permit_command,
        "execute": execute_command,
        "verify-runtime-action": verify_runtime_action_command,
    }
    try:
        return commands[args.command](args)
    except ControlledProofError as exc:
        print(f"controlled proof denied: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
