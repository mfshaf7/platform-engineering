# Stage Environment

This directory holds the staged Argo CD overlays and application set for the
non-production rehearsal environment.

The stage environment is intended to:

- validate Argo CD reconciliation
- validate Helm values against a second namespace set
- rehearse image/version promotion before touching `prod`

Stage can still be fully suspended with the `suspend-sentinel-configmap.yaml`
placeholder, but lifecycle operations are now component-aware rather than
all-or-nothing.

Available stage components:

- `gateway`
- `secrets`
- `version`
- `observability`
- `dashboards`

Dependency rules:

- resuming `gateway` also resumes `secrets` and `version`
- resuming `dashboards` also resumes `observability`
- suspending `secrets` or `version` also suspends `gateway`
- suspending `observability` also suspends `dashboards`

That lets operators bring back only the exact stage component they are working
on, instead of disturbing healthy production-adjacent systems with a full stage
resume.
