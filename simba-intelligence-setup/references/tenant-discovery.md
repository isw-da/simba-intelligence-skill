# Finding tenants in hosted SI environments

Use this reference when you need to know which tenant (account) a Symphony /
SI session belongs to, or when you need to map a Datadog log entry back to a
named customer (e.g. the customer). Companion to `references/datadog-logs.md`.

The work covers four API surfaces and three different identifier formats.

## Scope note: SI v1 vs SI v2

The Composer-side tenant lookup (the `/composer/api/accounts/<id>` pattern
described below) applies to both SI v1 (Composer-embedded
`/intelligence/playground`) and SI v2 (standalone `/playground`),
because both rely on the same Symphony / Composer backend for
authentication and tenant resolution. The screenshot proof of the
the customer account ID `<account-id>` came from the Composer
admin UI which is shared.

The Datadog correlation patterns (mapping a tenant UUID to logs), however,
only work for SI v1. SI v2 doesn't ship logs to Isw-Nonprod Datadog; see
`datadog-logs.md` § SI v1 vs SI v2 for full context.

---

## Quick wins (no API calls needed)

If you're already logged into a Composer admin URL, the tenant ID is in
the URL hash. Open the tenant you care about, look at the address bar:

```
https://<si-host>/composer/admin.html#accounts/<account-id>
                                                            ^^^^^^^^^^^^^^^^^^^^^^^^
                                                            account / tenant ID
```

That 24-char hex string is a MongoDB ObjectId. It is what Composer calls
the **account ID** and Symphony Managed exposes as the **tenant ID**.

For Amin's environments captured 2026-05-18:

| Tenant | Environment | Account ID |
|---|---|---|
| the customer | `<si-host>` (preview-eks) | `<account-id>` |

(Add others as they're discovered.)

---

## Identifier formats

You will encounter **three different IDs** for what is functionally "the
same tenant", living in different layers. They are not interchangeable.

| Identifier | Format | Where it lives | Example |
|---|---|---|---|
| Composer account ID | 24-char hex (MongoDB ObjectId) | Composer admin URL, `/composer/api/accounts` | `<account-id>` |
| VDD tenant ID | 36-char UUID | SI / VDD logs, LLM capability fallback messages | `e2a11f69-d23d-4ef5-b432-1d85089cf56f` |
| Symphony session ID | 36-char UUID | Composer auth flow, `Set-Cookie`, 410 Gone errors | `d7cf37cf-789a-49a6-b917-56fc5819530b` |

The mapping between Composer account ID and VDD tenant ID is not
documented externally; the safest way to confirm it for a given tenant is
to make one query as that tenant and grep the SI logs for the resulting
VDD tenant UUID in the planning phase (`simba-intelligence-chart-celery-worker`
container).

---

## Authentication you'll need

All Composer / Discovery / SI APIs are **cookie + CSRF** based, not token
based for the most part. From the HAR captured 2026-05-18:

- **Session cookie**: set by the Symphony login flow (you already have it
  if you're logged into the browser)
- **CSRF token**: visible as the `x-csrf-token` request header on every
  XHR; the page injects it from a meta tag at load time
- **Accept header**: must be `application/vnd.composer.v3+json` for the
  Composer/Discovery APIs to return JSON
- **Custom auth flag**: `x-www-authenticate: true` is set on every
  authenticated XHR

There is also an `access_token` query param used by Discovery in the
admin UI (`/discovery/admin.html?access_token=<uuid>`); that's the
Symphony Managed access token, separate from the session cookie. For
admin-side scripting you can usually ignore it and rely on the cookie.

### Pulling cookies for scripting

The lazy way: copy as cURL from Chrome dev tools (right-click any request
→ Copy → Copy as cURL). The cleaner way:

```bash
# In a logged-in browser tab on <si-host>, run in dev tools console:
copy(document.cookie)
# Now paste into shell:
export SIMBA_COOKIE='<pasted cookie string>'

# Get CSRF token (also from dev tools, Application → Storage, or grep the page):
export SIMBA_CSRF='9HoJUtAfAEidj7WA5rOQRn2q...'
```

---

## 1. Composer API: the canonical tenants list

### List all accounts (tenants)

```bash
curl -s "https://<si-host>/composer/api/accounts" \
  -H "Accept: application/vnd.composer.v3+json" \
  -H "x-csrf-token: $SIMBA_CSRF" \
  -H "x-www-authenticate: true" \
  -b "$SIMBA_COOKIE" | jq
```

Returns a JSON array. Each element contains at minimum the account ID,
display name, and probably enabled/disabled state. Captured payload was
~970 bytes for a small list; large estates will be bigger.

### Get a single tenant

```bash
curl -s "https://<si-host>/composer/api/accounts/<account-id>" \
  -H "Accept: application/vnd.composer.v3+json" \
  -H "x-csrf-token: $SIMBA_CSRF" \
  -H "x-www-authenticate: true" \
  -b "$SIMBA_COOKIE" | jq
```

Returns the full account record including custom attributes (the "Custom
attributes name value pairs" shown in the Edit Tenant UI) and whether
the tenant is disabled.

### Other useful Composer endpoints

```
GET /composer/api/user                            # current user (3.8 KB)
GET /composer/api/license                         # license details
GET /composer/api/version                         # Composer version (155 B)
GET /composer/api/connections/statistics          # data connection counts
GET /composer/api/sources/statistics              # source counts
GET /composer/api/visuals/statistics              # visualisation counts
GET /composer/api/dashboards/statistics           # dashboard counts
GET /composer/api/account-attributes/reserved     # reserved attribute names
GET /composer/api/customization/themes/active     # active theme (23 KB)
```

The Discovery API at `/discovery/api/...` mirrors most of these for
Dundas-style admin views (same paths, parallel surface).

---

## 2. SI Intelligence API: source and auth endpoints

Less useful for tenant discovery (it doesn't expose a "list tenants"
endpoint), but documented here for completeness. Captured from earlier
logs and HAR:

```
GET /intelligence/api/v1/auth/check-auth          # session validity check
GET /intelligence/api/v1/auth/token               # token issuance
GET /intelligence/api/sources/<source-id>         # source CRUD (note: no /v1)
```

This is the surface NLQ requests land on. Anything that knows about
VDD tenant UUIDs lives behind here, but it's not externally exposed for
admin queries.

---

## 3. Symphony Managed API: session lookup

The endpoint that errored in our earlier 410 Gone log. Use to map an
active session ID to its owning tenant.

```bash
curl -s "https://<si-host>/managed/api/Session/GetSession/?sessionId=<session-uuid>" \
  -b "$SIMBA_COOKIE" | jq
```

If the session is alive, the response contains `username` and `tenant`
fields (which is what SI was trying to read when it logged the 410).

This is the **only** path that resolves a Symphony session UUID to a
named tenant. If you have a session ID from browser cookies or from a
Datadog log, this is how you confirm whose session it is.

---

## 4. Datadog Logs API: list all tenants with recent activity

Indirect, no auth to the SI / Composer APIs required. Pulls every
`tenant <uuid>` substring from VDD planning logs over a window and
dedupes. You get every VDD tenant UUID that's had activity but no
names, which is useful for "which tenants are alive" reports.

```bash
curl -s -X POST "https://api.datadoghq.com/api/v2/logs/events/search" \
  -H "DD-API-KEY: $DD_API_KEY" \
  -H "DD-APPLICATION-KEY: $DD_APP_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "filter": {
      "query": "service:simba-intelligence \"Using VDD tenant\"",
      "from": "now-30d",
      "to": "now"
    },
    "page": { "limit": 1000 }
  }' \
  | jq -r '.data[].attributes.message' \
  | grep -oE 'tenant [a-f0-9-]{36}' \
  | sort -u
```

To go the other way (look up logs for a known tenant), use the UUID as
a substring query. See `datadog-logs.md` § Filtering by tenant.

---

## Tying it together: from the customer to Datadog logs

The end-to-end recipe for "show me everything the customer did today":

1. **Get the Composer account ID.** Open the Composer admin, navigate to
   the tenant, copy the hex from the URL hash. For the customer:
   `<account-id>`.
2. **Get the VDD tenant UUID.** Either ask DevOps for the mapping, or
   make one query as a user belonging to that tenant, then grep Datadog:
   ```
   service:simba-intelligence "Using VDD tenant" container_name:simba-intelligence-chart-celery-worker
   ```
   Sort by timestamp, find the entry that lines up with your test query,
   note the UUID.
3. **Filter Datadog by that UUID.**
   ```
   service:simba-intelligence "<vdd-tenant-uuid>"
   ```
4. **Join to query execution.** If you want the SQL the LLM produced,
   capture the visualisation or topology ID from the SI log and search:
   ```
   service:zoomdata-query-engine "<topology-id>"
   ```

This is the full trace for one tenant's NLQ on a hosted SI instance,
end-to-end.

---

## Open questions

- Is there an official Composer endpoint that returns the VDD tenant
  UUID alongside the account record? (Worth a quick `curl
  /composer/api/accounts/<id>` to check the response shape.)
- Is `simbaintel.logianalytics.com` (qa2 cluster) on the same Composer
  schema, or does it use a different multi-tenancy model? Re-run the
  HAR capture there to confirm.
- The 410 Gone we saw in the earlier session lookup happened because
  the session was expired, not because the endpoint is wrong. Worth
  confirming the live-session shape by capturing one mid-flight.
