# Identity And Access

## Required IAM Layers

- GitHub repository and environment protections
- GHCR publish and pull permissions
- Argo CD RBAC
- Kubernetes RBAC and namespace boundaries
- host-side administrative boundaries for WSL and Windows bootstrap

## Principle

Every automation path should run with the least privilege required for its scope.
