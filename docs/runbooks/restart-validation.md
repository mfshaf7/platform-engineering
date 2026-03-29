# Restart Validation

Validate after restart or logon:

- `make verify-platform-host` passes
- Windows bootstrap executed
- WSL services are enabled and active
- bridge health endpoint is reachable
- recovery health endpoint is reachable
- cluster workloads are healthy
- Argo CD is synced
- Prometheus targets are healthy
