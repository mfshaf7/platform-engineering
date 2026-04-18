# Operator Orchestration Service Access

There is no shared browser UI for `operator-orchestration-service`.

## WSL Fallback

```bash
k3s kubectl -n operator-orchestration-service port-forward svc/operator-orchestration-service 8080:8080
```

Then use:

- `http://127.0.0.1:8080/healthz`
- `http://127.0.0.1:8080/readyz`
- `http://127.0.0.1:8080/version`

## Credentials

- OpenProject token source:
  - Vault path `kv/components/operator-orchestration-service/prod/openproject`
- caller-auth shared secret source:
  - Vault path `kv/components/operator-orchestration-service/shared/runtime`

Do not surface either credential in Telegram repo config or Git-tracked docs.
