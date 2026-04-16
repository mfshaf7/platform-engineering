# Architecture Overview

## Purpose

This document defines the target end-to-end platform for managed runtime
delivery.

The goal is to remove ambiguity about:

- where release authority lives
- where runtime reconciliation happens
- how host-integrated services are owned
- how security and observability fit into the operating model

## Control Planes

There are four control planes:

| Control plane | Owner | Responsibility |
| --- | --- | --- |
| Source control | Component repos | Code, tests, repo-local docs |
| Platform control | `platform-engineering` | Approved versions, deployment manifests, standards, policy |
| Cluster control | Argo CD + Kubernetes | Reconciliation of workloads and shared services |
| Host control | Ansible + `systemd` + Windows bootstrap | Bridge and recovery lifecycle on the host side |

## Runtime Zones

### 1. Source zone

- product repositories such as `openclaw-telegram-enhanced`
- host integration repositories such as `openclaw-host-bridge`
- active image composition repositories such as `openclaw-runtime-distribution`
- reference architecture repositories such as `openclaw-isolated-deployment`

These repositories define the components that will be packaged and promoted.

### 2. Artifact zone

- GHCR-published runtime images
- chart packages
- build metadata, SBOMs, and attestations

Production consumes immutable artifacts from this zone.

### 3. Cluster zone

- isolated Ubuntu VM
- Kubernetes control plane
- Argo CD
- External Secrets Operator
- Prometheus
- Grafana
- product workloads

This zone owns the application runtime.

### 4. Host-integration zone

- Windows workstation
- WSL distribution
- `systemd` units:
  - `openclaw-host-bridge.service`
  - `openclaw-host-recovery.service`
- Windows Task Scheduler bootstrapping WSL after restart or logon

This zone owns host-integrated actions that should remain outside Kubernetes.

For OpenClaw host control, the supported environment split is:

- prod bridge always on through `openclaw-host-stack.target`
- stage bridge provisioned separately and started only for active stage test
  windows
- stage suspension should stop the stage bridge so an extra Windows-visible host
  listener is not left up unnecessarily

## Trust Boundaries

- product runtime logic is bundled into immutable artifacts
- cluster workloads are reconciled only from approved Git state
- host-control actions cross a typed boundary to the host bridge
- bridge and recovery remain outside Kubernetes because they manage host state
- secrets are delivered at runtime, not committed in plaintext
- shared control-plane assets remain product-neutral
- product-specific runtime contracts live under `products/<product>/`

## Why This Stack

### Argo CD

Argo CD provides:

- application-centric GitOps reconciliation
- visible sync and drift state
- a better demo and operator experience than a controller-only model
- a clean app-of-apps pattern for environment composition

### Terraform

Terraform provides:

- environment bootstrap inputs
- cluster prerequisites
- a cloud-aligned infrastructure story

### Helm

Helm provides:

- workload packaging
- values-based environment customization
- reusable chart boundaries for multiple products

### External Secrets Operator

External Secrets Operator provides:

- runtime secret injection into Kubernetes workloads
- separation between secret material and deployment manifests
- a more cloud-native secret model than plaintext config

### Prometheus and Grafana

Prometheus and Grafana provide:

- workload health visibility
- release verification dashboards
- operational evidence for demonstrations and incident review

### Ansible

Ansible remains the right tool for:

- WSL host configuration
- package installation
- `systemd` unit deployment
- Windows bootstrap integration
- mixed-OS idempotent configuration
