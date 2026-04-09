# Secrets And Config

## Secret Expectations

V1 requires two operator-managed secret inputs outside Git for the OpenProject
namespace:

- Vault path: `kv/products/openproject/prod/admin`
  required key: `password`
  synced secret: `openproject-admin-secret`
  synced key: `password`
- Vault path: `kv/platform/postgresql/prod/openproject`
  required key: `password`
  synced secret: `openproject-postgresql-credentials`
  synced key: `password`

The `openproject` namespace reads those paths through Vault Kubernetes auth role
`platform-openproject-prod-secrets`.

## Shared Database Secret Input

The standalone PostgreSQL service also expects:

- Vault path: `kv/platform/postgresql/prod/service`
- required key: `postgres_password`

That value is consumed only in namespace `platform-postgresql`.

## Chart-Generated Secrets

The OpenProject chart may still generate in-cluster secrets for bundled
Memcached or internal rails runtime values. The database credentials are not
left to generated defaults in v1 because the service now consumes a standalone
platform PostgreSQL instance.

## Non-Secret Config

V1 keeps config intentionally small:

- fixed NodePort access on `32083`
- `develop: true` for local-cluster friendliness
- `ingress.enabled: false`
- `openproject.https: false`
- `openproject.hsts: false`
- `postgresql.bundled: false`
- database host `platform-postgresql.platform-postgresql.svc.cluster.local`
- persistence forced to `ReadWriteOnce` on `local-path`

## Deferred Config

- SMTP / incoming email
- object storage
- OIDC / SSO
- ingress annotations
