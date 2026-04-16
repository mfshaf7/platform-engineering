# Records

This directory stores historical evidence records for production-impacting
changes.

Use it when the question is:

- what changed in production or a governed environment
- what evidence exists for a fix
- what was deployed and how was it verified

Records are not design decisions.

## Use A Change Record When

Use a change record when a production-impacting issue required governed repair,
such as:

- source fix plus rollout
- artifact rebuild or digest promotion
- Argo reconciliation evidence
- host or runtime drift repair

If the repair also changed a durable shared design, add or update an ADR. The
change record is not allowed to become the architecture rationale.

## Do Not Use A Change Record For

- long-form architecture rationale
- a future-looking design choice
- a repo refactor with no governed runtime impact

## Change Record Location

- [change-records/README.md](change-records/README.md)
