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
- [repository-lifecycle-identity.md](repository-lifecycle-identity.md)
- [workspace-intake-identity.md](workspace-intake-identity.md) - reviewed activation, delivery, and revocation procedure
- [prototype-landing-identity.md](prototype-landing-identity.md) - bounded Prototype Studio source identity and projection procedure
- [prototype-maturity-identity.md](prototype-maturity-identity.md) - bounded active `dev-integration` identity and projection procedure for candidate and baseline source transitions
- [agent-source-identity.md](agent-source-identity.md) - Platform custody and exact-repository runtime projection for Agent source implementation

## Current Live Footprint

- namespace: `operator-orchestration-service`
- Argo application: `operator-orchestration-service`
- direct operator UI: none
- Temporal runtime binding: none
- local `dev-integration`: Prototype Maturity is active only in the operator-scoped `accepted-idea-delivery` and `governance-control-fabric` sessions; stage and production remain unauthorized
