# Connecting SI to SAP Datasphere

Use this when a customer asks whether SI / Composer can connect to SAP
Datasphere. The answer is yes, via the HANA Cloud SQL endpoint that
Datasphere exposes per space through Database Users (Open SQL Schema).

This is the documented external-access mechanism in Datasphere itself,
not a workaround.

---

## Pick the right EDC: `saphana`, not `saphanacloud`

The Composer chart ships two HANA-related connectors. They look similar
but only one talks directly to a HANA SQL endpoint.

| Connector            | Driver               | URL prefix         | Use for             |
| -------------------- | -------------------- | ------------------ | ------------------- |
| `edc-saphana`        | SAP `ngdbc.jar`      | `jdbc:sap://`      | Datasphere, HANA Cloud, HANA on-prem |
| `edc-saphanacloud`   | DataDirect `ddhybrid-1.0.jar` | `jdbc:datadirect:` | Progress Hybrid Pipeline (managed bridge, requires Progress subscription) |

Despite the name, `edc-saphanacloud` is **not** the right connector for
direct HANA Cloud access. It expects a Progress-hosted Hybrid Data
Pipeline service in the middle. If you enable it with a `jdbc:sap://`
URL you get:

```
Cannot create JDBC driver of class 'com.ddtek.jdbc.ddhybrid.DDHybridDriver'
for connect URL 'jdbc:sap://...'
```

Switch to `edc-saphana` instead.

---

## Datasphere side: create the Database User

Done in the Datasphere UI by a user with Space admin rights on the
target space.

1. **Space Management** → click the space → **Edit**
2. **Database Access** tab
3. Optional: tick **Expose for Consumption by Default** so all views in
   the space are visible to external SQL clients
4. **Database Users** → **Create**
   - Name suffix: e.g. `COMPOSER` → full name becomes `<SPACE>#COMPOSER`
   - Tick **Enable Read Access (SQL)** under "Read Access to the Space Schema"
5. **Edit Privileges** → tick **Enable Write Access (SQL, DDL, & DML)**
   if SI needs to write back to the user's Open SQL Schema (most NLQ
   demos only need read, so this is usually unnecessary)
6. **Save** → wait for the toast "Database user updated"
7. Click the **ⓘ** icon next to the new user to view connection details:
   - Database User Name (the `<SPACE>#<SUFFIX>` form)
   - Host (a UUID at `*.hanacloud.ondemand.com`)
   - Port `443`
   - Password — click eye or **Copy Password**

After any privilege change, JDBC clients must **disconnect and
reconnect** to pick up the new grant. The pooled connection caches the
old session.

---

## SI side: enable `saphana` and stage the driver

The `saphana` EDC expects the JDBC driver mounted into a shared PVC at a
specific filename. The chart looks for `sap-hana-jdbc-2.0.12.jar`
regardless of the actual ngdbc version you stage.

### 1. Create the shared PVC

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: composer-shared-volume
  namespace: <namespace>
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 100Mi
  storageClassName: standard
```

### 2. Stage the driver via a temp pod

Download a recent ngdbc from Maven Central:

```bash
curl -sL -o /tmp/ngdbc.jar \
  "https://repo1.maven.org/maven2/com/sap/cloud/db/jdbc/ngdbc/2.28.7/ngdbc-2.28.7.jar"
```

Spin up a temp pod that mounts the PVC and creates the expected subPath:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: jar-loader
  namespace: <namespace>
spec:
  restartPolicy: Never
  containers:
    - name: shell
      image: busybox:1.36
      command: ["sh", "-c", "mkdir -p /vol/edc-saphana/drivers && sleep 600"]
      volumeMounts:
        - name: shared
          mountPath: /vol
  volumes:
    - name: shared
      persistentVolumeClaim:
        claimName: composer-shared-volume
```

Copy the jar with the filename the chart expects:

```bash
kubectl -n <namespace> cp /tmp/ngdbc.jar \
  jar-loader:/vol/edc-saphana/drivers/sap-hana-jdbc-2.0.12.jar
kubectl -n <namespace> delete pod jar-loader
```

### 3. Enable the connector

```yaml
# values-hana.yaml
discovery:
  edc:
    saphana:
      enabled: true
```

```bash
helm upgrade <release> <chart-path> \
  -n <namespace> --reuse-values -f values-hana.yaml
```

Wait for the pod:

```bash
kubectl -n <namespace> wait --for=condition=Ready \
  pod/si-discovery-edc-saphana-0 --timeout=180s
```

If the pod crashes with `File /opt/zoomdata/lib/edc-saphana/sap-hana-jdbc-2.0.12.jar does not exist`, the jar isn't at the expected path or filename. Verify by running `ls` inside the pod.

---

## Create the SI connection

In the SI web UI:

1. **Connections** → **Create Connection** → select **SAP HANA** (not SapHanaCloud)
2. Fill in:
   - Connection Name: e.g. `Datasphere`
   - JDBC URL: `jdbc:sap://<host>:443?encrypt=true`
   - User Name: `<SPACE>#<SUFFIX>` (e.g. `GE319522#COMPOSER`)
   - Password: paste from Datasphere
3. **Validate** → expect "Connection successful"
4. **Save**

The SI agentic scan can then run against the connection and the
Playground will accept NLQ.

---

## Trial-account gotcha

The **SAP Datasphere academy basic trial** (sap.com/.../datasphere/trial)
enforces an IP allowlist that admits SAP-internal services only. The
Database Explorer at `cf-eu10.cf.hana-tooling.ingress.orchestration.prod-eu10.hanacloud.ondemand.com`
works because it's inside SAP's own cloud. External JDBC clients
(your laptop, a kind pod, anywhere else) get TCP-connected but the TLS
session is closed by the server before any cert exchange:

```
Object is closed: com.sap.db.jdbc.SecureChannelSession@... on
sun.nio.ch.UnixAsynchronousSocketChannelImpl[connected ...]
```

`openssl s_client` from the same source shows `unexpected eof while
reading` and `Cipher is (NONE)` — the server doesn't even speak TLS to
non-SAP IPs.

**This is a trial-account restriction, not a product limitation.**
Customer-owned Datasphere tenants (paid, or BTP free-tier productive
plans) allow external SQL access subject to allowlists the customer
controls.

To prove end-to-end against the academy trial you'd need to run the SI
saphana EDC from inside SAP's cloud — not practical. Options:

- Provision Datasphere via BTP free-tier service plan on a productive
  pay-as-you-go account (Datasphere is not bookable on the standard 90-day
  BTP trial)
- Ask the customer for a read-only Database User on a sandbox space in
  their actual Datasphere tenant

---

## Diagnostics

**Driver loaded, connection refused:** look for `JDBCDriverException`
in `kubectl -n <ns> logs si-discovery-edc-saphana-0 -c
zoomdata-edc-saphana --tail=200`. If the stack trace shows
`SecureChannelSession ... Object is closed` with a TCP socket that
connected (local + remote IP present), the server is closing the TLS
handshake. Server-side restriction, not a client config issue.

**Wrong EDC error:** `Cannot create JDBC driver of class
'com.ddtek.jdbc.ddhybrid.DDHybridDriver'` means saphanacloud is
enabled. Disable it and enable saphana instead:

```yaml
discovery:
  edc:
    saphana:
      enabled: true
    saphanacloud:
      enabled: false
```

**Driver file missing:** `File /opt/zoomdata/lib/edc-saphana/sap-hana-jdbc-2.0.12.jar does not exist` — re-check the filename in the PVC. The chart hard-codes the path; it does not glob.

---

## Confirming the path works without SI

Use SAP HANA Database Explorer (linked from the Datasphere Database
Access tab via **Open Database Explorer** after selecting the Database
User). If you can query in there, the endpoint and credentials are good
and any failure in SI is a Composer-side problem.

A minimal local Java test using the same `ngdbc.jar`:

```java
import java.sql.*;
public class HanaTest {
  public static void main(String[] a) throws Exception {
    Class.forName("com.sap.db.jdbc.Driver");
    Connection c = DriverManager.getConnection(a[0], a[1], a[2]);
    ResultSet rs = c.createStatement().executeQuery("SELECT CURRENT_USER FROM DUMMY");
    rs.next();
    System.out.println("USER: " + rs.getString(1));
    c.close();
  }
}
```

```bash
javac HanaTest.java
java -cp ngdbc.jar:. HanaTest \
  'jdbc:sap://<host>:443?encrypt=true' \
  '<SPACE>#<SUFFIX>' \
  '<password>'
```

Running this from outside SAP's cloud against an academy trial fails
the same way the EDC does. Running it against a real tenant succeeds.
