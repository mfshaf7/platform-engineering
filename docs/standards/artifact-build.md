# Artifact Build Standard

Platform-managed runtime images should be built from:

- pinned source repository SHAs
- versioned environment manifests
- documented build arguments
- immutable registry destinations

For the OpenClaw gateway, current governed builds use
`openclaw-runtime-distribution` as the build/composition repo, while release
authority lives in the platform repo.

For a fixed pinned source bundle, the resulting gateway artifact should be
environment-neutral. Stage and prod deployment differences belong in the
environment contract and runtime values, not in the image identity itself.
