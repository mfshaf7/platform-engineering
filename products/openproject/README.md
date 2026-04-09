# OpenProject Product Integration

This directory captures the platform-specific integration contract for
OpenProject Community Edition on the local `k3s` cluster.

OpenProject is treated here as an internal supporting service:

- deployed and reconciled by Argo CD
- packaged through the official upstream Helm chart
- backed by a standalone platform-managed PostgreSQL service plus local app storage
- exposed through the existing Windows localhost-friendly operator access model

This directory does not duplicate upstream OpenProject application source.
