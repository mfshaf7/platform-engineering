# Manage Delivery Initiative Lineage

## Purpose

Define the only supported lineage model for top-level `Epic` work in
`Workspace Delivery ART`.

Use this runbook when:

- a new top-level initiative is created
- a follow-on epic continues an existing architecture thread
- a control-hardening epic belongs to an existing initiative family
- portfolio views need to distinguish unrelated initiative families cleanly

Canonical machine-readable contract:

- [delivery-art-initiative-lineage.json](../delivery-art-initiative-lineage.json)

That contract is the source for:

- the lineage custom fields on top-level `Epic` work
- the temporary shell exception for brand-new initiatives
- allowed `Initiative Family` values
- allowed `Lineage Role` values
- anchor/upstream gate requirements

## Working Rule

The ART may contain multiple valid initiative families in one portfolio.

The portfolio becomes incoherent only when top-level epics are left without
machine-readable family and lineage metadata.

So the rule is:

- same ART project does **not** imply same storyline
- every top-level `Epic` must eventually declare its family and lineage role
- only a brand-new `new` + `Initiating` shell with blank `Target PI` may remain
  temporarily unclassified

## Canonical Fields

These fields exist only on top-level `Epic` work:

- `Initiative Family`
- `Lineage Role`
- `Architecture Anchor Ref`
- `Required Upstream Ref`

Use `Execution Context` to mirror those fields in flat human-readable bullets:

- `Owner repo`
- `Initiative family`
- `Lineage role`
- `Architecture anchor`
- `Required upstream`

Do not keep lineage only in prose.

## Family Values

- `governed-ai-control-plane`
  - centralized governance control-plane architecture, parity, topology, and
    bounded governed AI activation
- `enterprise-cybersecurity-baseline`
  - cybersecurity baseline and assurance work
- `delivery-art-governance-foundations`
  - ART machine-model, taxonomy, and projection-governance controls
- `delivery-art-operator-surfaces`
  - ART operator-path and admin-surface hardening
- `devint-smoke`
  - smoke or rehearsal initiatives that exist only to prove reachability

## Lineage Roles

- `architecture-anchor`
  - top-level truth for one family
  - must not set `Architecture Anchor Ref`
  - must not set `Required Upstream Ref`
- `prerequisite-foundation`
  - required foundation tranche beneath an anchor
  - must set `Architecture Anchor Ref`
  - may set `Required Upstream Ref`
- `topology-decision`
  - structural topology or extraction decision
  - must set both `Architecture Anchor Ref` and `Required Upstream Ref`
- `bounded-activation`
  - first bounded consumer/runtime activation after the gate
  - must set both `Architecture Anchor Ref` and `Required Upstream Ref`
- `control-hardening`
  - control or operator-surface hardening beneath an existing family
  - must set `Architecture Anchor Ref`
  - may set `Required Upstream Ref`
- `operational-smoke`
  - temporary smoke or rehearsal work
  - must not set `Architecture Anchor Ref`
  - must not set `Required Upstream Ref`

## Exact Checklist

### 1. New Top-Level Initiative Shell

Allowed temporary posture:

- `status = new`
- `PM² Phase = Initiating`
- blank `Target PI`
- blank lineage fields

This is the only unclassified exception.

### 2. Move Beyond Shell Posture

Before the initiative becomes planning, committed, done, or retired:

- set `Initiative Family`
- set `Lineage Role`
- set `Architecture Anchor Ref` when the role requires it
- set `Required Upstream Ref` when the role requires it

### 3. Anchor Integrity

When `Architecture Anchor Ref` is present:

- it must point to an existing top-level `Epic`
- it must stay in the same `Initiative Family`

### 4. Upstream Integrity

When `Required Upstream Ref` is present:

- it must point to an existing ART work package
- it must resolve inside the same initiative family

### 5. Portfolio Views

Use the managed `Initiative Family Board` and `Initiative Family / ...` queries
to inspect initiative coherence by family instead of reading one flat ART board
as if every epic shared one storyline.

## Examples

- `#38`
  - family: `governed-ai-control-plane`
  - role: `architecture-anchor`
- `#227`
  - family: `governed-ai-control-plane`
  - role: `prerequisite-foundation`
  - anchor: `openproject://work_packages/38`
- `#247`
  - family: `governed-ai-control-plane`
  - role: `topology-decision`
  - anchor: `openproject://work_packages/38`
  - upstream: `openproject://work_packages/245`
- `#251`
  - family: `governed-ai-control-plane`
  - role: `bounded-activation`
  - anchor: `openproject://work_packages/38`
  - upstream: `openproject://work_packages/245`
- `#87`
  - family: `enterprise-cybersecurity-baseline`
  - role: `architecture-anchor`
- `#304`
  - family: `delivery-art-operator-surfaces`
  - role: `control-hardening`
  - anchor: `openproject://work_packages/277`

## Machine Gates

- `initiative-family-required-before-planning-or-commitment`
- `initiative-lineage-role-must-satisfy-anchor-requirements`
- `initiative-anchor-ref-must-point-to-top-level-epic`
- `initiative-anchor-family-must-match`
- `initiative-upstream-ref-must-point-to-existing-art-record`

If lineage drift appears, name the exact gate id instead of calling it generic
portfolio confusion.
