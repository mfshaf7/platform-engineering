# Suspend Unused Platform OpenProject Runtime

## Summary

The platform-integrated OpenProject instance was running beside the separate
`accepted-idea-delivery` OpenProject workbench even though only the latter is
used for current Delivery ART work. The unused application workloads are now
suspended at zero replicas to reduce the local WSL memory baseline.

## Classification

- work home: owner-repo maintenance
- Landing Unit: `maintenance-suspend-unused-openproject`
- owner repo: `platform-engineering`
- runtime: local `k3s`, Argo application `openproject`
- posture: reversible suspension with retained data

## Ownership

Platform Engineering owns the Argo application, runtime declaration, live
containment, and reactivation. The OOS-owned `accepted-idea-delivery` profile
continues to own the separate active ART workbench.

## Root Cause

Both the platform-integrated and dev-integration OpenProject stacks were active
after restart. That was valid configuration but unnecessary for the current
operating posture and kept roughly two additional GiB of Ruby application
processes resident in WSL.

## Source Changes

The OpenProject Argo values set web, worker, Memcached, and cron replicas to
zero and disable Hocuspocus while suspended. Product and shared live-state
documentation identify the endpoint as unavailable and retain the existing
reactivation path.

## Artifact And Deployment Evidence

The source PR and merge commit will be recorded in the pull-request history.
No image, secret, database, namespace, service, or persistent volume is
deleted by this change.

## Live Verification

Before the source change, the live Argo application already carried a bounded
`skip-reconcile` containment annotation. Platform scaled
`openproject-web`, `openproject-worker-default`, `openproject-hocuspocus`, and
`openproject-memcached` to zero and confirmed that the namespace had no pods.
Linux available memory rose from about 13 GiB to 16 GiB and the Windows
`vmmemWSL` working set fell from about 16.6 GiB to 11.1 GiB, with zero swap and
zero Linux memory pressure.

## Follow-Up Actions

After merge, reconcile the `platform-root-prod` and `openproject` applications
when Argo repository access is healthy and confirm all OpenProject application
deployments remain at zero. Reactivation requires a reviewed revert of the
replica and Hocuspocus values followed by `make openproject-apply`.
