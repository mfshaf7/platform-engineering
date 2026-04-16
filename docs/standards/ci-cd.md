# CI/CD Standard

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

Promotion should update environment pins, not mutate runtime directly.
