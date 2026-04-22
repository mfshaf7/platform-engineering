# Show Delivery Active Front

## Purpose

Show the fast broker-backed active front for one delivery `Epic` without paying
for the full deep execution read.

Use this when:

- the active `Epic` is already known
- you need the current committed front quickly
- you want a routine session-start read before opening repo code
- you do not yet need the full evidence-grade execution tree

This is the preferred startup read for active delivery work.

`parked` work is intentionally hidden from this surface by default because the
goal here is the current active front, not every open deferred item. Use
[show-delivery-execution.md](show-delivery-execution.md) or
[show-delivery-initiatives.md](show-delivery-initiatives.md) for all-open
visibility.

## Command

Run from `platform-engineering/`:

```bash
make openproject-show-delivery-active-front \
  TARGET_EPIC_ID=38
```

Optional fields:

- `INCLUDE_DONE=true|false`
- `INCLUDE_INACTIVE=true|false`
- `INCLUDE_PARKED=true|false` as a backward-compatible alias

For the `accepted-idea-delivery` devint lane, also set the namespace:

```bash
make openproject-show-delivery-active-front \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7 \
  TARGET_EPIC_ID=38
```

## Expected Outcome

The command prints JSON with:

- delivery identity
- top-level `Epic` identity and status
- a bounded summary of the active front
- highlighted active items under the `Epic`
- PI objectives attached to that initiative
- ART risks attached to that initiative

This output is intentionally lighter than
[show-delivery-execution.md](show-delivery-execution.md). Use the deeper read
when you need:

- full recursive tree detail
- completion-evidence inspection
- ready-contract inspection
- dependency relation detail
- blocker-field detail

## Session Start Rule

Recommended order when the active `Epic` is already known:

1. `make openproject-show-delivery-active-front TARGET_EPIC_ID=<epic-id>`
2. `make openproject-check-delivery-art-quality TARGET_EPIC_ID=<epic-id>`
3. `make openproject-show-delivery-execution TARGET_EPIC_ID=<epic-id>` only when a deep read is actually needed

Use [show-delivery-initiatives.md](show-delivery-initiatives.md) only when the
active initiative is not yet known or when portfolio/PI replanning is the
current job.

## Related References

- [show-delivery-initiatives.md](show-delivery-initiatives.md)
- [check-delivery-art-quality.md](check-delivery-art-quality.md)
- [show-delivery-execution.md](show-delivery-execution.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
