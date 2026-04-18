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
- disposable
- isolated from governed `stage` and `prod`

It is not:

- a second stage environment
- a release lane
- a source of governed rollout evidence
- a place that may write to governed backends or consume governed secrets

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

## Runtime Target

The shared runtime target is local `k3s`.

Expected lane properties:

- separate per-profile or per-operator namespaces
- local-only generated secrets
- no Argo or environment-pin updates
- no writes to governed `stage` or `prod` services
- easy reset and teardown

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

The session manifest is local-only and does not become governed evidence.

## Required Operator Actions

Shared operator entrypoints:

- `devint-up`
- `devint-status`
- `devint-smoke`
- `devint-down`
- `devint-reset`
- `devint-promote-check`

The shared runner dispatches those actions into the owner repo's concrete
profile.

## Profile Admission

`dev-integration` profiles are not automatically self-serve just because a repo
contains a `profile.yaml`.

The workspace contract tracks profile lifecycle separately:

- `proposed`
- `active`
- `suspended`
- `retired`

Only `active` profiles are launchable from the shared runner. The request and
admission truth is owned in `workspace-governance`, even if the current human
request surface happens to be a specific tool such as OpenProject.

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

That keeps fast local iteration separate from governed rollout.
