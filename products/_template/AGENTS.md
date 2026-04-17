# Product Integration Agent Notes

This file is the template for product-local guidance inside
`platform-engineering/products/<product>/`.

Use it when a product needs operator instructions that are too specific to live
in the repo-root `AGENTS.md`.

## Purpose

Document only the product-specific platform integration rules here.

Examples:

- product-local scripts and runbooks
- product-local access and login guidance
- product-specific release or rollout guardrails
- product-specific visibility and operating checks

## Do Not Put Here

- generic platform bootstrap
- shared secret-delivery patterns
- shared platform standards
- another copy of the repo-root instructions

## Minimum Content

- what this product directory owns
- what it does not own
- what to read first
- current workflow maturity:
  - source-only
  - platform-integrated
  - fully governed
- whether stage exists for this product
- whether governed prod promotion exists for this product
- the highest real operator endpoint that exists today
- where product-local scripts and runbooks live
- how product-local access docs stay aligned with shared platform access docs
- product-specific guardrails that future agents must preserve
- whether the product supports a governed runtime lifecycle profile, and which
  states are actually implemented

## Workflow Maturity Guardrail

Do not copy OpenClaw-style release guidance into another product unless that
product really has the same stage, approval, and promotion path.

If the product does not yet have a full end-to-end workflow:

- say so explicitly
- stop at the highest real governed layer
- treat any required live mutation as a platform or host change with evidence
  and follow-up

If the product is fully governed and uses a rehearsal environment, prefer
explicit release-state objects over implicit controller state:

- release candidate
- verification evidence
- approval decision

If the product has a live prod surface that should be exercised after cutover,
also prefer an explicit post-promotion prod smoke or UAT object rather than
leaving prod acceptance in chat memory or ad hoc notes:

- prod verification evidence

If the product supports a governed runtime lifecycle, publish the product-local
profile using the shared vocabulary in
`../../docs/standards/governed-runtime-lifecycle-model.md` instead of inventing
new state names ad hoc.

## New Product Discussion Gate

If this directory is being created for a brand-new product, discuss the target
architecture with the user before implementation hardens:

- why the product belongs on the platform
- whether it is source-only, platform-integrated, or fully governed on day one
- what operator surfaces and access paths it will expose
- which shared components it depends on
- what evidence and rollout path will actually exist
