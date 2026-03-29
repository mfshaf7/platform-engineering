# Threat Model

## Primary Risks

- supply-chain drift between source, artifact, and runtime
- secret leakage through repo or ad hoc runtime edits
- unauthorized live patching
- runtime health regressions without operator visibility
- host-control privilege misuse across the bridge boundary

## Required Controls

- version pinning
- artifact provenance
- runtime attestation
- secret-store-backed delivery
- observability and alerting
- governed hotfix workflow
