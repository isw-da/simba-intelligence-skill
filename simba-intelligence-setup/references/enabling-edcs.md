# Enabling Additional EDC Connectors

The SI Helm chart bundles 43+ External Data Connector (EDC) images from
the legacy Zoomdata/Composer architecture. Only PostgreSQL and Python
are enabled by default. All others are available but disabled.

---

## Architecture

The Composer subchart has a single template (`edc-deployment.yaml`)
that iterates over all entries in `.Values.edc`, checks the `enabled`
flag, and creates a StatefulSet for each enabled connector. A matching
configmap template (`edc-configmap.yaml`) writes properties from the
`properties` map into the pod's configuration.

**Critical: The subchart alias is `discovery`, not `logi-symphony`.**
The parent chart's `Chart.yaml` defines:

```yaml
dependencies:
- alias: discovery
  name: composer
```

All EDC overrides must go under `discovery.edc.<connector>`, not
`logi-symphony.edc.<connector>`.

---

## Listing available connectors

```bash
helm get values <release> -n <namespace> -a | grep 'repository: zoomdata-edc' | sort
```

As of chart version 25.4.0, the available EDCs include (among others):
bigquery, clickhouse, databricks, db2, denodo, dremio, drill,
elasticsearch-7.0, elasticsearch-8.0, hdfs, hive, impala, jira,
memsql, mongo, mssql, mysql, opensearch-2.0, oracle, postgresql,
redshift, s3, salesforce, saphana, snowflake, sparksql, teradata,
trino, vertica.

---

## Enabling a connector (simple case)

For connectors that bundle their own JDBC driver (PostgreSQL, MySQL,
Snowflake, BigQuery, S3, SparkSQL, etc.):

```bash
cat > /tmp/enable-connector.yaml << 'EOF'
discovery:
  edc:
    <connector-name>:
      enabled: true
EOF

helm upgrade <release> <chart-path> \
  -n <namespace> \
  --reuse-values \
  -f /tmp/enable-connector.yaml
```

Always include any previously enabled connectors in the override file
to prevent them being disabled. `--reuse-values` merges with the last
user values, but explicit is safer.

Wait for the new pod:

```bash
kubectl -n <namespace> get pods | grep edc-<connector-name>
kubectl -n <namespace> wait --for=condition=Ready \
  pod/si-discovery-edc-<connector-name>-0 --timeout=120s
```

Verify registration in Composer:

```bash
curl -s http://localhost:<discovery-port>/discovery/api/connectors \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/vnd.composer.v3+json" | \
  python3 -m json.tool | grep '"name"'
```

---

## Enabling a connector that needs an external JDBC driver

Some connectors (Oracle, Teradata, Redshift, Databricks, Elasticsearch,
Jira, MemSQL) require externally provided JDBC drivers due to licensing.
These connectors mount a shared PVC at
`/opt/zoomdata/lib/edc-<name>/drivers/`.

### Step 1: Create the shared PVC (once per cluster)

```bash
cat <<'EOF' | kubectl apply -n <namespace> -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: composer-shared-volume
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
EOF
```

### Step 2: Copy the driver JAR into the PVC

Spin up a temporary pod that mounts the volume:

```bash
kubectl -n <namespace> run driver-loader --image=busybox --restart=Never \
  --overrides='{
    "spec": {
      "containers": [{
        "name": "driver-loader",
        "image": "busybox",
        "command": ["sleep", "300"],
        "volumeMounts": [{
          "name": "shared",
          "mountPath": "/drivers"
        }]
      }],
      "volumes": [{
        "name": "shared",
        "persistentVolumeClaim": {
          "claimName": "composer-shared-volume"
        }
      }]
    }
  }'

kubectl -n <namespace> wait --for=condition=Ready pod/driver-loader --timeout=60s
```

Create the directory and copy the driver:

```bash
kubectl -n <namespace> exec driver-loader -- \
  mkdir -p /drivers/edc-<connector-name>/drivers

kubectl cp /path/to/driver.jar \
  <namespace>/driver-loader:/drivers/edc-<connector-name>/drivers/driver.jar

kubectl -n <namespace> exec driver-loader -- \
  ls -la /drivers/edc-<connector-name>/drivers/
```

Clean up:

```bash
kubectl -n <namespace> delete pod driver-loader
```

### Step 3: Enable the connector

Same as the simple case. The chart's default values already include the
`extraVolumeMounts` and `extraVolumes` config for connectors that need
external drivers.

### Driver sources

| Connector | Driver | Source |
|---|---|---|
| Oracle | ojdbc11.jar | Maven Central (no login required): `https://repo1.maven.org/maven2/com/oracle/database/jdbc/ojdbc11/` |
| Teradata | terajdbc4.jar | Teradata Downloads (login required) |
| Databricks | DatabricksJDBC42.jar | Databricks website |
| Redshift | redshift-jdbc42.jar | Maven Central |

---

## Adding custom properties to an EDC

The configmap template reads from the `properties` map:

```yaml
discovery:
  edc:
    <connector-name>:
      enabled: true
      properties:
        some.spark.property: "value"
        another.property: "value"
```

Properties are written into the EDC's configmap and loaded at startup.
Confirmed working for Spark-based EDCs (S3, SparkSQL) where Hadoop/S3A
configuration is needed.

---

## Adding environment variables to an EDC

The deployment template supports `extraEnvs` (not `extraEnvVars`):

```yaml
discovery:
  edc:
    <connector-name>:
      enabled: true
      extraEnvs:
        - name: AWS_ACCESS_KEY_ID
          value: "your-key"
        - name: AWS_SECRET_ACCESS_KEY
          value: "your-secret"
```

Verify after deployment:

```bash
kubectl -n <namespace> exec si-discovery-edc-<connector-name>-0 -- env | grep AWS
```

---

## Known issues and open questions

### S3 EDC credential validation

The S3 EDC uses Spark under the hood (Apache Spark local mode) to read
files from S3 paths. Spark config properties for S3A
(`spark.hadoop.fs.s3a.*`) are successfully loaded via the `properties`
Helm value, and AWS env vars are injected via `extraEnvs`. However, the
EDC's own pre-validation step (before Spark is invoked) checks for S3
credentials through a separate internal mechanism and fails with
"Missing S3 Access Key and Secret Key." The connection can be created
via API (bypassing UI validation) but schema discovery also fails at
the same validation step.

**Status:** Open. Needs engineering input (Leo) on how the S3 EDC
expects credentials at the validation layer.

**Workaround for demos:** Use real AWS S3 with IAM credentials, or
park S3 and use Oracle + PostgreSQL for the federated query story.

### No generic JDBC EDC (workaround available)

The chart does not include a generic JDBC connector. Every EDC is
purpose-built for a specific database type. To connect to a new
database type (e.g. Microsoft Fabric via the Simba Fabric JDBC driver),
a new EDC image would need to be created by engineering, or the
SparkSQL EDC may be adaptable (untested).

**Workaround:** Custom EDC connectors can now be built from the public
template at https://github.com/Zoomdata/edc-cratedb. A GraphQL EDC
has been built and verified using this approach. See
`references/custom-edc-build.md` for the full guide including version
compatibility fixes, deployment steps, and Consul/Composer registration.

### Connector list does not include Fabric

The Simba JDBC Data Connector for Microsoft Fabric Spark (v0.9.1,
preview, April 2025) exists and uses driver class
`com.simba.fabricspark.jdbc.Driver` with JDBC URL format
`jdbc:fabricspark://`. No corresponding EDC exists in the chart.
The SparkSQL EDC is architecturally the closest match but has not been
tested with the Fabric driver.

---

## Quick reference: Helm values path

```
discovery:           <-- subchart alias (NOT logi-symphony)
  edc:
    <connector>:
      enabled: true/false
      properties: {}   <-- written to configmap
      extraEnvs: []    <-- injected as env vars on pod
      extraVolumeMounts: []
      extraVolumes: []
      image:
        repository: zoomdata-edc-<name>
      heapSizeMax: "1500M"
      heapSizeMin: "1500M"
      resources:
        limits:
          memory: 2Gi
        requests:
          memory: 2Gi
```
