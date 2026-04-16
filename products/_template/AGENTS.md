# Product Integration Agent Notes

This file is the template for product-local guidance inside
`platform-engineering/products/<product>/`.

Use it when a product needs operator instructions that are too specific to live
in the repo-root `AGENTS.md`.

## Purpose

Document only the product-specific platform integration rules here.

Examples:

- product-local scripts and runbooks
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
- where product-local scripts and runbooks live
- product-specific guardrails that future agents must preserve
