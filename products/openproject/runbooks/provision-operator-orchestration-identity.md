# Provision Operator-Orchestration OpenProject Identity

## Purpose

Provision the dedicated OpenProject service identity and single-purpose API
token for `operator-orchestration-service`.

This converges:

- OpenProject user `operator-orchestration-service`
- project membership on `workspace-proposals`
- project roles:
  - `Reader`
  - `Work package creator`
  - `Work package editor`
  - `Work package structure editor`
- named API token:
  - `openproject-workspace-proposals-v1`
- Vault secret path:
  - `kv/components/operator-orchestration-service/prod/openproject`

## Preconditions

- OpenProject rollout is healthy
- the canonical `workspace-proposals` backlog model already exists
- `VAULT_TOKEN` is set for a token that can write the target Vault path

Additional precondition for delivery-plane access:

- the canonical `workspace-delivery-art` project already exists

## Command

For the current proposal backlog only:

```bash
export VAULT_TOKEN='...'
make openproject-provision-operator-orchestration-identity
```

For the accepted-idea delivery baseline:

```bash
export VAULT_TOKEN='...'
make openproject-provision-operator-orchestration-delivery-access
```

## Optional Rotation

To rotate the broker API token and overwrite the Vault value:

```bash
export VAULT_TOKEN='...'
OPENPROJECT_ROTATE_API_TOKEN=true \
  make openproject-provision-operator-orchestration-identity
```

## Expected Outcome

- the OpenProject user exists and remains non-admin
- the user is a member of `workspace-proposals`
- the user has only:
  - `Reader`
  - `Work package creator`
  - `Work package editor`
  - `Work package structure editor`
- Vault path `kv/components/operator-orchestration-service/prod/openproject`
  contains key `apiToken`

When the delivery-access target is used:

- the user is also a member of `workspace-delivery-art`

## Verification

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "user = User.find_by!(login: \"operator-orchestration-service\"); projects = Project.where(identifier: [\"workspace-proposals\", \"workspace-delivery-art\"]).order(:identifier).map { |project| member = Member.find_by(project: project, principal: user); {identifier: project.identifier, roles: member&.roles&.order(:name)&.pluck(:name) || []} }; puts({login: user.login, admin: user.admin, projects: projects, tokens: user.api_tokens.where(token_name: \"openproject-workspace-proposals-v1\").count}.to_json)"'
```

```bash
k3s kubectl -n vault exec vault-0 -- \
  env VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="$VAULT_TOKEN" \
  vault kv get -format=json kv/components/operator-orchestration-service/prod/openproject
```

Check only for presence of key `apiToken`; do not echo the token value into
terminal history or Git-tracked artifacts.

## Notes

- the token belongs to the broker component, not the OpenProject runtime secret
  tree
- this runbook does not yet create a Vault Kubernetes auth role for the broker;
  that belongs to the broker runtime admission work
