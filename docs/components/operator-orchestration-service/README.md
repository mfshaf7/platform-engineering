# Operator Orchestration Service

## Purpose

`operator-orchestration-service` is the shared internal workflow broker and
aggregate orchestrator for bounded operator requests and admitted durable
workflows.

It owns workflow definitions, run control, correlation, aggregate projections,
and final orchestration receipts. Temporal is a proposed replaceable runtime
adapter behind OOS; it is not part of the current live footprint.

## Start Here

- [architecture.md](architecture.md)
- [access.md](access.md)
- [operations.md](operations.md)
- [release-governance.md](release-governance.md)
- [repository-provider-identity.md](repository-provider-identity.md)
- [repository-provisioning-identity.md](repository-provisioning-identity.md)

## Current Live Footprint

- namespace: `operator-orchestration-service`
- Argo application: `operator-orchestration-service`
- direct operator UI: none
- Temporal runtime binding: none
