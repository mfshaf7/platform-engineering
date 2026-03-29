# CI/CD Standard

The platform CI/CD contract requires:

- manifest validation on pull requests
- Terraform formatting and validation
- Helm linting
- environment pin visibility during promotion
- drift-check automation on a schedule
- dedicated security posture validation

Promotion should update environment pins, not mutate runtime directly.
