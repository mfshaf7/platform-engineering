# Standardize Delivery ART

## Purpose

Normalize the live `Workspace Delivery ART` records to the current execution
and narrative standard after the contract, validators, or field model changes.

Use this when:

- a new required field such as `Owner Repo` was added after work already
  existed
- active or done items drifted away from the current description template
- a full ART quality sweep shows structural issues that are better repaired in
  one governed pass than by hand-editing each item

This is a controlled maintenance workflow. It is not a replacement for the
normal create, update, and complete entrypoints.

## What It Standardizes

The current standardization pass can:

- populate missing `Owner Repo`
- populate missing `Assignee` and `Responsible` on active and done work
- populate missing active-execution contract fields:
  - `Delivery Team`
  - `Iteration`
  - `Acceptance Criteria`
  - `Definition of Ready`
  - `Definition of Done`
- normalize descriptions to the current per-type narrative headings:
  - `Epic`
    - `What This Initiative Achieves`
    - `Current PI Focus`
    - `Scope Boundaries`
    - `Execution Context`
  - `PI Objective`
    - `Outcome`
    - `Why This PI`
    - `Success Signal`
    - `Execution Context`
  - `Risk`
    - `Risk Event`
    - `Impact`
    - `Current Handling`
    - `Execution Context`
  - `Feature`
    - `What This Achieves`
    - `Benefit Hypothesis`
    - `Scope Boundaries`
    - `Execution Context`
  - `Enabler`
    - `What This Enables`
    - `Benefit Hypothesis`
    - `Scope Boundaries`
    - `Execution Context`
  - `User story` / `Task`
    - `What This Achieves`
    - `Why This Matters Now`
    - `Evidence Expectation`
    - `Execution Context`
  - `Milestone`
    - `Exit Condition`
    - `Execution Context`
- preserve existing done-state completion sections while normalizing the
  narrative headings around them

It does not invent new scope, PI commitment, or blocker decisions.

## Command

Run from `platform-engineering/`:

```bash
make openproject-standardize-delivery-art \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7
```

Optional fields:

- `TARGET_EPIC_ID=<epic-id>`
  - limit the normalization pass to one initiative subtree instead of the full
    ART

## Expected Outcome

The command prints a JSON summary showing:

- the project identifier
- the optional target epic id
- the number of changed work packages
- which work packages were changed and which fields or description surfaces
  were normalized

After the pass, rerun:

```bash
make openproject-check-delivery-art-quality \
  OPENPROJECT_NAMESPACE=devint-accepted-idea-delivery-mfshaf7
```

The normalization pass is only complete when the ART quality report is clean
enough for the intended scope.

## Related References

- [check-delivery-art-quality.md](check-delivery-art-quality.md)
- [delivery-art-contract.md](../delivery-art-contract.md)
- [operator-orchestration-service delivery operator surface](https://github.com/mfshaf7/operator-orchestration-service/blob/main/docs/operations/delivery-workflow-operator-surface.md)
