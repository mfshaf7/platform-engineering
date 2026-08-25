# Delivery Catalog Control

This directory owns the Platform-side OpenProject adapter for the Governance
Operations Console Delivery Catalog.

The adapter exposes exactly two authenticated route shapes inside the existing
OpenProject Rails process:

- `GET /v1/delivery-catalog/projection`
- `POST /v1/delivery-catalog/<catalog-item-id>/mutations`

It does not expose a general OpenProject administration API.

## Source Model

The projection derives Catalog truth from native OpenProject records wherever
OpenProject already owns the value:

- versions and version dates
- custom-field options
- project principals
- live work-package usage

Values without a native OpenProject owner use the namespaced
`delivery_catalog_control_v1` setting. That setting stores only bounded
registry values, retirement tombstones, and idempotency receipts. It is not a
second project database.

## Runtime Shape

The active dev-integration composition mounts:

- `additional_environment.rb` as the OpenProject additional-environment hook
- `openproject_delivery_catalog_control.rb` as the bounded runtime extension
- `catalog-control-contract.json` as the machine contract

The composition also projects a runtime-generated shared secret separately to
OpenProject and the Operator Orchestration Service. The secret never belongs
in Git or composition state.

The platform-integrated production OpenProject runtime is unchanged. Activating
this adapter outside dev-integration requires its own governed promotion and
security evidence.

## Validation

Run:

```bash
python3 products/openproject/catalog-control/validate_catalog_control.py
python3 products/openproject/catalog-control/test_validate_catalog_control.py
python3 scripts/test_dev_integration_compositions.py
```

The validator keeps the Console-facing Catalog vocabulary, source kinds,
capability modes, and exact route boundary coherent.
