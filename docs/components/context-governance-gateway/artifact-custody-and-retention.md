# Context Governance Gateway Artifact Custody And Retention

## Purpose

Define the platform controls required before CGG can preserve raw operational
context in a shared metadata or artifact store.

This document does not approve shared custody. It defines the gate that must be
satisfied first.

## Current Custody State

- raw artifact store: local dev-integration MinIO/PVC-backed custody only
  after workspace lifecycle activation
- redacted artifact store: local dev-integration MinIO/PVC-backed custody only
  after workspace lifecycle activation
- metadata store: local dev-integration PostgreSQL and PVC-backed CGG state
  only after workspace lifecycle activation
- backup: not approved for governed stage or production
- restore: not approved for governed stage or production
- retention deletion: not approved for governed stage or production
- legal hold: not approved for governed stage or production
- debug override: not approved for governed stage or production
- tamper-evident ledger: local source and local dev-integration evidence only

Approved custody today is limited to owner-repo local CLI/source behavior and
the active local dev-integration profile. Neither is governed stage or
production custody.

## Required Storage Model

Before governed shared custody is approved, the platform must define:

- storage class and namespace
- raw artifact bucket or equivalent storage boundary
- redacted artifact bucket or equivalent storage boundary
- metadata schema owner
- encryption at rest
- secret delivery path
- access control by artifact class
- backup schedule
- restore test cadence
- deletion procedure
- retention policy
- incident or legal hold behavior
- audit and ledger preservation after deletion

Raw and redacted artifacts must be logically separated. Operator-facing
receipts, packets, release records, and support evidence must reference raw
artifacts by digest and location metadata instead of embedding raw bodies.
This applies to local dev-integration evidence as well as future governed
stage or production custody.

## Retention Classes

The first platform custody implementation must define retention classes for:

- raw artifacts
- redacted artifacts
- manifests
- model-safe packets
- operator receipts
- ledger events
- debug override records
- deletion records

Each class must define default retention, maximum retention, deletion trigger,
approval role, and metadata retained after deletion.

## Backup And Restore Gate

Backup is not approved until the platform proves:

- what data is backed up
- where backups are stored
- who can restore them
- how restore is tested
- how deleted raw artifacts stay deleted after restore unless legal hold
  explicitly overrides deletion
- how ledger integrity is preserved across restore

Restore evidence must be operator-reviewable and must not paste raw artifact
bodies into change records or tickets.

## Debug Override Gate

Debug override is exceptional access. Before it is implemented, the platform
must require:

- operator identity
- caller identity
- artifact digest
- reason
- approved scope
- expiry
- reviewer or approval reference when required
- fields that remain denied or suppressed
- ledger event id

Debug override must not become a raw model-projection mode.

## Denied Patterns

Do not:

- store raw artifacts in PostgreSQL rows by default
- place raw artifacts in platform logs or release records
- use object storage without retention and deletion policy
- restore deleted raw artifacts silently
- allow dashboard browsing of raw artifacts by default
- let packet consumers fetch raw artifacts without separate authorization
- treat scanner results as a substitute for context-admission policy
