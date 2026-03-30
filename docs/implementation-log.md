# Implementation Log

## Purpose

This log records the steps taken while introducing the platform repository.

It is intentionally concise and operator-readable.

## Step Log

1. Created a dedicated platform repository and renamed it to `platform-engineering`
   before the first upstream push so the repo identity matched the broader
   long-term scope.
2. Evaluated the initial GitOps stack and replaced the earlier lightweight GitOps-first
   direction with a more cloud-aligned stack:
   - GitHub
   - GitHub Actions
   - GHCR
   - Terraform
   - Kubernetes
   - Argo CD
   - Helm
   - External Secrets Operator
   - Prometheus
   - Grafana
   - Ansible
   - `systemd` in WSL
3. Defined the control-plane split between source repos, platform repo, cluster
   runtime, and host runtime.
4. Added an environment-manifest model so production can pin approved versions.
5. Added Argo CD app-of-apps scaffolding for runtime, observability, and
   secret-management layers.
6. Added Helm chart scaffolding for a runtime workload and a platform version
   ConfigMap.
7. Added Terraform scaffolding for cluster bootstrap variables and module
   boundaries.
8. Added Ansible scaffolding for Kubernetes node preparation and WSL host
   service configuration.
9. Expanded the repo layout to include observability, policies, security, and
   product-integration areas so the repo reflects a true platform engineering
   function instead of only a deployment folder.
10. Added environment-specific Helm value overlays, Argo bootstrap assets,
    first-pass observability rules and dashboard scaffolding, and a dedicated
    security-posture workflow to make the repository closer to an operational
    baseline instead of a documentation-only shell.
11. Added operator entrypoints in `Makefile` plus clearer CI/CD and GitOps
    standards so the repo now documents not just structure, but expected
    delivery behavior.
12. Replaced generic host-stack placeholders with concrete WSL host variables,
    environment files, systemd units, and bootstrap documentation aligned to the
    existing `openclaw-host-bridge` runtime and Windows scheduled-task model.
13. Expanded Terraform from a simple VM placeholder to a concrete environment
    contract that now records cluster namespaces, runtime image coordinates, and
    host-integration inputs.
14. Promoted `stage` from placeholder status to a first-class GitOps environment
    with its own Argo applications, value overlays, and promotion runbook.
15. Added the first governed gateway artifact build workflow so environment
    version pins now drive the bundled-image build path instead of leaving image
    creation as a purely local deployment script.
16. Replaced the placeholder `k3s` node role with a real `k3s` installer and
    service bootstrap path so the platform repo can bring up the cluster
    control plane through Ansible rather than only describing it.
17. Added a fresh-WSL bootstrap path with `systemd` configuration, WSL package
    prerequisites, and required host-bridge runtime-path validation so an
    unreliable distro can be replaced with a reproducible platform-managed one.
18. Tightened the WSL host bootstrap path with explicit validation for the
    local Node runtime and secret-bearing config files so a fresh distro fails
    early when required operator-created inputs are still missing.
19. Promoted the Windows scheduled-task bootstrap into a rendered platform
    artifact so the new-distro flow can produce a concrete PowerShell launcher
    instead of relying on an implicit template and manual reconstruction.
20. Added a post-bootstrap host verification playbook and entrypoint so the new
    WSL distro can prove `systemd`, host stack services, rendered Windows
    bootstrap artifact, and `k3s` health before any migration cutover touches
    the live runtime.
21. Added an explicit `Platform-Core` migration runbook covering parallel
    bring-up, controlled cutover, Docker-backed old-runtime shutdown, cleanup,
    and rollback so disruptive migration steps are governed instead of ad hoc.
22. Added a pre-cutover evidence capture playbook so host status, Kubernetes
    health, and any remaining Docker-backed runtime state can be recorded
    before disruptive migration steps begin.
23. Added a rendered cutover record template so migration operators can log
    exactly what was stopped, started, restored, and cleaned up during the
    `Platform-Core` cutover instead of relying on free-form notes.
24. Added a rendered cutover command inventory so the current legacy Docker
    runtime can be mapped to explicit stop, restore, and cleanup commands
    before the migration reaches the disruptive cutover phase.
25. Added a rendered Windows cutover inventory so legacy scheduled-task names,
    disable/enable actions, and restore steps are explicit before the migration
    reaches the Windows-side cutover phase.
26. Added a rendered runtime reachability checklist so post-cutover validation
    tests the actual gateway-to-bridge and gateway-to-recovery path instead of
    only checking local host-side health from WSL.
27. Added a rendered runtime-container verification checklist so operators have
    exact `docker exec` commands for bridge health, recovery health, authenticated
    bridge operations, and authenticated recovery probes from the real gateway
    context after cutover.
28. Added Windows task evidence capture so the migration records the current
    legacy scheduled-task action, last-run result, and path-coupling failure
    mode before Windows-side cutover begins.
29. Recorded the interrupted `Platform-Core` first-run recovery checkpoint and
    added an explicit operator pickup prompt for the `wsl.exe --shutdown`
    recovery step so the next live action is documented before a possible
    session disconnect.
30. Recovered the broken Windows Docker Desktop engine path, restored
    `Platform-Core` WSL integration, and re-established direct `docker inspect`
    against the legacy gateway container so the live mount list could be
    verified instead of inferred.
31. Corrected the stale platform host-stack path assumptions by repointing the
    managed OpenClaw config and Node paths at the real `mfshaf7` home in
    `Platform-Core`, repaired Windows portproxy forwarding for `48721` and
    `48722`, and revalidated bridge and recovery reachability from the legacy
    gateway container.

## Next Implementation Steps

These are the next concrete steps after scaffolding:

1. connect real registry coordinates and GitHub environments
2. add real secret-store integration for External Secrets
3. add runtime version reporting from the runtime and host diagnostics surfaces
4. add Prometheus alert rules and Grafana dashboards tailored to the first product
5. perform a staged non-production bootstrap before touching live production
32. Repaired the stage `k3s` Argo bootstrap, AppProject policy, and observability
    deployment path so `Platform-Core` could host a real OpenClaw workload
    instead of only core cluster services.
33. Recovered the stage `k3s` gateway runtime by importing the working
    `openclaw:local` image, removing stale `host-control` plugin config from the
    `k3s` config source, matching the working Docker startup shape, and raising
    the pod memory envelope so the gateway now serves health checks and
    authenticated bridge and recovery operations from `Platform-Core`.
34. Completed the direct host cutover by stopping the legacy Docker gateway,
    moving Windows `127.0.0.1`, `::1`, and `localhost` gateway traffic onto the
    `Platform-Core` `k3s` runtime, and revalidating `/healthz` from both Windows
    and the distro host.
35. Published the source-backed gateway chart and stage value changes, pushed
    the authoritative repo state to GitHub, and confirmed Argo reconciled the
    gateway application to `Synced` and `Healthy`.
36. Corrected the host-network rollout behavior by switching the gateway
    Deployment strategy to `Recreate` so a second host-network pod would not
    deadlock on the single-node `Platform-Core` host.
37. Migrated the legacy Ubuntu repo set and OpenClaw workspace into
    `Platform-Core` under `/home/mfshaf7/projects` and
    `/home/mfshaf7/.openclaw/workspace` so the runtime, build inputs, and
    operator repos now live in the target distro.
38. Reconciled the moved `platform-engineering` checkout by preserving the raw
    migrated legacy copy as a dated backup and replacing the active working copy
    with a clean clone of the pushed authoritative repository state.
39. Hardened `Platform-Core` logon persistence after repo migration by
    repointing the managed host paths at `/home/mfshaf7/projects`, switching the
    Windows scheduled task to start the platform-managed `systemd` target
    directly, tightening host verification to require active bridge and recovery
    units, and revalidating Windows localhost gateway health after the updated
    task ran successfully.
40. Recovered the Argo CD repo-server after the persistence test left it in a
    stale init-container crash loop, refreshed the affected applications, and
    re-established `Synced` and `Healthy` stage status at platform revision
    `6ca129c4bcc741b8cccc1697051064b311171412`.
41. Disabled the stale Windows logon tasks `OpenClaw Node` and
    `OpenClawPcControlBridge` after confirming they were legacy startup paths
    outside the current platform model and were either failing or targeting
    obsolete launchers.
42. Removed the retired Windows tasks `OpenClawHostStack`, `OpenClaw Node`,
    and `OpenClawPcControlBridge`, deleted the obsolete `node.cmd` launcher,
    and removed the unused `/opt/openclaw-host-bridge` and
    `/opt/platform-engineering` repo copies after revalidating that the live
    Platform-Core stack depended only on `/home/mfshaf7/projects`.
43. Refreshed the stage Argo applications after the final cleanup publish so
    the live gateway, root, and platform-version applications reconciled to
    platform revision `977a34c31653c73f072aeb3ded4d7fdcdffc4e3c`.
44. Removed the rollback-only `platform-engineering` backup directories after
    the final cut so `/home/mfshaf7/projects` now contains only the active
    authoritative repos.
45. Removed the legacy `Ubuntu` WSL distro, made `Platform-Core` the default
    WSL distribution, and replaced the repo's implicit `kubectl` dependency
    with the native `k3s kubectl` path so host verification no longer depends
    on Docker Desktop CLI tooling.
46. Pinned the stage environment metadata to the current Telegram,
    host-bridge, isolated-deployment, and platform-engineering source SHAs and
    corrected the recorded WSL distribution to `Platform-Core` so the published
    environment contract now matches the live post-cutover runtime instead of
    retaining placeholder values from the migration period.
47. Formalized the current gateway artifact contract by documenting that stage
    still intentionally runs `openclaw:local` during the post-cutover soak,
    that production remains a GHCR-backed path, and that the governed build
    workflow must now reject placeholder source refs before building.
48. Replaced the gateway build workflow's workstation-style `docker build`
    dependency with a CI-owned Buildx/GHCR path, added immutable source-bundle
    tagging plus OCI metadata, made the gateway chart digest-aware, and aligned
    the environment contracts so future stage and production promotion can use
    digest-backed image references instead of mutable local tags.
49. Recovered the real gateway base-image provenance from the imported
    `openclaw:local` runtime image and replaced the unpublished
    `openclaw:stable-preview` placeholder with the official upstream GHCR base
    image `ghcr.io/openclaw/openclaw:latest` so the CI build can pull a real
    source image instead of depending on a legacy local-only tag.
50. Built the first governed stage gateway artifact in GitHub Actions and
    recorded the resulting immutable GHCR image reference in the stage
    environment contract so stage can move from `openclaw:local` to a
    digest-backed CI-produced image.
51. Replaced the placeholder environment promotion workflow with a
    digest-based stage-to-prod promotion path that copies approved image and
    source pins into the prod contract, validates the resulting manifests in
    CI, and opens a reviewable production promotion pull request instead of
    mutating `main` directly.
52. Adjusted the prod Argo composition for single-cluster coexistence with
    stage by leaving the shared `openclaw-platform` AppProject under one root
    only and disabling the prod `prometheus-node-exporter` DaemonSet, which
    otherwise cannot schedule alongside the stage exporter on the same
    single-node host due to host port `9100` contention.
