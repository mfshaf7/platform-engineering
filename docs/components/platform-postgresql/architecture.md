# Platform PostgreSQL Architecture

## Role

`platform-postgresql` is the shared PostgreSQL service for platform-managed
products.

It is a shared dependency, not a product in itself.

## Current Live Shape

- namespace: `platform-postgresql`
- Argo applications:
  - `platform-postgresql`
  - `platform-postgresql-secrets`
- primary service:
  - `platform-postgresql.platform-postgresql.svc.cluster.local:5432`

Current known consumer:

- OpenProject

## Model

This component exists so products can use a platform-managed database without
embedding database lifecycle into each product directory.

## Read With

- [../../architecture/current-platform-topology.md](../../architecture/current-platform-topology.md)
- [../../standards/secrets.md](../../standards/secrets.md)
- [../../../products/openproject/dependencies.md](../../../products/openproject/dependencies.md)
