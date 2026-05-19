# Inspecting SI logs in Datadog

This reference covers how to find logs for hosted Simba Intelligence
environments (trials, demos, internal tenants) in the Datadog `Isw-Nonprod`
org. Use it when investigating a tenant issue, tracing a query, or
diagnosing an SI auth or LLM failure for a customer.

It does **not** cover SI Agent installation (the Datadog Agent isn't
deployed alongside SI by default). Logs land in Datadog because the
underlying Symphony / Discovery / Zoomdata stack already ships logs.

---

## What's available, what isn't

Available:

- Application logs for `simba-intelligence`, `simba-intelligence-chart-celery-worker`,
  `zoomdata-query-engine`, `dundas-bi-*`, `consul`, `nginx` across three
  Kubernetes clusters.
- Filtering by `kube_cluster_name`, `service`, `pod_name`, `container_name`,
  `availability-zone`, `aws_account`, `kube_app_version`.
- Substring search across raw message bodies (tenant UUIDs, session IDs,
  topology IDs, source IDs, customer error strings).
- Web access facets where logs are parsed as nginx (`URL Path`, `Method`,
  `Response code`, `Client IP`, `Browser`).

Not available:

- **No APM traces** for any SI / Zoomdata / Composer / Dundas service in
  nonprod. Confirmed via the APM service catalogue. Tracing is logs only.
- **No extracted attributes** on `simba-intelligence` message bodies. You
  can search for a tenant UUID as a string but you can't click-filter on
  `tenant_id` as a facet.
- **No tenant-name search.** Tenants appear as UUIDs only. "Amplifin"
  returns zero hits.
- **isw.logisymphony.com is not in this Datadog org** (it's on GCP, not
  AWS, and not reporting to Isw-Nonprod). Check the prod org or GCP Cloud
  Logging for that one.

---

## URL → cluster mapping

Confirmed by probing each public URL (`curl -sI`, DNS, TLS cert) and
cross-referencing the cluster's `aws_account` and AZ in log metadata.

| Public URL | DNS target | Cluster (`kube_cluster_name`) | Pod prefix | AWS account | Region |
|---|---|---|---|---|---|
| `simba.logisymphony.com` | `k8s-simba-simbasim-218e14a15a-*.us-east-2.elb.amazonaws.com` | `preview-eks-cluster` | `previewmain-simbaintelligence-*` | 151662208362 | us-east-2 |
| `simbaintel.logianalytics.com` | `a91867f3b2b1447abbafea4b4308bd1e-*.us-east-1.elb.amazonaws.com` | `qa2-eks-cluster` | `si2-simba-intelligence-chart-*` | 731970931268 | us-east-1 |
| `isw.logisymphony.com` | `34.54.16.145` (GCP, `via: 1.1 google`) | not in Isw-Nonprod | n/a | n/a | GCP |

Notes:

- The public URLs do not appear in log messages literally. The Referer
  header on access logs shows the internal frontend (`preview.logi-symphony.com`,
  `qa2.logi-symphony.com`, etc.), so substring searches on the public
  domain return zero hits.
- A fourth cluster, `uat-symphony-deployment` (us-east-2, ~26k logs/day),
  hosts the broader Symphony UAT stack including Dundas BI. It does not
  serve any of the three Simba-branded customer URLs.

---

## Service catalogue

Top SI-related `service` values in Isw-Nonprod:

| Service | What it logs | Typical volume |
|---|---|---|
| `simba-intelligence` | Main app: auth (`/intelligence/api/v1/auth/check-auth`), source listing, NLQ entry, composer auth failures | ~112k / day |
| `simba-intelligence` (container `simba-intelligence-chart-celery-worker`) | VDD tenant planning, capability fallbacks, source enrichment | included above |
| `zoomdata-query-engine` | SQL execution, topology IDs, ZEngine sessions, record counts, connector errors | ~33k / day |
| `dundas-bi-storage` | Composer storage / metadata APIs | ~122k / day (UAT cluster) |
| `dundas-bi-reverseproxy` | Composer reverse proxy, `/managed/api/...` traffic | ~3k / day |
| `nginx` | Ingress, static asset serving | ~14k / day |
| `consul` | Service discovery health checks | ~9k / day |

---

## Filtering by tenant

For the full story on identifier formats, API endpoints, and the
Amplifin example, see `references/tenant-discovery.md`. Short version:

The same logical tenant has **three different IDs** in different layers.
The one that appears in Datadog SI logs is the VDD tenant UUID:

```
[2026-05-18 03:19:31 INFO/MainProcess] Using VDD tenant's CHAT capability
as fallback for tenant e2a11f69-d23d-4ef5-b432-1d85089cf56f
```

| Layer | Format | Example |
|---|---|---|
| Composer admin (what you see in the URL) | 24-char hex ObjectId | `69fafe7ced27777725d94774` |
| VDD / SI logs (what appears in Datadog) | 36-char UUID | `e2a11f69-d23d-4ef5-b432-1d85089cf56f` |
| Symphony session | 36-char UUID | `d7cf37cf-789a-49a6-b917-56fc5819530b` |

To filter Datadog by tenant:

1. Get the **VDD tenant UUID** for the customer you care about. The
   easiest way is to ask them to run one NLQ, then grep:
   ```
   service:simba-intelligence "Using VDD tenant" container_name:simba-intelligence-chart-celery-worker
   ```
   and pick the UUID timed to their query. See `tenant-discovery.md`
   for the full mapping procedure.
2. Use that UUID as a quoted substring in the query:
   ```
   service:simba-intelligence "<vdd-tenant-uuid>"
   ```

For a session-scoped trace (single user, single login), capture the
`sessionId` from browser dev tools while reproducing the issue, then:

```
service:simba-intelligence "sessionId=<uuid>"
```

---

## Tracing an SI query end to end

The full pipeline (chat entry, Celery's actual role, query engine,
EDC connector, Vertex AI) is documented in `query-tracing.md`. Headline
corrections to what was here before:

- The NLQ entry point is `POST /intelligence/api/v1/chat/stream`,
  handled **synchronously by the SI app pod**, not by Celery.
- The Celery worker (`simba-intelligence-chart-celery-worker`) handles
  background tasks only: `validate_and_cache_suggestions`,
  `generate_suggestions_scheduled_task`, `cleanup_expired_oauth_tokens_task`,
  etc. Chats do not go through it.
- The natural-language question is **never logged** anywhere we found.
  Privacy plus.
- Vertex AI is the LLM provider in use; quota errors (`429 Resource
  exhausted`) are the most common error pattern.

See `query-tracing.md` for the per-stage patterns, reconstruction
recipe across services, and the list of additional service tags
(`agents-runtime`, `data-analyst`, `text-summarizer`, etc.) found
during the investigation.

## LLM observability (Vertex AI)

Quick patterns; full context in `query-tracing.md` § LLM observability.

```
# Anything from the Vertex AI SDK
service:simba-intelligence ("vertexai" OR "google.api_core.exceptions")

# Just the 429 quota errors (most common Vertex AI error in our window)
service:simba-intelligence "429 Resource exhausted"

# Per tenant
service:simba-intelligence "vertexai" "<vdd-tenant-uuid>"
```

Prompt text, response text, and per-request token counts are **not
logged**. For real cost/usage telemetry, look at the GCP billing
console for project `agile-tracker-403309` (SA key at
`~/si-trace-viewer/backend/gcp-sa.json`).

---

## Log Explorer URL templates

Bookmark or share these. Adjust `from_ts` / `to_ts` (epoch milliseconds)
as needed.

All SI app logs in a cluster, last hour:
```
https://isw-nonprod.datadoghq.com/logs?query=service%3Asimba-intelligence%20kube_cluster_name%3Apreview-eks-cluster
```

Tenant-scoped logs across the SI app tier:
```
https://isw-nonprod.datadoghq.com/logs?query=service%3Asimba-intelligence%20%22<tenant-uuid>%22
```

Query engine errors only:
```
https://isw-nonprod.datadoghq.com/logs?query=service%3Azoomdata-query-engine%20status%3Aerror
```

Composer auth failures (the 410 Gone pattern):
```
https://isw-nonprod.datadoghq.com/logs?query=service%3Asimba-intelligence%20%22composer_auth%22%20%22410%22
```

---

## Programmatic access

For scripts, MCP tools, or notebooks that need to pull logs without the
browser:

### What you need

1. **An API key**, which submits requests on behalf of the org. The 16
   existing keys at `/organization-settings/api-keys` are owned by other
   teams; the API Keys page is read-only for Amin in Isw-Nonprod, so
   you cannot mint your own here. Either ask an admin to create a
   dedicated read-only key (recommended name: `Amin_Logs_ReadOnly`) or
   reuse an API key you already own from another project.
2. **An Application key**, scoped to your user, created at
   `/personal-settings/application-keys`. Inherits the user's read
   permissions; that's all the Logs API needs. Click `+ New Key`, name
   it `amin-logs-read`, scope to `logs_read_data` if you want it
   narrower than full inherited rights.

### curl

```bash
curl -X POST "https://api.datadoghq.com/api/v2/logs/events/search" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "query": "service:simba-intelligence \"e2a11f69-d23d-4ef5-b432-1d85089cf56f\"",
      "from": "now-1h",
      "to": "now"
    },
    "page": { "limit": 50 },
    "sort": "-timestamp"
  }'
```

### Python

```python
from datadog_api_client import ApiClient, Configuration
from datadog_api_client.v2.api.logs_api import LogsApi
from datadog_api_client.v2.model.logs_list_request import LogsListRequest
from datadog_api_client.v2.model.logs_query_filter import LogsQueryFilter

cfg = Configuration()
cfg.api_key["apiKeyAuth"] = os.environ["DD_API_KEY"]
cfg.api_key["appKeyAuth"] = os.environ["DD_APP_KEY"]

with ApiClient(cfg) as client:
    api = LogsApi(client)
    body = LogsListRequest(
        filter=LogsQueryFilter(
            query='service:simba-intelligence "<tenant-uuid>"',
            _from="now-1h",
            to="now",
        ),
    )
    resp = api.list_logs(body=body)
    for log in resp.data:
        print(log.attributes.timestamp, log.attributes.message[:200])
```

Site is `datadoghq.com` (not `.eu` or `.us3`). Rate limit is generous for
ad-hoc queries but watch out for batch backfills.

---

## Known gotchas

- **`*amplifin*` will not match anything.** Tenant names aren't logged.
  Use the VDD tenant UUID (see `tenant-discovery.md`).
- **Searching the public URL won't work.** `simba.logisymphony.com` is a
  DNS alias for the AWS ELB; the Referer header on access logs shows the
  internal frontend (`preview.logi-symphony.com`). Filter by
  `kube_cluster_name` instead.
- **The hot index window is short.** If you need logs older than
  ~15 days, click `Try Rehydrating From Archives` in the Log Explorer.
- **Watchdog Insights often fingers `cluster_name:preview-eks-cluster`
  as an error outlier.** That cluster runs the public Simba preview and
  is genuinely chatty with `composer_auth` 410s when Symphony sessions
  expire. Don't treat the Watchdog warning as a new incident unless the
  error pattern is unfamiliar.
- **`uat-symphony-deployment` is the wider Symphony stack**, not a
  Simba-only environment. Filter by `service:simba-intelligence` if you
  only want the SI app, otherwise you'll pull in Dundas BI noise.
- **No APM, no flame graphs.** Distributed tracing is not instrumented.
  Use the three-stream log join described above.

---

## When to look elsewhere

- `isw.logisymphony.com` (GCP-hosted): check the prod Datadog org or
  GCP Cloud Logging in the relevant project. Not in Isw-Nonprod.
- Customer's own SI deployment: they have their own observability
  stack. Ask them to share the relevant logs rather than guessing.
- Local kind cluster (`simba-intel-lab`): logs are not shipped to
  Datadog. Use `kubectl -n simba-intel logs -l app.kubernetes.io/component=discovery-query-engine`
  as documented in `references/troubleshooting.md`.
