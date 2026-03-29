# Artifact Build Standard

Platform-managed runtime images should be built from:

- pinned source repository SHAs
- versioned environment manifests
- documented build arguments
- immutable registry destinations

For the OpenClaw gateway, the build path currently reuses the deployment repo's
bundled-image process, but release authority lives in the platform repo.
