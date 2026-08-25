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

## Non-Runtime Automation Secret

The future broker credential for OpenProject does not belong in the OpenProject
runtime secret tree because it is not consumed by the `openproject` namespace.

- Vault path: `kv/components/operator-orchestration-service/prod/openproject`
- expected key: `apiToken`

This secret is owned by the `operator-orchestration-service` component and
should only be delivered to that component's runtime once it is admitted and
deployed.

## Dev-Integration Catalog Control Secret

The Delivery Refinement runtime composition generates one operator-private
shared secret for the bounded Catalog adapter. The composition projects it as:

- `OPENPROJECT_CATALOG_CONTROL_SHARED_SECRET` in the dev-integration
  OpenProject runtime
- the matching OOS Catalog client token in the OOS runtime

The value is not stored in Git, OpenProject settings, or redacted composition
state. The platform-integrated production OpenProject secret contract is not
changed by this dev-integration binding.

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
