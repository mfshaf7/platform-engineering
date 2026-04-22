# CI/CD Standard

CI/CD exists to feed the governed release-control model, not to replace it.

Use [governed-release-control-model.md](governed-release-control-model.md) for
the tier model and required release-state objects.

The platform CI/CD contract requires:

- manifest validation on pull requests
- Terraform formatting and validation
- Helm linting
- environment pin visibility during promotion
- drift-check automation on a schedule
- dedicated security posture validation
- documented workflow entrypoints under `docs/workflows/`
- environment-gated manual workflows for stage and prod state changes when
  GitHub environments are configured
- artifact or release metadata strong enough to construct the current tier's
  candidate or deployed contract truth
- verification and readiness reset behavior when the candidate or deployed
  contract changes

Promotion should update environment pins or other Git-managed release objects,
not mutate runtime directly.

Build success does not make a workload stage-ready or prod-ready. The workflow
still needs the matching verification, readiness, and post-promotion evidence
required by the workload's governed release tier.
