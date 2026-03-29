# GitOps Standard

Argo CD is the reconciler for cluster-side desired state.

Rules:

- environment intent is expressed under `environments/`
- application definitions are declared in Argo manifests
- runtime drift is measured against approved Git state
- live mutation is an exception path, not a normal operational tool
