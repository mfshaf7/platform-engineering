# Shared Platform Scripts

This directory is now reserved for shared platform scripts only.

## Shared Platform Scripts

These support shared platform operations:

- `bootstrap_operator_access.sh`
- `bootstrap_vault.sh`
- `dispatch_github_workflow_from_k3s_secret.sh`
- `migrate_k8s_secret_to_vault.py`
- `validate_governance_docs.py`
- `validate_operational_docs.py`
- `validate_repo_structure.py`

`validate_governance_docs.py` checks ADR and change-record structure, and the
shared PR governance template that routes future changes into the right
decision and evidence path.

`validate_operational_docs.py` checks workflow-doc coverage and freshness stamps
for current topology and access docs.

## Product-Specific Scripts

Product-specific entrypoints and helper modules must live under the owning
product directory:

- OpenClaw: [products/openclaw/scripts/README.md](../products/openclaw/scripts/README.md)
- OpenProject: [products/openproject/scripts/README.md](../products/openproject/scripts/README.md)

Do not add new product-specific scripts at the top level.
