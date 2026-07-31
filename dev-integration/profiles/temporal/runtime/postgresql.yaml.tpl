apiVersion: v1
kind: Namespace
metadata:
  name: __KUBERNETES_NAMESPACE__
  labels:
    app.kubernetes.io/part-of: temporal
    dev-integration-profile: temporal
    dev-integration-operator: __OPERATOR__
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: temporal-postgresql
  namespace: __KUBERNETES_NAMESPACE__
  labels:
    app.kubernetes.io/part-of: temporal
automountServiceAccountToken: false
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: temporal-postgresql-init
  namespace: __KUBERNETES_NAMESPACE__
  labels:
    app.kubernetes.io/part-of: temporal
data:
  00-create-databases.sh: |
    #!/usr/bin/env sh
    set -eu

    psql --set ON_ERROR_STOP=1 \
      --username "$POSTGRES_USER" \
      --dbname postgres \
      --set app_user="$TEMPORAL_APP_USER" \
      --set app_password="$TEMPORAL_APP_PASSWORD" <<'SQL'
    SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'app_user', :'app_password')
    WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user')
    \gexec
    SELECT format('CREATE DATABASE temporal OWNER %I', :'app_user')
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal')
    \gexec
    SELECT format('CREATE DATABASE temporal_visibility OWNER %I', :'app_user')
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'temporal_visibility')
    \gexec
    SQL
---
apiVersion: v1
kind: Service
metadata:
  name: temporal-postgresql
  namespace: __KUBERNETES_NAMESPACE__
  labels:
    app.kubernetes.io/name: temporal-postgresql
    app.kubernetes.io/part-of: temporal
spec:
  type: ClusterIP
  selector:
    app.kubernetes.io/name: temporal-postgresql
    app.kubernetes.io/part-of: temporal
  ports:
    - name: postgresql
      port: 5432
      targetPort: postgresql
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: temporal-postgresql
  namespace: __KUBERNETES_NAMESPACE__
  labels:
    app.kubernetes.io/name: temporal-postgresql
    app.kubernetes.io/part-of: temporal
spec:
  replicas: 1
  serviceName: temporal-postgresql
  selector:
    matchLabels:
      app.kubernetes.io/name: temporal-postgresql
      app.kubernetes.io/part-of: temporal
  template:
    metadata:
      labels:
        app.kubernetes.io/name: temporal-postgresql
        app.kubernetes.io/part-of: temporal
        dev-integration-profile: temporal
    spec:
      serviceAccountName: temporal-postgresql
      automountServiceAccountToken: false
      terminationGracePeriodSeconds: 30
      containers:
        - name: postgresql
          image: __POSTGRESQL_IMAGE__
          imagePullPolicy: IfNotPresent
          env:
            - name: POSTGRES_USER
              valueFrom:
                secretKeyRef:
                  name: temporal-postgresql
                  key: admin_username
            - name: POSTGRES_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: temporal-postgresql
                  key: admin_password
            - name: TEMPORAL_APP_USER
              valueFrom:
                secretKeyRef:
                  name: temporal-postgresql
                  key: username
            - name: TEMPORAL_APP_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: temporal-postgresql
                  key: password
            - name: POSTGRES_DB
              value: postgres
            - name: PGDATA
              value: /var/lib/postgresql/data/pgdata
          ports:
            - name: postgresql
              containerPort: 5432
          readinessProbe:
            exec:
              command:
                - sh
                - -ec
                - pg_isready -U "$POSTGRES_USER" -d postgres
            initialDelaySeconds: 5
            periodSeconds: 5
            timeoutSeconds: 3
          livenessProbe:
            exec:
              command:
                - sh
                - -ec
                - pg_isready -U "$POSTGRES_USER" -d postgres
            initialDelaySeconds: 30
            periodSeconds: 10
            timeoutSeconds: 3
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 1Gi
          securityContext:
            allowPrivilegeEscalation: false
            seccompProfile:
              type: RuntimeDefault
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
            - name: init
              mountPath: /docker-entrypoint-initdb.d
              readOnly: true
      volumes:
        - name: init
          configMap:
            name: temporal-postgresql-init
            defaultMode: 0550
  volumeClaimTemplates:
    - metadata:
        name: data
        labels:
          app.kubernetes.io/name: temporal-postgresql
          app.kubernetes.io/part-of: temporal
      spec:
        accessModes:
          - ReadWriteOnce
        storageClassName: local-path
        resources:
          requests:
            storage: 10Gi
