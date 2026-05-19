# Datadog assets relevant to SI

Inventory of dashboards, monitors, synthetic tests, and saved views in
the `Isw-Nonprod` Datadog org related to SI / Logi Symphony. Captured
2026-05-18. Refresh by re-running the searches below; this is a
point-in-time snapshot.

The headline: there is very little SI-specific tooling built. One
generic K8s dashboard, five infrastructure-level monitors, no
discoverable synthetic tests, no notebooks. If you need a real cockpit
for an SI deal, you'll build it yourself.

---

## Dashboards

Search: `https://isw-nonprod.datadoghq.com/dashboard/lists?q=logi`

| Name | Owner | Team | Type | URL |
|---|---|---|---|---|
| LogiSymphony-Dev | Tata Reddy | LogiSymphony | Custom (shared) | [`/dashboard/r2b-jd2-rqg/logisymphony-dev`](https://isw-nonprod.datadoghq.com/dashboard/r2b-jd2-rqg/logisymphony-dev) |
| Azure Logic App | Datadog | (integration) | Integration | n/a |

The LogiSymphony-Dev dashboard is **generic Kubernetes / host metrics**
(`avg:kubernetes.cpu.system.total{*}`, `system.cpu.user`, system uptime,
disk space, RAM breakdown). It does not surface SI-specific signals
(chat volume, Vertex AI errors, query latency, per-tenant activity).
Useful for the underlying cluster health but not for "is SI healthy".

Searches for `simba`, `composer`, `zoomdata`, `dundas` returned no
matching custom dashboards.

---

## Monitors

Search: `https://isw-nonprod.datadoghq.com/monitors/manage?q=logisym`

Five LogiSym monitors exist, all infrastructure-level, all currently OK:

| Name | Type | Notes |
|---|---|---|
| LogiSym - CPU usage is high for host {{host.name}} | Metric | Per-host CPU |
| LogiSym - Kubernetes Pods Restarting | Integration (kubernetes) | The one that fired the original event we started from |
| LogiSym - Pod not ready | Integration | Pod readiness probe |
| LogiSym - RDS CPU Utili... | Metric | RDS Postgres CPU |
| LogiSym - {{url.name}} is unreachable | Integration | URL synthetic wrapper |

What's missing (worth proposing if SRE owns this):

- No monitor on the `composer_auth 410 Gone` pattern (which fires
  regularly in preview-eks-cluster).
- No monitor on Vertex AI 429 quota errors.
- No monitor on chat volume / chat latency / failed chats.
- No monitor on per-tenant activity drops.

If you're about to demo an "SI observability" angle to a customer, this
gap is worth flagging as something you'd build out together.

Searches for `simba` returned 0 monitors.

---

## Synthetic tests

Search: `https://isw-nonprod.datadoghq.com/synthetics/tests`

None matching `simba`, `logisymphony`, `symphony`, `composer`. The `LogiSym
- {{url.name}} is unreachable` monitor implies there is at least one
synthetic test wired to it, but the synthetic itself isn't visible to
Amin in this org. Probably scoped to a different team.

The 15 HTTP tests visible by default belong to the `zenith` team and
target `ai-dev.insightsoftware.com`, unrelated to SI.

If you need a synthetic for an SI URL, just create one. Datadog →
Digital Experience → Synthetic Monitoring → New Test.

---

## Notebooks

Search: `https://isw-nonprod.datadoghq.com/notebook/list`

None owned by Amin. None discoverable for SI by title search. The
"Created by me" view is empty.

---

## Saved views

Saved views in the Log Explorer are personal by default. Amin has none
saved as of capture. Worth saving the queries built in `datadog-logs.md`
and `query-tracing.md` as views for one-click access. The "My View"
button at the top of Log Explorer is where this lives.

Suggested saved views to create:

- `SI - chat POSTs` → `service:simba-intelligence "POST /intelligence/api/v1/chat/stream"`
- `SI - composer_auth 410` → `service:simba-intelligence "composer_auth" "410"`
- `SI - Vertex AI 429` → `service:simba-intelligence "429 Resource exhausted"`
- `SI - tenant <UUID>` (per customer) → `service:simba-intelligence "<vdd-tenant-uuid>"`
- `Query engine errors` → `service:zoomdata-query-engine status:error`

---

## What this implies

The current Datadog footprint for SI is basically "infrastructure
monitors, one dashboard, no application-level cockpit". When you're
running a trial and a customer asks "show me observability", the answer
today is "we have raw logs and you can build any view you want", not
"here's the dashboard". That's an opportunity, not a problem, but worth
being honest about.

For the next deal where SRE or the customer wants a real SI cockpit, the
work to do is:
- A dashboard with chat volume, chat latency p95, Vertex AI error rate,
  per-tenant activity, 410 composer_auth rate, top-N error stack traces.
- Monitors on the four patterns listed above.
- A saved view per active customer keyed on their VDD tenant UUID.
