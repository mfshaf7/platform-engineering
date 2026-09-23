# Prototype Closure Identity

Platform owns the dedicated GitHub App identity and local runtime projection
used by Prototype Closure. The
[identity definition](../../../security/prototype-closure-identity.yaml) binds
one selected repository, short-lived installation tokens, exact Closure branch
and write paths, the approved Security review, and the reviewed OOS and WGCF
source revisions.

The identity is separate from Prototype Landing, Prototype Maturity, and Agent
Gary. It cannot merge, write directly to `main`, administer repositories,
create or delete repositories, write a durable owner repository, or use
personal or ambient credentials.

## Operator Command

Use the single Platform command family:

```sh
make prototype-closure-identity ACTION=validate
make prototype-closure-identity ACTION=commission ARGS="<identity arguments>"
make prototype-closure-identity ACTION=deliver ARGS="<identity and runtime arguments>"
make prototype-closure-identity ACTION=suspend ARGS="<identity and runtime arguments>"
make prototype-closure-identity ACTION=revoke ARGS="<identity, runtime, and rollback arguments>"
```

`commission` verifies the exact App, installation, selected repository,
permissions, and provider boundary, then revokes its proof token.

`deliver` requires the active `accepted-idea-delivery` and Governance
Control Fabric session manifests. It projects one short-lived Closure token to
OOS, enables the exact WGCF readiness path, initializes the persistent
Platform evidence ledger, and projects WGCF's dedicated OOS readback credential
from `--oos-reader-secret-file`. The credential file is produced by the OOS
profile and must remain mode `0600`; its value is never written to a receipt.

`suspend` blocks new Closure requests in OOS and WGCF while preserving
credentials, state, evidence, and source history for bounded recovery.
`revoke` revokes the active installation token and removes only the Closure
OOS and WGCF projections. It preserves Landing, Maturity, Studio history,
durable-owner source, and the local Platform evidence ledger.

## Runtime Evidence

Use `make prototype-closure-evidence` to record owner evidence after the
corresponding Platform runtime inspection or cleanup has actually completed:

```sh
make prototype-closure-evidence ACTION=record-owner-evidence \
  EVIDENCE_FILE="<session-state>/prototype-closure/state/platform-evidence.json" \
  ARGS="--field runtime_disposition_proof_ref --prototype-id <id> --subject-ref <plan-ref> --source-revision <sha>"

make prototype-closure-evidence ACTION=record-post-merge-disposition \
  EVIDENCE_FILE="<session-state>/prototype-closure/state/platform-evidence.json" \
  ARGS="--prototype-id <id> --merged-source-revision <sha> --disposition <revoked|absent>"
```

The recorder validates the `0600` owner file, serializes concurrent writes,
replaces only the exact current record selector, and emits a content-addressed
secret-free result. It does not inspect or clean runtime resources by itself;
the operator must record only the disposition established by the corresponding
Platform action.

## Availability Boundary

Security review #1140 permits this bounded local activation sequence. Platform
work item #1107 owns commissioning and rollback evidence. Commissioning does
not establish normal availability: Console work item #1151 must still exercise
all four Closure actions through the configured owner-backed path.
