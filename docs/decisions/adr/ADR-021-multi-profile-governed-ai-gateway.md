# ADR-021: Multi-Profile Governed AI Gateway

## Status

- Accepted

## Context

ADR-012 established a platform-owned governed AI access plane and logical model
profiles. Its first runtime proof served only the intake classifier, so profile
selection, activation, provider routing, and service readiness were effectively
global.

Work Design is the first additional consumer. It requires a different caller,
typed task contracts, strict input and output schemas, and an activation
decision that must not change intake availability. A single selected profile or
one global activation switch would couple unrelated consumers and make a local
suspension remove the whole gateway from service.

## Decision

The governed AI gateway resolves the complete reviewed profile registry for one
environment and selects a profile at request time.

Each invocation must match one exact:

- profile and independently approved activation state
- caller identity
- caller-owned task kind, contract reference, and version
- input contract and provider output schema
- provider binding and runtime limits

Profiles do not fall back to another profile, task, model, or provider route.
The gateway keeps provider credentials and invocation audit custody; the caller
keeps workflow instructions, operator approval, and canonical mutation
semantics.

Activation and rollback are profile-local. Suspending one profile denies that
profile before provider access without disabling another eligible profile. Pod
readiness is true when at least one profile is independently eligible to serve;
the readiness response reports per-profile and compatibility-profile state.

The existing intake profile remains the compatibility profile for its legacy
response shape and the shared dev-integration smoke. Compatibility does not
grant other profiles activation or task fallback.

## Consequences

### Positive

- one gateway can support multiple bounded consumers without sharing workflow
  authority
- activation, suspension, audit, and runtime limits remain independently
  attributable to each profile
- new consumers can be registered and source-tested before provider access is
  activated
- suspending one profile does not create an outage for unrelated active
  profiles

### Constraints

- every new profile requires an exact caller and typed task contract
- runtime startup must reject malformed registry or binding state
- callers cannot discover or substitute profiles and tasks at request time
- live activation still requires the separate Platform and Security gates
- this decision does not authorize Work Design activation or canonical
  mutation by a model

## Alternatives Considered

- Deploy one gateway runtime per logical profile:
  - Rejected for the current scale because it duplicates provider custody,
    runtime operations, and audit infrastructure without strengthening the
    request boundary.
- Keep one launch-time selected profile:
  - Rejected because switching consumers would couple availability and make
    independent activation impossible.
- Use one generic untyped inference endpoint:
  - Rejected because caller-owned task boundaries and strict evidence would be
    lost.

## Related Artifacts

- [ADR-012-governed-ai-access-plane-and-model-profiles.md](ADR-012-governed-ai-access-plane-and-model-profiles.md)
- [../../components/governed-ai-gateway/architecture.md](../../components/governed-ai-gateway/architecture.md)
- [../../standards/governed-ai-access-model.md](../../standards/governed-ai-access-model.md)
- [../../../security/governed-ai-model-profiles.yaml](../../../security/governed-ai-model-profiles.yaml)
- [../../../security/governed-ai-access-plane.yaml](../../../security/governed-ai-access-plane.yaml)
- [../../../security/governed-ai-runtime-assist-contract.yaml](../../../security/governed-ai-runtime-assist-contract.yaml)
