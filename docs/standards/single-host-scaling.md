# Single-Host Scaling

## Purpose

This platform currently runs on a single host and a single local `k3s` node.

That means most new shared components and product integrations should not
default to multi-replica runtime shapes. Extra replicas on the same machine
consume memory, complicate restart behavior, and can create fake high-
availability posture without giving real host-level resilience.

## Default Rule

For new platform-managed runtime surfaces, default to `1` for replica-bearing
settings unless a higher count is explicitly justified.

This applies to new declarations such as:

- Kubernetes `replicas`
- Helm `replicaCount`
- autoscaling `minReplicas`
- other platform-owned replica-count inputs that become desired runtime state

This rule applies to both:

- shared components
- product integration runtimes

## Allowed Exception Shape

Use more than `1` replica only when the workload cannot reasonably operate as a
singleton on the current host.

If that happens, record the exception in:

- `environments/shared/single-host-scaling-policy.yaml`

Every exception must include:

- the exact Git-managed file
- the exact YAML path
- the maximum allowed replica count
- the reason the singleton default is not sufficient

Implicit or conversational exceptions are not valid.

## Contract Expectations

When a product or component has an active runtime contract, publish the current
runtime profile there, including:

- deployment replica count
- worker replica count when relevant
- any explicit scaling exception reference when the default is exceeded

## Validation Rule

This policy is enforced by:

- `python3 scripts/validate_single_host_scaling.py --repo-root .`

`make validate` must fail if a new product or component lands with a
multi-replica runtime declaration and no recorded exception.
