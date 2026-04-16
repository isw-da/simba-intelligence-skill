# Building Custom EDC Connectors

The bundled EDC connectors cover JDBC-accessible databases. For data
sources that use REST APIs, GraphQL, WebSocket, or proprietary protocols,
you can build a custom EDC from an open-source template.

---

## Architecture overview

Every EDC connector is a standalone Java microservice that:

1. Implements the `ConnectorService.Iface` Thrift interface
2. Registers with Consul for service discovery
3. Exposes an HTTP endpoint at `/connector` for Thrift RPC
4. Declares its capabilities (features, connection parameters, icon)
5. Handles metadata discovery (schemas, collections, field descriptions)
6. Handles data read requests (prepare, fetch, cancel, status)

Composer communicates with EDCs exclusively via Thrift binary protocol
over HTTP. The connector type (JDBC, REST, GraphQL, WebSocket) is an
internal implementation detail invisible to Composer.

---

## Template: edc-cratedb

The official public EDC template is available at:
**https://github.com/Zoomdata/edc-cratedb**

This repo contains:

- **Framework code** (~80 files in `framework/` and `common/`) that
  handles Thrift service registration, async processing, connection
  pooling, query building, and filter/sort/group processing. This code
  is reusable as-is.
- **Reference implementation** (~6 files in `provider/cratedb/`) that
  demonstrates a JDBC-based connector for CrateDB.

### Key interfaces

| Interface | Purpose |
|---|---|
| `IDataProvider` | Core contract: 14 methods for validation, metadata, data reads |
| `AbstractDataProvider` | Base class providing async task execution (prepare/fetch/cancel/status) |
| `GenericSQLDataProvider` | JDBC-specific base class (skip for non-JDBC connectors) |
| `IComputeTaskFactory` | Creates compute tasks from data read requests |
| `IComputeTask` | Executes a query and returns a `Cursor` |
| `Cursor` | Iterator over records with metadata and batching |
| `IFeatures` | Declares connector capabilities (aggregation, filtering, etc.) |
| `ITypesMapping` | Maps source types to Thrift field types |
| `IDescriptionProvider` | Defines connection parameters shown in the Composer UI |

### For non-JDBC connectors

Extend `AbstractDataProvider` directly (not `GenericSQLDataProvider`).
Implement the `IDataProvider` methods that handle metadata and validation,
and override `createComputeTaskFactory()` to return your custom task
factory.

---

## Required dependency: edc-api

The `edc-api` JAR contains Thrift-generated classes for the connector
protocol. The original Maven repository (`public-maven.zoomdata.com`) is
no longer available. Extract the JAR from a running EDC container:

```bash
# Copy the EDC fat JAR from a running pod
kubectl -n <namespace> cp \
  <release>-discovery-edc-postgresql-0:/opt/zoomdata/services/edc-postgresql.jar \
  /tmp/edc-postgresql.jar \
  -c zoomdata-edc-postgresql

# Extract the edc-api JAR
jar xf /tmp/edc-postgresql.jar BOOT-INF/lib/edc-api-*.jar

# Install to local Maven repo
mvn install:install-file \
  -Dfile=BOOT-INF/lib/edc-api-25.4.0-*.jar \
  -DgroupId=com.zoomdata \
  -DartifactId=edc-api \
  -Dversion=25.4.0 \
  -Dpackaging=jar
```

---

## Version compatibility (critical)

The template was written for edc-api v2.3.1 (2017). Production Composer
uses v25.4.0 (2025). There are breaking changes between versions.

### API changes (v2.3.1 to v25.4.0)

| Change | Old | New |
|---|---|---|
| `CollectionInfo` package | `com.zoomdata.gen.edc.types` | `com.zoomdata.gen.edc.request` |
| `Field.setName()` | Exists | Removed. Field names carried by `ResponseMetadata` |
| `Record.setFields()` | Exists | Renamed to `Record.setRecord()` |
| `SampleRecord` | Takes `Record` | Takes `List<SampleField>` |
| `PrepareResponse.getRequestIDs()` | Exists | Renamed to `getRequestIds()` |
| `RequestID.getRequestId()` | Exists | Renamed to `getId()` |
| `DataReadRequest.getCollectionInfo()` | Direct accessor | Via `getStructured().getCollectionInfo()` |
| `StructuredRequest.getFields()` | Direct accessor | Via `getRawDataRequest().getFields()` (returns `List<String>`) |
| `ConnectorService.Iface` | 13 methods | 14 methods (added `describeSchemas`) |

### Dependency upgrades required

| Dependency | Template version | Production version | Why |
|---|---|---|---|
| Thrift | 0.9.3 | 0.21.0 | Binary protocol incompatible across major versions |
| Spring Boot | 1.4.3 | 3.2.x | Required for Thrift 0.21.0 (jakarta.servlet) |
| Lombok | 1.16.12 | 1.18.30+ or remove | Annotation processing broken on Java 11+ |
| Java | 8 | 17 | edc-api v25.4.0 compiled for Java 17 (class file version 61) |

### javax to jakarta migration

Spring Boot 3.x uses Jakarta EE 9+. Replace all `javax.annotation`
imports with `jakarta.annotation`:

```bash
find src -name "*.java" -exec sed -i '' \
  's/javax\.annotation\.PostConstruct/jakarta.annotation.PostConstruct/g' {} +
find src -name "*.java" -exec sed -i '' \
  's/javax\.annotation\.PreDestroy/jakarta.annotation.PreDestroy/g' {} +
find src -name "*.java" -exec sed -i '' \
  's/javax\.annotation\.Nullable/jakarta.annotation.Nullable/g' {} +
```

### sun.misc.IOUtils removal

Replace `sun.misc.IOUtils` in `GenericDescriptionProvider.java` with
Guava's `ByteStreams`:

```java
// Old
import sun.misc.IOUtils;
byte[] image = IOUtils.readFully(this.getClass().getResourceAsStream(iconFile), -1, true);

// New
import com.google.common.io.ByteStreams;
byte[] image = ByteStreams.toByteArray(this.getClass().getResourceAsStream(iconFile));
```

### Lombok removal

The simplest fix is to remove Lombok and write constructors/getters
manually for `Meta.java` and `SQLConnectionPoolKey.java`. These are
small classes (under 30 lines each).

### Add describeSchemas method

Add to `ZoomdataConnectorService.java`:

```java
@Override
public MetaDescribeSchemaResponse describeSchemas(
        MetaDescribeSchemaRequest request) throws TException {
    return new MetaDescribeSchemaResponse(
            Collections.emptyList(),
            new ResponseInfo(ResponseStatus.SUCCESS, "OK"));
}
```

### Add ResponseInfoBuilder.ok() helper

Add to `ResponseInfoBuilder.java`:

```java
public static ResponseInfo ok() {
    return new ResponseInfo(ResponseStatus.SUCCESS, "OK");
}
```

---

## Deploying a custom EDC to Kubernetes

### Step 1: Build the Docker image

```dockerfile
FROM eclipse-temurin:17-jre
COPY target/connector-server-<name>-1.0.0-exec.jar /opt/connector.jar
EXPOSE 7338
CMD ["java", "-Duser.timezone=UTC", "-jar", "/opt/connector.jar"]
```

### Step 2: Load into the cluster

For kind:

```bash
docker build -t edc-<name>:1.0.0 .
docker save edc-<name>:1.0.0 -o /tmp/edc-<name>.tar
kind load image-archive /tmp/edc-<name>.tar --name <cluster-name>
```

For cloud (EKS/AKS/GKE): push to a container registry.

### Step 3: Deploy pod and service

```bash
cat <<'EOF' | kubectl apply -n <namespace> -f -
apiVersion: v1
kind: Pod
metadata:
  name: edc-<name>
  labels:
    app: edc-<name>
spec:
  containers:
  - name: edc-<name>
    image: edc-<name>:1.0.0
    imagePullPolicy: Never    # kind only; remove for cloud
    ports:
    - containerPort: 7338
    resources:
      requests:
        memory: "256Mi"
      limits:
        memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: edc-<name>
spec:
  selector:
    app: edc-<name>
  ports:
  - port: 7338
    targetPort: 7338
EOF
```

### Step 4: Register in Consul

Production EDCs auto-register with Consul on startup. Custom EDCs need
manual registration:

```bash
kubectl -n <namespace> exec <release>-consul-server-0 -c consul -- \
  consul services register \
    -name=edc-<name> \
    -address=edc-<name>.<namespace>.svc.cluster.local \
    -port=7338 \
    -meta=HTTP_URL=http://edc-<name>.<namespace>.svc.cluster.local:7338/connector
```

### Step 5: Register in Composer

After Consul registration, create the connector entry via the API:

```bash
curl -s -X POST "http://localhost:8080/discovery/api/connectors" \
  -u "admin:<password>" \
  -H "Content-Type: application/vnd.composer.v3+json" \
  -d '{
    "name": "<Display Name>",
    "type": "DISCOVERY",
    "params": {
      "SERVICE_NAME": "edc-<name>",
      "HTTP_URL": "http://edc-<name>.<namespace>.svc.cluster.local:7338/connector",
      "BEHIND_GATEWAY": "false"
    }
  }'
```

Verify the connector appears and responds:

```bash
curl -s "http://localhost:8080/discovery/api/connectors" \
  -u "admin:<password>" | python3 -c "
import sys,json
for c in json.load(sys.stdin).get('content',[]):
    print(f\"{c['name']:20s} available={c['available']}\")
"
```

---

## Composer API authentication

The Composer REST API uses Basic auth against the admin user:

```bash
curl -s "http://localhost:8080/discovery/api/<endpoint>" \
  -u "admin:<COMPOSER_ADMIN_PASSWORD>"
```

The admin password is set in Helm values at
`global.discovery.adminPasswordSecret.value` and is also available as
the `COMPOSER_ADMIN_PASSWORD` environment variable on the SI pod:

```bash
kubectl -n <namespace> exec deploy/<release>-simba-intelligence-chart \
  -- env | grep COMPOSER_ADMIN_PASSWORD
```

Note: The OAuth token endpoint (`/discovery/api/zoomdata/oauth/token`)
does not work with the standard `zoomdata:zoomdata` client credentials
in v25.4.0. Use Basic auth directly on API endpoints instead.

---

## Verified custom EDC: GraphQL

A working GraphQL EDC connector has been built and tested.

**Source code:** https://github.com/isw-da/edc-graphql

### Capabilities

- Connects to any GraphQL endpoint via HTTP POST
- Auto-discovers schema via GraphQL introspection (`__schema` query)
- Maps root query fields to Composer collections
- Maps GraphQL scalar types to Thrift field types
- Fetches data by building GraphQL queries from EDC structured requests
- Supports authentication via configurable headers (Bearer, API key, custom)

### Connection parameters

| Parameter | Required | Description |
|---|---|---|
| GRAPHQL_URL | Yes | GraphQL endpoint URL |
| AUTH_TOKEN | No | Authentication token |
| AUTH_HEADER_NAME | No | Header name (default: Authorization) |
| AUTH_HEADER_PREFIX | No | Token prefix (default: Bearer) |
| CUSTOM_HEADERS | No | Additional headers as JSON |

### Test results (Countries API)

Successfully tested against `https://countries.trevorblades.com/graphql`:

- `describeServer` returns GRAPHQL connector with 5 connection parameters
- `validateSource` connects and introspects the schema
- `schemas` returns `["default"]`
- `collections` discovers 6 collections (continent, continents, countries, country, language, languages)
- `describe("countries")` returns 15 fields with correct types
- `fetch("countries", fields=["name","code","capital","emoji"])` returns 250 records
- Registered in Composer via Consul, connector shows `available=true`
- Composer successfully calls `ServerInfoRequest` and receives 33 feature entries

---

## Building additional custom connectors

The GraphQL EDC proves the pattern. To build a connector for a new
protocol:

1. Clone the GraphQL EDC project (not the original CrateDB template,
   which requires all the version upgrades documented above)
2. Replace the `provider/graphql/` package with your implementation
3. Implement `IDataProvider` methods for your protocol:
   - `pingSource` / `pingCollection` for connectivity validation
   - `schemas` / `collections` / `describe` for metadata discovery
   - `createComputeTaskFactory` for data fetching
4. Set the `@Connector("YOUR_TYPE")` annotation
5. Update `createDescriptionProvider()` with your connection parameters
6. Build, containerise, deploy, register

### Known limitation: QE aggregation queries

RAW_DATA_ONLY connectors experience `NumberFormatException` in the
Query Engine's `RowConverter` when aggregation queries (GROUP BY, COUNT,
SUM) are executed. The QE stores field metadata in its own order (likely
alphabetical) and uses that order to parse positional field values from
the fetch response. If the connector returns fields in a different order
(e.g. introspection order), the type mapping breaks.

**Root cause:** The QE sends the raw query `{ collectionName }` with no
field list, then maps the positional response against its stored metadata.
The connector returns fields in schema introspection order, which does
not match the QE's stored order.

**Fix (not yet implemented):** Read `StructuredRequest.getFieldMetadata()`
to get the QE's expected field order and return fields in that order in
both `ResponseMetadata` and `Record`.

**Workaround:** Raw data queries (filter, sort, project) work correctly.
Aggregation is handled client-side by SI's LLM query agent for simple
cases. Complex aggregation requires the fix above.

### Planned connectors

| Connector | Protocol | Status |
|---|---|---|
| GraphQL | HTTP POST + introspection | Built, tested, deployed (https://github.com/isw-da/edc-graphql) |
| SAP Datasphere | JDBC (HANA Cloud driver) | Planned (simple, extend GenericSQLDataProvider) |
| Qlik | WebSocket (QIX Engine API) | Planned (implement IDataProvider directly) |
