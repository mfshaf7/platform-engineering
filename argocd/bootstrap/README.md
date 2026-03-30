# Argo Bootstrap

Bootstrap order:

1. install Kubernetes
2. install Argo CD into `argocd`
3. apply [install.yaml](install.yaml)
4. apply the platform root that matches the target scope:
   - [../apps/root-shared.yaml](../apps/root-shared.yaml)
   - [../apps/root-stage.yaml](../apps/root-stage.yaml)
   - [../apps/root-prod.yaml](../apps/root-prod.yaml)
5. verify the relevant `platform-root-*` application syncs the target
   environment applications
