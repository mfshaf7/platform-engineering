# Network Trust Boundaries

## Cluster Side

- ingress and service exposure should be explicit
- observability endpoints should be limited to approved namespaces and monitors

## Host Side

- bridge and recovery endpoints should be reachable only from intended runtime paths
- host-control networking should be documented and auditable

## Cross-Boundary Rule

Traffic between runtime workloads and host-integrated services is a governed boundary,
not an implicit local shortcut.
