# Trust Boundaries

## Core Boundaries

- Source code is trusted only after review and artifact publication.
- Cluster workloads are trusted only when reconciled from approved Git state.
- Host-control actions are mediated through the bridge and recovery services.
- Secrets must enter workloads through runtime injection, not plaintext commits.
- Emergency live patches are treated as incidents, not normal operations.
