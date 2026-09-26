# Delivery ART Owner Evidence

This directory contains the Platform Engineering evidence profile consumed by
Operator Orchestration Service (OOS) for source-backed Delivery ART work.

OOS reads `evidence-profile.json` from the work session's exact recorded base
commit. Candidate branches cannot change the policy used to validate
themselves. The first landing of this profile therefore uses the controlled,
reviewed bootstrap path; automated acquisition is available only to later work
sessions whose base already contains the accepted profile.

The profile runs bounded repository, dev-integration, identity, documentation,
and source-diff checks. It grants no merge, ART mutation, runtime activation,
Security approval, stage, or production authority.
