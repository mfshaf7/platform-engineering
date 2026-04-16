# Decisions

This directory stores durable platform decisions.

Use it when the question is:

- why was this design chosen
- which architecture choice is current
- which older choice was superseded

Decision records are not runbooks and not incident evidence.

## Use An ADR When

Use an ADR when a platform-wide or component-wide decision changes:

- trust boundary or control-plane ownership
- secret-delivery or identity model
- rollout or artifact policy
- host integration or recovery architecture
- component architecture that future work must preserve

If that decision is later applied to stage, prod, or a host-owned governed
surface, pair the ADR with a change record. The ADR explains the durable
decision; the change record proves the rollout.

## Do Not Use An ADR For

- a one-off fix diary
- a rollout completion note
- a production incident evidence record
- a product-local runtime tweak that does not change shared platform design

## ADR Location

- [adr/README.md](adr/README.md)
