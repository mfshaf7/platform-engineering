# Dependencies

## Upstream Package Inputs

- official OpenProject Helm chart from `https://charts.openproject.org`
- pinned chart version `13.4.4`
- upstream application version `17.2.3`
- standalone PostgreSQL chart from `https://charts.bitnami.com/bitnami`
- pinned PostgreSQL chart version `18.5.16`
- PostgreSQL application version `18.3.0`

## Cluster Dependencies

- Argo CD for reconciliation
- External Secrets Operator for admin-password delivery
- Vault secret paths for the initial admin password and database credentials
- single-node `k3s` storage through the `local-path` storage class

## Bundled Runtime Dependencies

V1 uses only one bundled dependency from the chart:

- Memcached

The application database is provided by a separate platform-managed PostgreSQL
service in namespace `platform-postgresql`.

## Runtime Data Paths

- OpenProject shared assets volume mounted at `/var/openproject/assets`
- standalone PostgreSQL persistent data volume created by the Bitnami chart in
  namespace `platform-postgresql`

## Access Dependency

- Windows localhost access depends on the existing platform-managed NodePort
  forwarding path owned by `PlatformCoreHostStack`
