# Provision Delivery ART Identities

## Purpose

Converge the assignable non-admin identities that the `Workspace Delivery ART`
needs in order to represent repo ownership directly in the OpenProject UI and
broker-backed delivery workflow.

This control provisions:

- the broker identity `operator-orchestration-service`
- repo-owner identities for:
  - `platform-engineering`
  - `workspace-governance`
  - `workspace-governance-control-fabric`
  - `security-architecture`
  - `openclaw-runtime-distribution`
  - `openclaw-telegram-enhanced`
  - `openclaw-host-bridge`
- canonical project membership on `workspace-delivery-art`
- the broker identity membership on `workspace-proposals`
- the broker API token in Vault for the existing operator workflow

The machine-readable source of truth is:

- [../delivery-art-identities.json](../delivery-art-identities.json)

OpenProject's live assignee surface currently requires more than plain project
membership. The repo-owner identities therefore carry:

- `Reader`
- `Work package editor`

on `workspace-delivery-art` so they actually appear as assignable principals in
the work-item form and broker-backed create/update flow.

## Preconditions

- OpenProject rollout is healthy
- the canonical `workspace-proposals` backlog model already exists
- the canonical `workspace-delivery-art` project already exists
- `VAULT_TOKEN` is set for a token that can write:
  - `kv/components/operator-orchestration-service/prod/openproject`

## Command

```bash
export VAULT_TOKEN='...'
make openproject-provision-delivery-art-identities
```

## Expected Outcome

- every identity in [../delivery-art-identities.json](../delivery-art-identities.json)
  exists and remains non-admin
- `workspace-delivery-art` exposes those identities as assignable principals
  in work-item forms
- `operator-orchestration-service` remains a member of both:
  - `workspace-proposals`
  - `workspace-delivery-art`
- Vault path `kv/components/operator-orchestration-service/prod/openproject`
  contains key `apiToken`

## Verification

Confirm the expected members and roles:

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "logins = %w[operator-orchestration-service platform-engineering workspace-governance workspace-governance-control-fabric security-architecture openclaw-runtime-distribution openclaw-telegram-enhanced openclaw-host-bridge]; projects = Project.where(identifier: [\"workspace-proposals\", \"workspace-delivery-art\"]).order(:identifier); rows = logins.map do |login| user = User.find_by!(login: login); memberships = projects.map do |project| member = Member.find_by(project: project, principal: user); {identifier: project.identifier, roles: member&.roles&.order(:name)&.pluck(:name) || []}; end; {login: user.login, admin: user.admin, memberships: memberships}; end; puts rows.to_json"'
```

Confirm the delivery project now exposes the principals as assignable:

```bash
k3s kubectl -n openproject exec deploy/openproject-web -- \
  sh -lc 'bundle exec rails runner "project = Project.find_by!(identifier: \"workspace-delivery-art\"); form = WorkPackages::CreateForm.new(User.find_by!(login: \"operator-orchestration-service\"), project: project, type: project.types.find_by!(name: \"Task\")); schema = ::API::V3::WorkPackages::SchemaRepresenter.create(form.schema, current_user: User.find_by!(login: \"operator-orchestration-service\")); assignee = schema.to_hash.dig(:_embedded, :assignee); puts({href: assignee[:_links][:allowedValues][:href], writable: assignee[:writable]}.to_json)"'
```

Confirm the broker token remains in Vault:

```bash
k3s kubectl -n vault exec vault-0 -- \
  env VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN="$VAULT_TOKEN" \
  vault kv get -format=json kv/components/operator-orchestration-service/prod/openproject
```

Check only for presence of key `apiToken`; do not echo the token value into
terminal history or Git-tracked artifacts.

## Notes

- the repo-owner identities are assignable principals, not admin users
- the broker identity remains the only ART identity that currently needs an API
  token and Vault-backed secret storage
- if `delivery-art-identities.json` changes, rerun this workflow so the
  OpenProject project membership surface stays aligned with the contract
