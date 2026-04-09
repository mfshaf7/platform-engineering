# Bootstrap Vault

## Purpose

This runbook establishes Vault as the cluster secret source of truth and
connects environment-scoped `ExternalSecret` consumers through Kubernetes auth.

## Architecture

- `vault` runs once per cluster as shared infrastructure
- `external-secrets` remains the delivery mechanism into Kubernetes namespaces
- each consuming namespace gets its own namespaced `SecretStore`
- Vault policies and roles are split by environment to preserve least privilege

## Deploy Shared Apps

1. apply [root-shared.yaml](../../argocd/apps/root-shared.yaml)
2. wait for `vault` and `external-secrets` to reconcile in Argo CD
3. initialize and unseal Vault

## Initialize And Unseal

The official Vault Helm chart does not initialize or unseal Vault for you. Use
the recovery keys and root token handling policy that matches your environment.

For this local platform, keep the unseal keys and root token outside the repo.

If the platform is expected to recover automatically after routine restart, do
not stop at manual Shamir unseal. Use
[vault-auto-unseal.md](vault-auto-unseal.md) to move the platform to an
unattended restart model.

## Configure Vault For ESO

After Vault is initialized and unsealed:

```bash
export VAULT_TOKEN='...'
./scripts/bootstrap_vault.sh
```

This script:

- enables the `kv` v2 secrets engine
- enables Kubernetes auth
- configures Kubernetes auth against the in-cluster API
- creates least-privilege policies for each platform-managed consumer namespace
- creates the Vault roles expected by the environment `SecretStore` manifests

After adding a new Vault-backed service such as OpenProject, rerun the same
script so the matching policy and Kubernetes auth role exist before Argo
reconciles the service `SecretStore`.

## Configure Shared Operator Access

To standardize the local operator login across Argo CD and Vault:

```bash
export VAULT_TOKEN='...'
export OPERATOR_USERNAME='<operator-username>'
export OPERATOR_PASSWORD='<fresh-operator-password>'
./scripts/bootstrap_operator_access.sh
```

This script:

- enables Vault `userpass` auth if needed
- creates or updates the `platform-admin` Vault policy
- creates or updates the Vault user for the operator login
- creates or updates the Argo CD local account and admin RBAC grant
- rotates the Argo CD account password hash in `argocd-secret`
- restarts the Argo CD control-plane pods so the account change is active

## Migrate Existing Gateway Secrets

If the gateway secrets already exist in Kubernetes, migrate them into Vault:

```bash
export VAULT_TOKEN='...'
python3 scripts/migrate_k8s_secret_to_vault.py \
  --namespace openclaw-stage \
  --secret-name openclaw-gateway-secrets \
  --vault-path products/openclaw/stage/gateway

python3 scripts/migrate_k8s_secret_to_vault.py \
  --namespace openclaw \
  --secret-name openclaw-gateway-secrets \
  --vault-path products/openclaw/prod/gateway
```

## Reconcile Environment Secret Apps

The environment roots apply:

- [environments/stage/secrets](../../environments/stage/secrets)
- [environments/prod/secrets](../../environments/prod/secrets)
- [environments/prod/openproject-secrets](../../environments/prod/openproject-secrets)
- [environments/prod/platform-postgresql-secrets](../../environments/prod/platform-postgresql-secrets)

Each consuming namespace owns:

- a dedicated `ServiceAccount`
- a dedicated Vault-backed `SecretStore`
- the `ExternalSecret` objects that materialize the runtime secrets needed in
  that namespace

The shared control-plane resources are platform-named:

- `platform-root-shared`
- `platform-core`
- `platform-vault`
- `platform-secrets-stage`
- `platform-secrets-prod`

## Outcome

After reconciliation:

- Vault is the source of truth
- ESO syncs runtime secrets into Kubernetes
- gateway pods continue to consume `openclaw-gateway-secrets`
- rotation no longer depends on manual namespace-to-namespace secret copying
