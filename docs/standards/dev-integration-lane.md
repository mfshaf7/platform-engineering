# Dev-Integration Lane

## Purpose

`dev-integration` is the fast local iteration lane for cross-repo workflow and
API development that is still too fluid for governed `stage` rehearsal.

It exists to stop using governed `stage` as the place where operators discover
basic environment, command, and integration-shape mistakes.

## Control Model

`dev-integration` is:

- local only
- ungoverned for delivery
- contract-aligned for interfaces
- runtime-model driven: disposable or persistent-project-backed
- lane-classed as `prototype-devint`, `integration-devint`, or
  `governed-devint`
- isolated from governed `stage` and `prod`

It is not:

- a second stage environment
- a release lane
- a source of governed rollout evidence
- a place that may write to governed backends or consume governed secrets

Primary operator procedure:

- [../runbooks/dev-integration-profiles.md](../runbooks/dev-integration-profiles.md)

Use that runbook for the actual request and usage path. This standard defines
the lane model and boundaries; it is not the primary step-by-step operator
surface.

## Ownership

- lane standard: `workspace-governance`
- shared runner and local-k3s implementation: `platform-engineering`
- concrete profile: owner repo for the workflow being iterated
- trust-boundary review: `security-architecture`

This means `dev-integration` is workspace-standardized, but not
workspace-operated.

## Core Model

Every `dev-integration` session has three parts:

1. profile
   - defines the runtime shape
2. branch or worktree
   - defines the source state for each participating repo
3. session manifest
   - records exactly what ran

Profile-only is not enough because the runtime shape does not tell you which
branch, worktree, or dirty state each repo contributed.

Branch-only is not enough because source state does not tell you which
services, seed jobs, smoke checks, and cleanup behavior the environment needs.

## Lane Classes

- `prototype-devint`: prototype preview for internal tools, client app
  concepts, UI prototypes, and UI-plus-backend experiments before graduation.
- `integration-devint`: fast workflow or API integration rehearsal that is not
  governed runtime evidence.
- `governed-devint`: local proof lane for an admitted governed component or
  workflow before stage handoff.

## Runtime Target

The shared runtime target is local `k3s`.

Expected lane properties:

- separate per-profile or per-operator namespaces
- local-only generated secrets
- no Argo or environment-pin updates
- no writes to governed `stage` or `prod` services
- easy reset and teardown for disposable profiles
- safe suspend and resume for persistent project-backed profiles

## Runtime State Models

Profiles must declare one of these runtime state models in `profile.yaml`:

- `disposable`
  - optimized for short-lived smoke and workflow rehearsal
  - `devint-down` may remove the live runtime
  - `devint-reset` is destructive and wipes the local profile state
- `persistent`
  - optimized for long-running project-backed execution in the local lane
  - `devint-down` must preserve project data and act as suspend, not wipe
  - `devint-up` must resume or reconcile the preserved runtime state
  - `devint-reset` remains the only destructive rebuild path
  - shared `devint-smoke` must stay read-only on the persistent working lane

Persistent profiles are still local-only and ungoverned. They do not become a
replacement for `stage`, but they do avoid forcing large in-flight project
trees to rebuild on every stop/start cycle.

If a workflow still needs mutating smoke, admit and use a separate disposable
companion profile instead of writing test artifacts into the persistent
working lane.

When a new profile requests `persistent` state, the admission record must make
these operator commitments explicit:

- why a disposable lane is insufficient
- what data survives normal suspend/resume
- what storage footprint or storage-class assumptions are required
- what `devint-reset` is allowed to destroy
- whether a cutover plan is required from an existing disposable lane

## Git Model

`dev-integration` explicitly allows:

- local branches
- git worktrees
- local-only commits
- dirty working trees

It does not require:

- pushing to GitHub
- opening a PR
- merging to `main`

That GitHub cost begins only when the winning shape is handed off into the
governed stage path.

## Required Session Manifest

Every `dev-integration` run must record:

- profile id
- operator
- namespace
- session id
- owner repo
- runtime owner
- source repos with:
  - path
  - branch
  - head SHA
  - dirty or clean
  - upstream tracking state
  - whether a path override or worktree was used

The current session manifest is local-only and does not become governed evidence.
The shared runner also retains a no-overwrite manifest and result receipt for
every dispatched action under the session archive. Those action records bind
the result to the exact source state observed before dispatch. When an owner
repo path override is selected, that checkout supplies the profile definition,
working directory, command path, and recorded Git state as one boundary; the
runner re-executes itself from a selected `platform-engineering` checkout and
preserves the already resolved workspace root across that boundary. It must not
record one checkout while executing another. A governed Review
Packet may cite action-record digests; the local files do not become governance
authority by themselves.

## Required Operator Actions

Shared operator entrypoints:

- `devint-up`
- `devint-status`
- `devint-access`
- `devint-smoke`
- `devint-down`
- `devint-reset`
- `devint-promote-check`

The shared runner dispatches those actions into the owner repo's concrete
profile.

Persistent profiles that retain safety-critical local state may additionally
implement:

- `devint-backup`
- `devint-restore`

Those actions are optional for profiles without a durable local data boundary.
When implemented, both remain active-profile actions, backups stay
operator-local, restore requires explicit confirmation, and neither action
produces governed rollout evidence.

## Profile Admission

`dev-integration` profiles are not automatically self-serve just because a repo
contains a `profile.yaml`.

The workspace contract tracks profile lifecycle separately:

- `proposed`
- `build-admitted`
- `active`
- `suspended`
- `retired`

`build-admitted` authorizes bounded owner-repo implementation after platform
and security gates, but it is still not launchable. Only `active` profiles are
launchable from the shared runner. The request and admission truth is owned in
`workspace-governance`, even if the current human request surface happens to be
a specific tool such as OpenProject.

## Forbidden Targets

`dev-integration` must never:

- write to governed stage backends
- write to governed prod backends
- consume shared governed secrets by default
- claim governed stage or prod evidence

If a workflow needs a canonical backend, it must use a local disposable
instance or another explicitly scratch-scoped backend.

## Handoff To Stage

`dev-integration` does not promote its runtime directly.

The required handoff is:

1. generate a promotion report from the local session
2. convert winning local changes into real source commits
3. run repo-local validation
4. move through the normal PR and platform contract path
5. rehearse the governed candidate in `stage`

Active profiles must carry a concrete stage-handoff contract:

- `stage_handoff.required_checks` in the profile contract
- matching documentation in the profile README
- promote-check output that reflects the same checks instead of stale
  hardcoded assumptions

Source landing is not closure when the documented handoff still requires
governed `stage` evidence.

If a persistent profile and a disposable companion profile split the workflow,
the handoff obligations should stay attached to the profile that actually proves
the mutating behavior instead of pretending the persistent workbench still
owns that proof.

That keeps fast local iteration separate from governed rollout.

When the handoff reaches the PR path, follow the workspace-level Codex review
and PR procedure in:

- [workspace-governance/docs/codex-github-review-and-automation.md](https://github.com/mfshaf7/workspace-governance/blob/main/docs/codex-github-review-and-automation.md)
