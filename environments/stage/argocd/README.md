# Stage Environment

This directory holds the staged Argo CD overlays and application set for the
non-production rehearsal environment.

The stage environment is intended to:

- validate Argo CD reconciliation
- validate Helm values against a second namespace set
- rehearse image/version promotion before touching `prod`
