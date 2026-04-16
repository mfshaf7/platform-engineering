# External Secrets Access

There is no shared browser UI for External Secrets Operator.

Operator access is through Kubernetes inspection:

```bash
k3s kubectl -n external-secrets get pods
k3s kubectl get externalsecret -A
k3s kubectl get secretstore,clustersecretstore -A
```
