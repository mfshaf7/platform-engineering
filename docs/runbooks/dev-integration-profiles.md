# Dev-Integration Profiles

This runbook is the primary operator-facing procedure for requesting and using
`dev-integration` profiles.

Use it when you need a fast local `k3s` environment for cross-repo workflow or
API iteration and want to know:

- whether an approved profile already exists
- how to launch and operate an approved profile
- how to request a new profile when no approved one fits

Do not reconstruct this flow from scattered contracts, templates, and
standards files. Those remain supporting governance sources, not the primary
operator path.

## 1. Check Whether An Active Profile Already Exists

The canonical registry is:

- [workspace-governance/contracts/developer-integration-profiles.yaml](https://github.com/mfshaf7/workspace-governance/blob/main/contracts/developer-integration-profiles.yaml)

Only profiles with:

- `lifecycle: active`

are self-serve launchable from the shared runner.

Current example:

- `idea-workflow`
  - owner repo: `operator-orchestration-service`
  - profile path:
    [operator-orchestration-service/dev-integration/profiles/idea-workflow/profile.yaml](https://github.com/mfshaf7/operator-orchestration-service/blob/main/dev-integration/profiles/idea-workflow/profile.yaml)

If a suitable `active` profile already exists, use it directly. If not, follow
the request path in section 3.

## 2. Use An Active Profile

Run the shared operator commands from `platform-engineering/`:

```bash
make devint-up PROFILE=<profile>
make devint-status PROFILE=<profile>
make devint-smoke PROFILE=<profile>
make devint-promote-check PROFILE=<profile>
make devint-reset PROFILE=<profile>
make devint-down PROFILE=<profile>
```

Meaning:

- `devint-up`
  - creates or refreshes the local `k3s` namespace and starts the profile
- `devint-status`
  - shows the current session and runtime state
- `devint-smoke`
  - runs the profile’s smoke checks
- `devint-promote-check`
  - shows what must be formalized before governed `stage`
- `devint-reset`
  - tears down and rebuilds the local profile state
- `devint-down`
  - stops and removes the local profile session

Important boundaries:

- `dev-integration` is local only
- it is not governed rollout evidence
- it must not write to governed `stage` or `prod` backends
- it may use local branches, worktrees, and dirty state
- it still requires a governed handoff before `stage`

## 3. Request A New Profile When None Fits

If no suitable `active` profile exists, request a new one.

The request/admission contract is generic, but the current human request
surface adapter is OpenProject.

Current request surface:

- project: `Workspace Proposals`
- identifier: `workspace-proposals`
- access path:
  [../../products/openproject/runbooks/access-openproject.md](../../products/openproject/runbooks/access-openproject.md)
- canonical backlog contract:
  [../../products/openproject/idea-backlog-contract.md](../../products/openproject/idea-backlog-contract.md)

Recommended request record shape in the current adapter:

- type:
  - `Component Proposal` when one component repo clearly owns the profile
  - otherwise the proposal type that best matches the owner shape
- status:
  - `captured` or `triaged` while the profile is still `proposed`

Required request content:

- requested profile id
- owner repo
- purpose
- participating repos
- runtime dependencies
- expected canonical backend writes, if any
- whether identity, secrets, runtime privilege, or AI review is involved
- requested by
- request record system
- request record ref

Supporting template:

- [workspace-governance/templates/dev-integration-request/README.md](https://github.com/mfshaf7/workspace-governance/blob/main/templates/dev-integration-request/README.md)

When the current adapter is OpenProject, record:

- `request_record.system: openproject`
- `request_record.ref: openproject://work_packages/<id>`

## 4. How A Requested Profile Becomes Launchable

A request is not the same thing as an approved self-serve profile.

The admission path is:

1. the request is recorded
2. the owner repo confirms the profile belongs there
3. `platform-engineering` accepts or rejects the shared-lane fit
4. `security-architecture` reviews it when the profile widens identity,
   secrets, runtime privilege, AI influence, or other risky boundaries
5. `workspace-governance` records the profile in
   `developer-integration-profiles.yaml`
6. the profile becomes self-serve only when its lifecycle is set to `active`

Lifecycle meanings:

- `proposed`
  - request exists, not self-serve launchable
- `active`
  - admitted and self-serve launchable
- `suspended`
  - admitted before, temporarily blocked from normal launch
- `retired`
  - no longer part of the active self-serve set

## 5. What Happens After Dev-Integration

`dev-integration` never promotes its runtime directly into `stage`.

The required handoff is:

1. run `make devint-promote-check PROFILE=<profile>`
2. turn the winning local shape into real source changes
3. run repo-local validation
4. move those changes through the normal PR and platform contract path
5. rehearse the governed candidate in `stage`

For the workspace-level PR flow and Codex review procedure that begins after
step 4, use:

- [workspace-governance/docs/codex-github-review-and-automation.md](https://github.com/mfshaf7/workspace-governance/blob/main/docs/codex-github-review-and-automation.md)

Supporting standard:

- [../standards/dev-integration-lane.md](../standards/dev-integration-lane.md)
