# Runtime Contract

Document the runtime guarantees the product must expose through the platform.

Suggested sections:

- current runtime profile
  - primary deployment replica count
  - background worker replica count when applicable
  - explicit single-host scaling exemption reference when any runtime surface
    exceeds `1`
- health endpoints
- metrics
- version metadata
- secret dependencies
- network or ingress expectations
- host-integration expectations
