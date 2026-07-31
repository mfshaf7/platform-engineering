apiVersion: v1
kind: ServiceAccount
metadata:
  name: temporal-runtime
  namespace: __KUBERNETES_NAMESPACE__
  labels:
    app.kubernetes.io/part-of: temporal
    orchestration.workspace/identity: temporal-runtime
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: temporal-oos-worker
  namespace: __KUBERNETES_NAMESPACE__
  labels:
    app.kubernetes.io/part-of: temporal
    orchestration.workspace/identity: oos-workflow-worker
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: temporal-wgcf-activity
  namespace: __KUBERNETES_NAMESPACE__
  labels:
    app.kubernetes.io/part-of: temporal
    orchestration.workspace/identity: wgcf-activity-worker
automountServiceAccountToken: false
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: temporal-diagnostic
  namespace: __KUBERNETES_NAMESPACE__
  labels:
    app.kubernetes.io/part-of: temporal
    orchestration.workspace/identity: human-diagnostic
automountServiceAccountToken: false
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: temporal-default-deny
  namespace: __KUBERNETES_NAMESPACE__
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: temporal-dns-egress
  namespace: __KUBERNETES_NAMESPACE__
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: temporal-server-mesh
  namespace: __KUBERNETES_NAMESPACE__
spec:
  podSelector:
    matchExpressions:
      - key: app.kubernetes.io/component
        operator: In
        values:
          - frontend
          - history
          - matching
          - worker
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchExpressions:
              - key: app.kubernetes.io/component
                operator: In
                values:
                  - frontend
                  - history
                  - matching
                  - worker
  egress:
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: temporal-postgresql
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - podSelector:
            matchExpressions:
              - key: app.kubernetes.io/component
                operator: In
                values:
                  - frontend
                  - history
                  - matching
                  - worker
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: temporal-postgresql-access
  namespace: __KUBERNETES_NAMESPACE__
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: temporal-postgresql
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchExpressions:
              - key: app.kubernetes.io/component
                operator: In
                values:
                  - frontend
                  - history
                  - matching
                  - worker
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: database
      ports:
        - protocol: TCP
          port: 5432
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: temporal-support-frontend
  namespace: __KUBERNETES_NAMESPACE__
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: frontend
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchExpressions:
              - key: app.kubernetes.io/component
                operator: In
                values:
                  - web
                  - admintools
                  - database
      ports:
        - protocol: TCP
          port: 7233
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: temporal-support-egress
  namespace: __KUBERNETES_NAMESPACE__
spec:
  podSelector:
    matchExpressions:
      - key: app.kubernetes.io/component
        operator: In
        values:
          - web
          - admintools
  policyTypes:
    - Egress
  egress:
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: frontend
      ports:
        - protocol: TCP
          port: 7233
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: temporal-schema-job-egress
  namespace: __KUBERNETES_NAMESPACE__
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: database
  policyTypes:
    - Egress
  egress:
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/name: temporal-postgresql
      ports:
        - protocol: TCP
          port: 5432
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: frontend
      ports:
        - protocol: TCP
          port: 7233
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: temporal-admitted-worker-egress
  namespace: __KUBERNETES_NAMESPACE__
spec:
  podSelector:
    matchExpressions:
      - key: orchestration.workspace/identity
        operator: In
        values:
          - oos-workflow-worker
          - wgcf-activity-worker
  policyTypes:
    - Egress
  egress:
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/component: frontend
      ports:
        - protocol: TCP
          port: 7233
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: temporal-admitted-worker-frontend
  namespace: __KUBERNETES_NAMESPACE__
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/component: frontend
      app.kubernetes.io/part-of: temporal
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchExpressions:
              - key: orchestration.workspace/identity
                operator: In
                values:
                  - oos-workflow-worker
                  - wgcf-activity-worker
      ports:
        - protocol: TCP
          port: 7233
