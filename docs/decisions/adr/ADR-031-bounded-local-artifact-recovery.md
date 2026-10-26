# ADR-031: Bounded local artifact integrity recovery

## Status

Operator-approved design; exact Security acceptance required before activation.
Local dev-integration only.

## Context

Known imperfect RAM is accepted. A PostgreSQL executable differed by one bit
from independently verified same-image bytes while compressed layers were valid.
The wider read-only audit found MinIO client and Temporal admin CLI mismatches.
Metadata or two consumers sharing one cache cannot prove unpacked-byte integrity.

## Decision

Extend existing Platform lifecycle, not a new daemon/control plane. A root-owned
helper admits only check, repair and confirm with a finite namespace/repository
policy. No model/browser supplies paths, shell, references or credentials.
Install through existing Windows/WSL administration after exact acceptance;
startup checks installed code/policy hashes and never implicitly installs root
code.

Retain consumed immutable identities. Verify manifest/config/layer SHA256 values,
replay OCI layers without extraction and compare the read-only unpacked file
inventory, hashes, links and modes. Root-protected checksummed baseline caches
optimize checks; mismatches regenerate from verified content. Missing compressed
content may be fetched only from the exact public registry digest via HTTPS,
without ambient registry credentials. Never upgrade tags or activate models.

Hold existing lifecycle and shared/exclusive owner-operation locks. Pending
owner work/Helm compensation defers repair. Plan all consumers and reject
unmanaged/unsupported users before effects. Persist identities/replicas, pause
affected managed controllers and wait. The root helper independently requires
zero CRI users, refreshes exact aliases through native containerd/CRI and verifies
replacement bytes. Never mount writable container layers or persistent volumes.

Persist the repair attempt before destructive effects. Failed/uncertain attempts
are not replayed; safe pre-effect quiescence can continue idempotently. Only
native healthy readback closes an incident. The existing timer uses cheap fault
signals, scans once per ongoing unknown failure and resumes helpers only through
the retained supervisor. No speculative repeating restart loop.

For frontend corruption, stop its managed service, quarantine derived output,
rebuild exact clean accepted source/toolchain without credentials, then verify
native process/artifact readback. Failed/interrupted rebuilds latch. Source work,
databases, accounts, secrets and unsupported host tools have no generic automatic
overwrite permission; their owner procedures remain authoritative.

## Consequences

Startup adds bounded I/O; healthy timer ticks do not hash full images. Each root
invocation is independently bounded to600seconds plus30seconds termination grace.
Existing serving memory/model/security gates remain. Private journals/receipts
retain evidence; existing Platform capability reasons surface recovery blocking.

Software cannot guarantee recovery when RAM corrupts the verifier, replacement
or mutable data, or when the host is unavailable. Disable automatic repair in
reviewed policy and restore accepted source for rollback, preserving evidence
and data. The [primary procedure](../../../products/governance-operations-console/runbooks/operate-complete-runtime.md)
owns commissioning and recovery.
