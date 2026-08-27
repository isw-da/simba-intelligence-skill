# Simba Intelligence 26.2.1 + Logi Composer, local kind lab

Install run on 2026-08-27 by Claude Code, against `kind-simba-intel-lab`.
Purpose: get a real instance running so the SI knowledge base can be tested
against something that answers rather than against documentation.

## Environment

| Item | Value |
|---|---|
| Host | Apple Silicon Mac, Darwin 25.3.0, `arm64` |
| Docker | server arch `arm64`, 12 CPU, 31 GiB |
| Cluster | kind, context `kind-simba-intel-lab`, single node `simba-intel-lab-control-plane` |
| Kubernetes | v1.34.0, containerd 2.1.3 |
| Node age | 101 days (the brief said 2 days; the node and its namespaces are 101d old) |
| Namespace | `simba-intel` (created by the install, previously absent) |
| Helm release | `si` |
| Chart | `simba-intelligence-chart` 26.2.1, appVersion 26.2.1 |
| Subchart | `composer` 1.21.0, appVersion 26.2, alias `discovery` |
| Chart source | `/tmp/simba-intelligence-chart-26.2.1.tgz`, 505,703 bytes |

## What Composer is here

Logi Composer is not a separate install. It is the `composer` subchart aliased
`discovery`, gated on `global.discovery.enabled` (default `true`). Everything
named `si-discovery-*` is Composer, and the Composer web container reports
itself as `Zoomdata Server :: 26.2.0-8.20260626120913.162d1ef9.release`.

## Commands, in order

```bash
# 1. Confirm context and that the namespace does not already exist
kubectl config current-context          # kind-simba-intel-lab
kubectl get ns                          # no simba-intel

# 2. Unpack the chart to read it before installing it
mkdir -p /Users/aminhasan/simba-intel-lab/chart-262
cd /Users/aminhasan/simba-intel-lab/chart-262
tar xzf /tmp/simba-intelligence-chart-26.2.1.tgz

# 3. Render the chart to get the real image list rather than guessing
helm template si /tmp/simba-intelligence-chart-26.2.1.tgz \
  --namespace simba-intel --set ingress.enabled=false \
  | grep -E "^\s+image:" | sed 's/.*image: *//' | tr -d '"' | sort -u

# 4. Check every image for an arm64 manifest BEFORE installing
docker manifest inspect <image> | grep '"architecture"'

# 5. Values file
cat > /Users/aminhasan/simba-intel-lab/si-262-values.yaml << 'YAML'
ingress:
  enabled: false
YAML

# 6. Install from the local tarball
helm install si /tmp/simba-intelligence-chart-26.2.1.tgz \
  --version 26.2.1 \
  -f /Users/aminhasan/simba-intel-lab/si-262-values.yaml \
  --namespace simba-intel --create-namespace
```

`helm install` returned `STATUS: deployed, REVISION: 1` at 16:45:03.

## Images actually pulled

All thirteen resolved from Docker Hub with no pull secret. Every one has a
linux/arm64 manifest, so nothing needed `--platform` and nothing crashlooped
on architecture.

| Image | arm64 |
|---|---|
| `docker.io/insightsoftware/simba-intelligence:26.2.1` | yes |
| `docker.io/insightsoftware/simba-intelligence-job-base:26.2.1` | yes |
| `docker.io/insightsoftware/curl:1` | yes |
| `docker.io/insightsoftware/curl` (no tag, resolves to `:latest`) | yes |
| `docker.io/insightsoftware/zoomdata:26.2.0` | yes |
| `docker.io/insightsoftware/zoomdata-client:26.2.0` | yes |
| `docker.io/insightsoftware/zoomdata-query-engine:26.2.0` | yes |
| `docker.io/insightsoftware/zoomdata-edc-postgresql:26.2.0` | yes |
| `docker.io/hashicorp/consul:1.22.1` | yes |
| `docker.io/hashicorp/consul-k8s-control-plane:1.9.1` | yes |
| `docker.io/postgres:15-alpine` | yes |
| `docker.io/redis:8-alpine` | yes |
| `docker.io/nginx:1.28-alpine` (discovery proxy, not deployed here) | yes |

Note the deliberate version skew: the SI images are `26.2.1`, the Composer
(`zoomdata-*`) images are `26.2.0`, set by `global.image.tag` in the chart.

---

# Findings: where the knowledge base and the cluster disagree

These matter more than the install. Each one was observed on a running
26.2.1 instance, not inferred.

## 1. The install script contains a `pkill` by pattern that must go

`scripts/install-si.sh:201`

```bash
pkill -f "port-forward.*simba-intelligence-chart.*8082:5050"
```

Two lines like this exist (the second targets `discovery-web.*8081:9050`).
`pkill -f` matches any process whose full command line contains the pattern,
including a shell, editor or agent that merely has the string on its command
line. This class of command has already killed a live application on this
machine. The script already captures `PF1_PID` and `PF2_PID` twenty lines
later and tells the user to `kill` those, so the fix is to record the PIDs to
a file and kill only those, or to skip the pre-kill entirely and fail loudly
on a port collision (which step 3 already checks for).

Not run during this install.

## 2. The airgapped guide names two images that do not exist

`references/deployment-airgapped.md` tells the user to run:

```bash
docker pull insightsoftware/simba-intelligence-chart:<VERSION>
docker pull insightsoftware/zoomdata-web:<VERSION>
docker pull insightsoftware/zoomdata-query-engine:<VERSION>
```

- `insightsoftware/zoomdata-web` does not exist. The Composer web image is
  `insightsoftware/zoomdata`.
- `insightsoftware/simba-intelligence-chart` does exist but is **not a
  container image**. Its manifest mediaType is
  `application/vnd.cncf.helm.config.v1+json`, so it is the Helm chart as an
  OCI artefact. `docker pull` will succeed and produce something that cannot
  run. The application image is `insightsoftware/simba-intelligence`.

An air-gapped install following this guide would transfer a chart tarball
labelled as an app image and be missing the app entirely. The correct way to
enumerate images is the one used here:

```bash
helm template si <chart.tgz> --namespace simba-intel \
  | grep -E "^\s+image:" | sed 's/.*image: *//' | tr -d '"' | sort -u
```

## 3. MCP service port is 8001, not 8000, and the sidecar is gone

`SKILL.md` § Architecture states the MCP server is on service port **8000**
and that ingress must route `/mcp/*` to it. On this instance the service
`si-simba-intelligence-chart-mcp` listens on **8001**, and the deployment has
exactly **one** container named `simba-intelligence-chart-mcp`.

`references/si-26.2-release.md` already records this correctly (PY-524, nginx
sidecar removed, FastMCP serves on `:8001`). SKILL.md's own architecture
section contradicts its own reference file. SKILL.md is the file that gets
read first, so it is the one that misleads.

Consequence: `references/local-access.md` and the Caddyfile in
`install-si.sh` route only `/` and `/discovery/*`. Neither routes `/mcp/*`
at all, so the MCP server that the SI MCP knowledge base is about is not
reachable through the documented local access path on any port.

## 4. The expected-pods table in `deployment-local.md` is out of date

| Documented | Actual on 26.2.1 |
|---|---|
| `si-simba-intelligence-chart-mcp-*` — **2/2** Running | **1/1** (sidecar removed) |
| `si-simba-intelligence-chart-db-migrate-*` | `si-simba-intelligence-chart-dbm-2608-001-*` |
| `si-simba-intelligence-chart-initjob-*` | `si-simba-intelligence-chart-init-2608-001-*` |

The job pods now carry a date-and-sequence suffix (`2608-001`), so any script
or doc matching on `db-migrate` or `initjob` by name will miss them.
Everything else in that table was correct.

## 5. Basic auth against the bundled Composer API works

This settles an open disagreement. `logi-composer/CLAUDE.md` states that for
the SI-bundled deployment "Basic auth is rejected: set
`COMPOSER_CONTEXT_PATH=/discovery` and use session-cookie + CSRF auth
instead". Peter's material says Basic works.

On this instance, Basic works:

```
GET /discovery/api/accounts, HTTP Basic admin:<pw>   -> 200, account list returned
GET /discovery/api/accounts, no auth                 -> 401
GET /discovery/api/accounts, wrong password          -> 401
```

Credentials come from the cluster, not from the values file default:
`COMPOSER_ADMIN_USERNAME=admin` on the SI deployment, password from
`kubectl -n simba-intel get secret si-discovery-web -o jsonpath='{.data.admin\.password}' | base64 -d`.

The live spec is explicit about it too: `security: [{basicAuth: []}]`, with
three declared schemes, `basicAuth`, `trustedAccessAuth` and `bearerAuth`.

Caveat worth keeping: this is a bundled Composer reached **directly** at its
own service. It says nothing about a Composer sitting behind Symphony or
Composer-managed SSO (`managedUrl`, PY-530), which is the likelier origin of
the session-cookie-plus-CSRF advice. The claim to correct is the unqualified
one: Basic is not rejected by the bundled deployment as such.

### Independent corroboration

A second session was working the same cluster in parallel and reached the same
verdict by a different route, recorded in
`/Users/aminhasan/simba-intel-lab/BASIC-AUTH-VERDICT.md`. It tested
`/discovery/api/sources` with the `application/vnd.composer.v3+json` media
type rather than `/discovery/api/accounts`, and added a corroborating detail
worth keeping: the server answers an unauthenticated request with
`WWW-Authenticate: Basic realm="api"`, so it advertises Basic unprompted.

It also identified the likely origin of the wrong claim. The install generates
a random 24-character admin password into the `si-discovery-web` secret, so a
guessed credential such as `admin:admin` returns 401 with an OAuth2-flavoured
body, `{"error":"invalid_token",...}`, which reads like "this endpoint wants a
bearer token". The credential was wrong, not the mechanism. And getting the
context path wrong (`/api/sources`, `/composer/api/sources`) returns 302, which
is easy to misread as an auth failure.

Two independent tests, different endpoints, same answer.

## 6. `/discovery/api-docs` is unauthenticated; the Swagger UI is not

- `GET /discovery/api-docs` -> **200**, full OpenAPI 3.1.0 spec, no credentials
- `GET /discovery/v3/api-docs` -> 401
- `GET /discovery/swagger-ui/index.html` -> 401
- `GET /discovery/` -> 401
- `GET /discovery/actuator/health` -> 200 `{"status":"UP"}`

So the spec is pullable from any instance without credentials, which is the
cheapest possible way to diff a customer's version against the mirror.

## 7. Live spec versus the mirror

Saved to `/Users/aminhasan/simba-intel-lab/composer-openapi-live-26.2.1.json`.

| | Paths | Operations |
|---|---|---|
| Live, bundled Composer 26.2.0 in chart 26.2.1 | **223** | **344** |
| Mirror `si-docs-mirror/composer-api/composer-openapi.json` | 220 | 338 |

In live only:
- `/api/data-gateway/clients`
- `/api/data-gateway/clients/authenticate`
- `/api/data-gateway/clients/{id}`
- `/api/data-gateway/clients/{id}/reset-secret`
- `/api/export/visualdata/enriched`

In the mirror only:
- `/api/connections/{connectionId}/schema/compact`
- `/api/sources/ai-enhancer`

The four `data-gateway/clients` paths line up with
`data-gateway.client-api.enabled: true` in the chart's discovery values, so
the mirror was probably pulled from a host with that feature off rather than
from an older build.

## 8. The deprecated product name is still in the 26.2.1 chart

The Postgres StatefulSet, its service and its PVC are all named
`si-logi-symphony-postgresql`:

```
statefulset.apps/si-logi-symphony-postgresql
service/si-logi-symphony-postgresql
pvc/data-si-logi-symphony-postgresql-0
```

and the JDBC URLs handed to Composer point at
`jdbc:postgresql://si-logi-symphony-postgresql:5432/zoomdata-user-auditing`.

So one cluster carries all three generations of the name at once: Zoomdata in
the images and Java packages, Logi Symphony in the database resources, and
Composer in the chart and the API title. "Never say Logi Symphony" is the
right rule for what we write; it is not safe as a search-and-replace rule for
what we read out of a cluster, and anyone grepping for the SI database by the
current product name will not find it.

## 9. Chart 26.2.1 ships Composer images at 26.2.0

`global.image.tag: "26.2.0"` while the SI images are `26.2.1`. Deliberate, but
it means "the 26.2.1 chart" and "Composer 26.2.1" are different things. The
web container announces itself as
`Zoomdata Server :: 26.2.0-8.20260626120913.162d1ef9.release`.

## 10. One image in the chart is untagged

The Composer subchart's `wait-consul` init containers render as
`image: docker.io/insightsoftware/curl` with no tag, so they resolve to
`:latest`, while the SI chart's own init containers correctly pin
`insightsoftware/curl:1`. It works today because `:latest` exists and is
multi-arch, but it is unpinned in a chart that pins everything else, and an
air-gapped mirror built from the tagged list would miss it.

## 11. Apple Silicon is a non-issue on 26.2.1

Every one of the thirteen images has a `linux/arm64` manifest. Nothing needed
`--platform`, nothing crashlooped on architecture, and the query engine (the
component most likely to be JVM-and-native-fragile) started clean:

```
Started QueryEngineApplication in 9.776 seconds
```

The `main-arm64` / `main-amd64` tags on the registry are branch builds, not
evidence of incomplete multi-arch on the release tags. Worth stating plainly
in the KB, because the caution costs people time.

## 12. Two stale claims in `~/CLAUDE.md`

- "Helm OCI pull is broken; use cached tarball at `~/Library/Caches/helm/content/`"
  — `helm pull oci://docker.io/insightsoftware/simba-intelligence-chart --version 26.2.1`
  works.
- "Chart: `simba-intelligence-chart-25.4.0`" — two majors behind. Current is 26.2.1.

The subchart alias note ("`discovery`, not `logi-symphony`") is still correct
and confirmed by `Chart.yaml`.

## 13. The brief's cluster age was wrong

The task brief said the cluster was 2 days old. `kubectl get ns` and
`kubectl get nodes` both report 101 days. That matters, because 101 days of
accumulated container images is what caused the only real failure in this
install. See below.

---

# The one real failure: the kind node ran out of disk

This is the finding that would have cost a customer an afternoon, and no
reference in the skill mentions it.

## Symptom

Roughly four minutes into the install, with Composer already healthy, the
`db-migrate` job failed:

```
DB migration failed: (psycopg2.OperationalError) connection to server at
"si-logi-symphony-postgresql" (10.96.76.108), port 5432 failed:
FATAL:  could not write init file
```

and Composer's own theme installer failed at the same moment:

```
ERROR:  could not extend file "base/16386/17723": No space left on device
```

Every SI pod then sat in `Init:CrashLoopBackOff` on its
`wait-for-database-schema` init container, and Postgres itself crashlooped
with `FATAL: could not write lock file "postmaster.pid": No space left on
device`.

The pod list at that moment looked like an SI problem. It was not.

## Cause

```bash
docker exec simba-intel-lab-control-plane df -h /
# overlay  59G  56G  0  100% /
```

The kind node's overlay is on the shared Docker VM disk. The node's own
containerd store held 17G, largely 101 days of superseded images from earlier
lab work: SI and `zoomdata-*` at 26.1.x, `apache/hive:4.0.0`,
`gvenzl/oracle-xe:21-slim`, and a set of EDC connector images. The host's
Docker had another ~23G of images and ~27G of volumes on the same disk.

`FATAL: could not write init file` is Postgres's message for a full or
unwritable data directory, and it does not say "disk". That is what makes
this expensive to diagnose: nothing in the SI logs says "out of space", only
the Postgres server log does.

## Fix applied

Evicted thirteen superseded, publicly re-pullable images from the kind node's
containerd cache, one by one, by exact name. The locally built custom EDC
images (`edc-datasphere:latest`, `edc-sharepoint:latest`) were left alone;
they also exist on the host Docker, so nothing unique was lost. The host's
own Docker images and volumes were not touched.

```bash
docker exec simba-intel-lab-control-plane crictl rmi docker.io/insightsoftware/simba-intelligence:26.1.1
# ... twelve more, each named explicitly
```

Result: 8.7G free, 85% used.

Postgres then had to be restarted by hand, because it had crashlooped past
its backoff while the disk was full and did not recover on its own:

```bash
kubectl -n simba-intel delete pod si-logi-symphony-postgresql-0
```

Composer web was also restarted, because its theme installer had aborted a
transaction mid-run and the installers are idempotent on restart:

```bash
kubectl -n simba-intel delete pod si-discovery-web-0
```

The `db-migrate` job retried on its own and completed. The two failed job
pods left behind by the incident were deleted so the gate would not report a
stale failure.

## What should go in the skill

`references/prerequisites.md` should carry a disk check, not just CPU and
memory:

```bash
docker exec <kind-node> df -h /
```

with a stated floor. This install consumed a little over 4G of images plus
about 1G of database, so 10G free is a sensible minimum and 20G comfortable.
`references/troubleshooting.md` should map `could not write init file` and
`No space left on device` to the node disk, because the SI-side symptom is a
misleading `Init:CrashLoopBackOff` on `wait-for-database-schema`.

---

# The gate

`/Users/aminhasan/simba-intel-lab/verify-si-up.sh`

Six checks, exits 0 only when all pass. It covers both products; the name was
kept because both the original brief and the follow-up point at that path.

```
[1/6] every pod Running-and-ready or Completed, nothing in a bad waiting state
[2/6] SI HTTP endpoint answers, service and port read from the cluster
[3/6] GET /api/v1/healthz -> 200, GET /api/v1/version -> parseable JSON
[4/6] Composer /discovery/actuator/health -> UP
[5/6] Composer /discovery/api-docs serves a parseable spec, saved to disk
[6/6] Composer query engine pod Running and ready
```

Final run, all six green:

```
  PASS  all 13 pods Running-and-ready or Completed
  PASS  GET / answered HTTP 200
  PASS  GET /api/v1/healthz -> 200            {"status":"OK"}
  PASS  GET /api/v1/version -> 200, version 26.2.1
        {"build_time":"2026-07-24T15:47:09Z","db_version":"6c21df0a75ba",
         "git":"e5d71a9","version":"26.2.1"}
  PASS  Composer /discovery/actuator/health -> UP
  PASS  GET /discovery/ answered HTTP 401
  PASS  GET /discovery/api-docs -> 200: "Logi Composer Rest API", 223 paths / 344 operations
  PASS  si-discovery-query-engine-0 Running and ready (restarts: 0)
RESULT: PASS   exit 0
```

## The gate was made to fail three ways before being trusted

| Fault injected | Result | Exit |
|---|---|---|
| `NAMESPACE=simba-intel-does-not-exist` | FAIL at check 0 | 1 |
| `kubectl scale deploy si-simba-intelligence-chart --replicas=0` | FAIL at check 2, no HTTP response | 1 |
| `kubectl scale statefulset si-discovery-query-engine --replicas=0` | FAIL at check 6, and check 1 caught the not-yet-ready SI pod | 1 |

Both scaled workloads were restored and the gate returned to green.

## Two bugs the gate itself had, both worth remembering

**It talked to a stranger.** The first run reported
`no HTTP response from http://127.0.0.1:18082/`, and a manual probe returned
`502` with the body `<urlopen error [Errno 61] Connection refused>`. Nothing
in the cluster produces that. An unrelated Python process (PID 33895) was
already listening on `127.0.0.1:18082`, so `kubectl port-forward` bound only
`[::1]` and every request went to somebody else's server. The gate now picks
the first free port by checking `lsof` before binding, and passes
`--address 127.0.0.1`.

This is the same hazard as the `pkill` line in `install-si.sh`, seen from the
other side. A second pre-existing port-forward from another session
(`svc/si-discovery-web 18099:9050`, PID 77992) was also found running. A
pattern kill would have taken it out.

**A 200 from the SI endpoint means nothing.** The gate's first Composer check
asked for `${SI}/discovery/` and got HTTP 200, then failed to find a spec
there. The SI app serves its SPA `index.html` with **200** for any unmatched
path:

```
GET /discovery/          -> 200 text/html   (SI's SPA, not Composer)
GET /discovery/api-docs  -> 200 text/html   (SI's SPA, not Composer)
GET /total/nonsense      -> 200             (SI's SPA)
```

So the SI service does not proxy Composer at all in this deployment, and any
liveness check of the form "curl the root and grep for html" passes even when
Composer is dead. `install-si.sh` step 10 does exactly that:

```bash
if curl -s http://localhost:8080/ | grep -q "html" 2>/dev/null; then
  info "Main app is accessible"
```

The gate now discriminates on `/discovery/actuator/health` returning JSON with
a `.status` field, and port-forwards `si-discovery-web` directly.

This is also the mechanism behind the "login loop" symptom in the
troubleshooting table. Worth stating in the skill as a mechanism rather than
a symptom: unmatched paths do not 404, they return the SI SPA, so a browser
asking for `/discovery/...` gets an SI page and loops.

---

# Access

Nothing is exposed outside the cluster; the values file sets
`ingress.enabled: false`. To reach either product, port-forward and kill the
PID you captured. Never `pkill` by pattern on this machine.

```bash
# Simba Intelligence
kubectl -n simba-intel port-forward --address 127.0.0.1 \
  svc/si-simba-intelligence-chart 8082:5050 & SI_PF=$!
# Composer
kubectl -n simba-intel port-forward --address 127.0.0.1 \
  svc/si-discovery-web 8081:9050 & DISC_PF=$!
# MCP
kubectl -n simba-intel port-forward --address 127.0.0.1 \
  svc/si-simba-intelligence-chart-mcp 8000:8001 & MCP_PF=$!

# when finished
kill $SI_PF $DISC_PF $MCP_PF
```

Check the ports are free first, several in the 8000s and 18000s are already
taken on this machine:

```bash
lsof -nP -iTCP:8081 -sTCP:LISTEN
```

Composer admin credentials come from the cluster, not from the values file:

```bash
kubectl -n simba-intel get secret si-discovery-web \
  -o jsonpath='{.data.admin\.password}' | base64 -d
# username: admin
```

MCP, probed on 8001: `GET /mcp` returns 405, which is correct for a
POST-only streamable HTTP transport, so the server is live.
`GET /.well-known/oauth-authorization-server` returns `Not Found` on this
default configuration.

---

# LLM provider

Not configured, and not needed to get here. SI is BYOLLM and starts happily
without a provider; `/api/v1/healthz` and `/api/v1/version` both answer. Any
NLQ, Data Source Agent or Playground work will need a provider configured per
`references/llm-config.md` first. No key was invented or guessed.

---

# Timings

| | |
|---|---|
| Session start | 16:42 |
| `helm install` submitted | 16:45:03 |
| Composer query engine up | 16:47 (started in 9.8s once scheduled) |
| Disk exhaustion hit | 16:49 |
| Disk freed, Postgres restarted | 16:51 |
| Composer web healthy after restart | 16:52 |
| All 13 pods Running-and-ready or Completed | 16:56 |
| Gate green, after two gate bugs fixed | 17:05 |
| Fault injection and restore complete | 17:09 |

About 14 minutes to a healthy stack including the disk incident, and roughly
11 minutes on top for the gate and its negative tests. A clean run on a
machine with disk headroom should be about 8 minutes.

---

# Files produced

| Path | What |
|---|---|
| `/Users/aminhasan/simba-intel-lab/verify-si-up.sh` | the gate, six checks, both products |
| `/Users/aminhasan/simba-intel-lab/si-262-values.yaml` | the Helm values used |
| `/Users/aminhasan/simba-intel-lab/composer-openapi-live-26.2.1.json` | live Composer spec, 223 paths / 344 operations |
| `/Users/aminhasan/simba-intel-lab/chart-262/` | unpacked chart, kept for reference |
| `/Users/aminhasan/simba-intel-lab/INSTALL-LOG.md` | this file |

# Teardown

```bash
helm uninstall si -n simba-intel
kubectl delete namespace simba-intel
```

---

# Concurrent work in this directory

Another session was operating on the same cluster and namespace while this
install ran, and wrote `BASIC-AUTH-VERDICT.md`,
`CONFIRMED-NOT-WORKING-VERDICT.md`, `settle-basic-auth.sh` and
`embed-26.2.1.js` into this directory between 16:49 and 16:54. It also left a
port-forward running (`svc/si-discovery-web 18099:9050`, PID 77992), which was
not touched.

Two writers on one namespace with no isolation is exactly the arrangement that
rule 18 exists to prevent. Nothing collided here, but the query-engine and
SI-app scale-to-zero fault injections in this log would have broken the other
session's probes had they overlapped. Worth flagging before the next parallel
run on this cluster.
