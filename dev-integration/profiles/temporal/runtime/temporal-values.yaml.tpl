fullnameOverride: temporal

additionalLabels:
  dev-integration-profile: temporal
  dev-integration-operator: __OPERATOR__

serviceAccount:
  create: false
  name: temporal-runtime

server:
  image:
    repository: __TEMPORAL_SERVER_REPOSITORY__
    tag: __TEMPORAL_SERVER_TAG__
    pullPolicy: IfNotPresent
  replicaCount: 1
  metrics:
    annotations:
      enabled: true
  config:
    logLevel: info
    persistence:
      defaultStore: default
      visibilityStore: visibility
      numHistoryShards: 4
      datastores:
        default:
          sql:
            createDatabase: false
            manageSchema: true
            pluginName: postgres12
            databaseName: temporal
            connectAddr: temporal-postgresql:5432
            connectProtocol: tcp
            user: temporal
            existingSecret: temporal-postgresql
            secretKey: password
            maxConns: 20
            maxIdleConns: 10
            maxConnLifetime: 1h
        visibility:
          sql:
            createDatabase: false
            manageSchema: true
            pluginName: postgres12
            databaseName: temporal_visibility
            connectAddr: temporal-postgresql:5432
            connectProtocol: tcp
            user: temporal
            existingSecret: temporal-postgresql
            secretKey: password
            maxConns: 20
            maxIdleConns: 10
            maxConnLifetime: 1h
    metrics:
      prometheus:
        timerType: histogram
        listenAddress: 0.0.0.0:9090
    namespaces:
      create: true
      namespace:
        - name: __TEMPORAL_NAMESPACE__
          retention: 7d
  frontend:
    service:
      type: ClusterIP
  resources:
    requests:
      cpu: 100m
      memory: 256Mi
    limits:
      cpu: 1
      memory: 1Gi

admintools:
  enabled: true
  image:
    repository: __TEMPORAL_ADMIN_REPOSITORY__
    tag: __TEMPORAL_ADMIN_TAG__
    pullPolicy: IfNotPresent

web:
  enabled: true
  image:
    repository: __TEMPORAL_UI_REPOSITORY__
    tag: __TEMPORAL_UI_TAG__
    pullPolicy: IfNotPresent
  service:
    type: ClusterIP
  ingress:
    enabled: false
  additionalEnv:
    - name: TEMPORAL_UI_ENABLED
      value: "true"
  resources:
    requests:
      cpu: 50m
      memory: 128Mi
    limits:
      cpu: 500m
      memory: 512Mi

schema:
  useHelmHooks: true
  backoffLimit: 20

shims:
  dockerize: false
  elasticsearchTool: false
