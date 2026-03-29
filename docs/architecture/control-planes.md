# Control Planes

## Purpose

This document isolates the ownership model behind the platform.

## Source Control Plane

Source repositories own code, tests, and component-local documentation.

## Platform Control Plane

`platform-engineering` owns:

- approved environment versions
- deployment standards
- release governance
- platform policy

## Cluster Control Plane

Argo CD and Kubernetes own:

- declared cluster workloads
- reconciliation status
- sync and health reporting

## Host Control Plane

Ansible, `systemd`, and Windows bootstrap own:

- bridge lifecycle
- recovery lifecycle
- machine-level runtime contracts
