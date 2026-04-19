# ADR-012: Governed AI Access Plane And Model Profiles

## Status

- Accepted

## Context

The workspace now has an intake model that can classify new repos, products,
and components before they quietly drift into the governed system.

The next step is allowing bounded AI assistance for that intake decision.

That raises a platform question: how do we tell whether a model used for intake
assistance is governed?

A raw upstream model name is not enough. The same upstream model could be:

- used through an approved internal policy path
- or called directly with a local API key from an unmanaged script

Those are not equivalent from a security or governance perspective.

The platform therefore needs a reusable control model that defines governed AI
by approved profile plus invocation path, not by vendor label alone.

## Decision

Adopt a platform-owned governed AI access model.

`platform-engineering` now owns:

- the shared standard in
  `docs/standards/governed-ai-access-model.md`
- the approved model-profile registry in
  `security/governed-ai-model-profiles.yaml`
- validation of that registry through
  `scripts/validate_ai_model_profiles.py`

The initial approved profile set includes a reserved intake-assist profile:

- `intake-classifier-v1`

That profile is intentionally recorded as `suspended`, not `active`, until the
real governed AI gateway, caller identity path, audit emission, and
direct-provider egress block exist.

`workspace-governance` may only accept `ai-suggested` intake entries when they
reference an `active` approved profile whose purpose is
`workspace-intake-assist`.

## Consequences

### Positive

- the platform now has a concrete definition of governed AI that does not rely
  on raw model names
- owner repos can consume approved profiles without inventing repo-local AI
  governance logic
- the workspace intake layer can distinguish operator AI suggestions that are
  governed from suggestions that are only conversational or ad hoc

### Constraints

- this ADR does not by itself deploy the live AI gateway
- the current intake profile must remain non-active until the real invocation
  path exists
- operator exception use of external AI tools remains explicitly outside the
  governed path

## Alternatives Considered

- Treat a raw model name as evidence of governed status
  - Rejected because the control posture depends on the invocation path and
    policy plane, not just the upstream model label.
- Let each repo decide locally which model counts as governed
  - Rejected because that creates governance drift and weakens auditability.

## Related Artifacts

- [../../../docs/standards/governed-ai-access-model.md](../../../docs/standards/governed-ai-access-model.md)
- [../../../security/governed-ai-model-profiles.yaml](../../../security/governed-ai-model-profiles.yaml)
- [security-architecture/docs/standards/ai-security-and-governance.md](https://github.com/mfshaf7/security-architecture/blob/main/docs/standards/ai-security-and-governance.md)
