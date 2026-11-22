# Delivery Catalog Control

This directory owns the Platform-side OpenProject adapter for the Governance
Operations Console Delivery Catalog.

The adapter exposes bounded authenticated route shapes inside the existing
OpenProject Rails process:

- `GET /v1/delivery-catalog/projection`
- `POST /v1/delivery-catalog/<catalog-item-id>/mutations`
- `GET /v1/delivery-memberships/projection` (unpublished membership extension)
- `POST /v1/delivery-memberships/mutations` (unpublished membership extension)

It does not expose a general OpenProject administration API.

The membership extension uses native Members services under the non-admin
broker's Delivery-project permission. The browser cannot choose a project or
global role. Native visibility, project-role grantability and group inheritance
remain enforced. Administrator/service access and groups containing those
identities are protected. It reuses the existing setting transaction for both
membership changes and request-bound receipts; exact replay never reapplies an
old decision. Search and pagination bound returned rows. No account creation or
invitation route is added. Procedure and recovery are owned by
[OOS](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-project-members.md).

Native integration support: `test_memberships_native.rb` runs only with explicit
`OPENPROJECT_MEMBERSHIP_QUALIFICATION=rollback-only` and an explicitly supplied
review-source path. It tests synthetic accounts/groups in a database transaction
and verifies that fixtures and receipt changes roll back. It is not a runtime
route or a replacement for composed source acceptance.

## Source Model

The projection derives Catalog truth from native OpenProject records wherever
OpenProject already owns the value:

- versions and version dates
- custom-field options
- project principals
- live work-package usage

Assignable lookup uses native `Principal.possible_assignee`, matching the
assignment endpoint rather than treating every active project user as
assignable. Group and placeholder identities retain native references; ordinary
membership and assignment permission remain separate facts.

Values without a native OpenProject owner use the namespaced
`delivery_catalog_control_v1` setting. That setting stores only bounded
registry values, retirement tombstones, and idempotency receipts. It is not a
second project database.

Target PI names use `PI-YYYY-NN`. Creating a PI or changing its dates
requires saving an iteration calendar. The calendar stores numbered
iterations alongside native OpenProject version dates. A PI details edit
keeps the saved dates, and the Iteration register is read-only.
The version, generated values and receipt commit in the same database
transaction. Old work-item iteration labels remain available for history.

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

Target PI calendar requests use a start date, a length in days and a count.
OpenProject derives the inclusive end date, rejects overlaps, and saves the
PI and all full iterations in one transaction. When dating an existing PI,
use its verified schedule. Exact numbered keys keep their identity and usage.
Other recorded labels retain their original values and dates. The adapter
leaves work-package assignments untouched.

## Validation

Run:

```bash
python3 products/openproject/catalog-control/validate_catalog_control.py
python3 products/openproject/catalog-control/test_validate_catalog_control.py
ruby products/openproject/catalog-control/test_pi_calendar.rb
python3 scripts/test_dev_integration_compositions.py
```

The validator keeps the Console-facing Catalog vocabulary, source kinds,
capability modes, and exact route boundary coherent.
