# Argo Bootstrap

Bootstrap order:

1. install Kubernetes
2. install Argo CD into `argocd`
3. apply [install.yaml](install.yaml)
4. apply [../apps/root.yaml](../apps/root.yaml)
5. verify `openclaw-root` syncs the target environment applications
