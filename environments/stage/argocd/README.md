# Stage Environment

This directory holds the staged Argo CD overlays and application set for the
non-production rehearsal environment.

The stage environment is intended to:

- validate Argo CD reconciliation
- validate Helm values against a second namespace set
- rehearse image/version promotion before touching `prod`

Stage can be suspended when production is established by removing the stage Argo
applications from `kustomization.yaml`. Resume restores every `*.yaml`
application manifest in this directory, which lets operators bring the entire
stage environment back only when they need to rehearse or test again.
