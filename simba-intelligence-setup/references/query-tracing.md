# Tracing SI queries in Datadog

This reference covers how SI's NLQ pipeline shows up in Datadog logs, the
gaps in what's logged (deliberate and otherwise), and the join patterns
that let you reconstruct a query end-to-end. Companion to
`datadog-logs.md` and `tenant-discovery.md`.

The short version: SI's NLQ pipeline is **synchronous and quiet**. The
natural-language question never appears in logs (privacy plus), and the
SI Python app emits very little chat-specific output. Reconstructing a
trace means correlating across services by timestamp, pod, tenant UUID,
session ID, and visualisation/topology ID.

---

## The NLQ entry point

When a user submits a question in the SI Playground, the frontend POSTs
to:

```
POST /intelligence/api/v1/chat/stream
```

In Datadog this lands as an nginx access log on `service:simba-intelligence`:

```
10.108.71.120 - - [18/May/2026:16:32:26 +0000] "POST /intelligence/api/v1/chat/stream HTTP/1.1" 200 7506 "https://preview.logi-symphony.com/intelligence/playground" "Mozilla/5.0 ..."
```

Useful fields in that line:
- Response size (`7506` bytes here): the streamed response. A small
  number suggests a quick refusal, a large one suggests a real answer
- Referer (`https://preview.logi-symphony.com/intelligence/playground`):
  the origin domain (which is also how to identify the cluster)
- Source IP (`10.108.71.120` here): the in-cluster gateway pod, not the
  user

The natural-language question is **in the POST body** and does not get
written to any log we've found. Searches for the question text return
zero results. Treat this as a privacy plus, not a bug.

### Searching for chat activity

All POSTs to chat/stream across a window:

```
service:simba-intelligence "POST /intelligence/api/v1/chat/stream"
```

By cluster:

```
service:simba-intelligence kube_cluster_name:preview-eks-cluster "POST /intelligence/api/v1/chat/stream"
```

Be aware that volume can be low. On 2026-05-18 across the entire
preview-eks-cluster there were only 2 actual POSTs over 26 hours plus
3 OPTIONS preflights. SI is not high-traffic in nonprod.

---

## What the SI app actually logs

The Python app on the `simba-intelligence-chart` pod is sparse with
chat-related output. Across a 26-hour window with hundreds of thousands
of nginx access lines, only a handful of substantive INFO/WARNING lines
appear. Categories observed:

- **Auth flow**: `WARNING - simba_intelligence.composer.composer_auth -
  Failed to retrieve username and tenant from Symphony Managed session:
  410 Client Error: Gone for url: http://previewmain-dundas-bi-website:9000/managed/api/Session/GetSession/?sessionId=<uuid>`
  Fires when a session expires mid-flight.
- **Source listing**: `Sending GET request to endpoint
  /api/sources/<source-id>` from the Celery worker container.
- **VDD capability resolution**: `[INFO/MainProcess] Using VDD tenant's
  CHAT capability as fallback for tenant <vdd-tenant-uuid>` Fires when
  SI looks up which LLM config to use; this is the bridge log that ties
  a chat to a tenant UUID.
- **Vertex AI errors**: see § LLM observability below.
- **Python tracebacks**: file paths like `simba_intelligence/llm/services/ai_service_vertex_ai.py`,
  `ai_service_factory.py`, `services/redis_service.py`,
  `composer/composer_sources.py`. These are the right module names to
  grep for when chasing specific failure modes.

---

## What the Celery worker does (and doesn't do)

The `simba-intelligence-chart-celery-worker` container handles
**background tasks only**, not chats. The task list captured from a
worker startup:

```
. validate_and_cache_suggestions
. suggestions_stats_task
. purge_and_sync_question_records_task
. generate_suggestions_task
. generate_suggestions_scheduled_task
. cleanup_expired_oauth_tokens_task
```

So a chat does not flow through Celery. It is handled synchronously by
the main `simba-intelligence-chart` pod (uvicorn / FastAPI). When you
search Celery worker logs for a chat, you'll mostly find the periodic
suggestion-generation tasks running.

To see only Celery worker logs:

```
service:simba-intelligence container_name:simba-intelligence-chart-celery-worker
```

The worker's own redis/transport configuration is logged at startup,
including the masked Redis URL `redis://:**@si2-simba-intelligence-chart-redis:6379/0`.
Useful for confirming the worker is connected to the right Redis when
debugging task delivery.

---

## SQL execution: zoomdata-query-engine

Once SI generates a plan and submits a query, execution lands in the
Zoomdata query engine. Volume here is high (~33k logs/day across all
clusters) and patterns to know:

- **Topology lifecycle**: `Topology [id: <uuid>]: Destroyed
  ZEngineSimpleTopolog...` and `... Destroyed CachingTopolog...`
- **Result events**: `Topology [id: <uuid>]: ResultSet for 1D aggregate
  request...`
- **Visualisation context**: `ErrorEvent: ErrorEvent(super=VisEvent(cid=<uuid>...))`
- **Record counts**: `block read in memory in 0 ms. row count = 307`
- **ZEngine sessions**: `ZEngine session created: <session-uuid>`
- **Cancellation flags**: `Cancellation flag can not be found for handle
  <uuid>:0`
- **Connector errors**: `Internal server error, Failed to execute
  request, received an error from connector`

Join keys back to the SI app:
- **Visualisation `cid`** (UUID): visible in browser dev tools when
  reproducing in the Playground; appears in ErrorEvents and Topology
  context.
- **Topology ID** (UUID): internal identifier per query plan.
- **Source ID** (24-char hex, e.g. `66c357dcc24fdd29da7...`): the
  composer source the query targets; matches the source ID in the SI
  app's `/api/sources/<id>` calls.

---

## SQL hitting the data source: zoomdata-edc-<connector>

For deep traces (what SQL hit Postgres / Oracle / Snowflake), each EDC
connector has its own service. The ones observed in Isw-Nonprod:

- `zoomdata-edc-postgresql`
- `zoomdata-edc-mysql`
- `zoomdata-edc-oracle`
- `zoomdata-edc-mongo`

To see what queries an EDC connector executed:

```
service:zoomdata-edc-postgresql kube_cluster_name:<cluster>
```

These logs are the only place the actual generated SQL is visible. If
the customer says "the AI is querying our database too aggressively",
this is where you confirm or deny it.

---

## LLM observability: Vertex AI calls

SI uses Vertex AI for both LLM completion and embeddings. The SDK is the
official `vertexai` Python package (`/workspaces/app/.venv/lib/python3.11/site-packages/vertexai/_model_garden/...`).

### Patterns that fire

Quota exhaustion (most common error in our window):

```
ValueError: Error setting embedding model dimensions: Embedding input failed:
429 Resource exhausted. Please try again later. Please refer to
https://cloud.google.com/vertex-ai/generative-ai/docs/error-code-429 for more details.
```

```
google.api_core.exceptions.ResourceExhausted: 429 Resource exhausted.
Please try again later.
```

```
debug_error_string = "UNKNOWN:Error received from peer ipv4:216.239.32.223:443
{grpc_message:"Resource exhausted ..."}"
```

The Celery task that runs into this most often:

```
[2026-05-18 04:30:05,334: ERROR/MainProcess] Task generate_suggestions_scheduled_task[<id>]
raised unexpected: ValueError(...)
```

So scheduled suggestion generation (the embeddings pipeline) is the
biggest Vertex AI quota consumer, not user queries.

### Useful queries

Anything from the Vertex AI SDK on the SI service:

```
service:simba-intelligence ("vertexai" OR "google.api_core.exceptions")
```

Just the 429 quota errors:

```
service:simba-intelligence "429 Resource exhausted"
```

By tenant (combine with `tenant <uuid>`):

```
service:simba-intelligence "vertexai" "<vdd-tenant-uuid>"
```

### What's not logged

- **Prompt text**: not logged. The prompt SI sends to Vertex AI doesn't
  appear in any captured log line. Same privacy plus as the NL question.
- **Response text**: not logged.
- **Token counts**: not logged at the application level. Vertex AI
  itself charges by tokens but the consumption isn't echoed into SI's
  logs.
- **Per-request latency**: not directly logged. Inferable by timestamp
  delta between consecutive log lines on the same pod.

For real cost/usage telemetry, look at the GCP billing console for
project `agile-tracker-403309` (service account
`~/si-trace-viewer/backend/gcp-sa.json`) rather than trying to derive
it from Datadog.

---

## Other services worth knowing about

While searching for Vertex AI traffic, several additional service tags
surfaced that aren't in the main `datadog-logs.md` catalogue. Treat
this list as a pointer for future investigation; we haven't profiled
each one:

- `agents-runtime`: likely the agentic execution runtime
- `agents-api`: API gateway for agent endpoints
- `data-analyst`: possibly an LLM-backed analyst persona
- `text-summarizer`: LLM-backed summarisation
- `doc-entity-extraction`: entity extraction service
- `doc-assist-query`
- `author-assist-suggestion`
- `author-assist-ingestion`
- `author-assist-collections`
- `generic-completion`: generic LLM completion endpoint
- `justperform-mcp-server`: MCP server for JustPerform

If a customer asks about agentic features, these services are where
the action is. Worth dedicated investigation when one of those deals
comes up.

---

## Reconstruction recipe

End-to-end trace of a single query (best-effort given the sparse
logging):

1. **Identify the chat POST.** Filter `service:simba-intelligence "POST
   /intelligence/api/v1/chat/stream"` for the customer's domain or
   cluster. Capture timestamp, pod, response size.
2. **Note the session ID.** Capture from the browser's `Cookie` header
   while reproducing the issue. Or check the surrounding `check-auth`
   calls for the session.
3. **Find the VDD tenant resolution.** Search `service:simba-intelligence
   "Using VDD tenant"` within ±60 seconds of the chat POST on the same
   pod. The captured UUID is the VDD tenant.
4. **Look for Vertex AI calls.** Search `service:simba-intelligence
   "vertexai"` in the same window for the same pod. If the chat
   succeeded these should be silent (Vertex AI only logs errors); if
   it failed you'll see the stack trace.
5. **Find the query execution.** Switch to `service:zoomdata-query-engine`
   and look for Topology / ZEngine logs in the same window. Capture
   topology IDs.
6. **Find the SQL.** Switch to `service:zoomdata-edc-<connector>` for
   the same time window. This is where the actual generated SQL is
   visible.

Cross-references:
- `datadog-logs.md` for the cluster mapping and full Log Explorer URL
  templates
- `tenant-discovery.md` for the three identifier formats and the
  Composer/SI/Symphony Managed APIs

---

## Known gaps

- **No APM traces.** None of these services are instrumented with
  Datadog APM (confirmed). All correlation is by-hand via log search.
- **No distributed trace IDs.** SI doesn't emit OTel or DD trace IDs
  in its log lines, so there's no single key to follow across services.
- **Sentry handles the frontend.** Errors from the React Playground go
  to Sentry (`o999875.ingest.sentry.io/api/6006079/envelope`), not
  Datadog. To trace a user-facing error end-to-end, you need both.
- **Prompt and response text are intentionally absent.** Don't go
  hunting for them; the design is correct.
