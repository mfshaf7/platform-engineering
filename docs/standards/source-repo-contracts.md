# Source Repo Contracts

## Purpose

This document defines how source repositories plug into the platform deployment
model.

## Canonical Responsibilities

| Repository type | Canonical responsibility | Consumed by platform repo as |
| --- | --- | --- |
| Product runtime repo | Runtime source, product-specific docs, metrics and health contracts | artifact input and version metadata |
| Host integration repo | host bridge, recovery, host-side startup and service code | WSL host package input and host metadata |
| Deployment composition repo | image build context, integration docs, deployment-specific glue | reference deployment input and environment documentation |

## Platform Consumption Rule

This repository pins released versions from those repos.

It must not silently absorb unreleased local workspace changes.

## Emergency Hotfix Rule

If a live hotfix happens:

1. record the incident
2. backport it to the canonical source repo
3. rebuild the artifact
4. update the platform manifest
5. reconcile the runtime back to the approved artifact
6. confirm drift returns to `green`
