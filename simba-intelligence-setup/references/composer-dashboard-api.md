# Building Composer dashboards via the discovery API (verified on SI 26.2)

Verified end to end 2026-07-20 against SI 26.2.0 (kind, chart install) building
the FRC webinar dashboard. Complements the generic dashboard-builder guidance
with what this stack actually accepts.

## The workflow that works

1. `GET /discovery/api/sources` → source id (vendor media type
   `application/vnd.composer.v3+json` on every call; basic auth admin works).
2. `GET /api/sources/{id}/visual-types` → pick types; the id field is
   `visualTypeId`.
3. `GET /api/sources/{id}/visual-types/{vt}/initial-visual` → template. Never
   hand-craft visual JSON.
4. Modify template: `level = "IN_DASHBOARD"`, drop `id`/`visId`, set variables
   and filters, `POST /api/visuals`.
5. `POST /api/dashboards` with widgets referencing the visual ids
   (2-element `path`/`params`, no `unifiedBarCfgs`).

## 26.2-specific findings (the bits the generic guide gets wrong or misses)

- **Visual-level filters use `path`/`operation`, not `name`/`operator`:**
  `{"path": "alert_type", "operation": "IN", "value": ["cycle", "fan_in"]}`
  in `source.filters`. The wrong keys render as "invalid filters" in widgets.
- **Metric function vocabulary:** `sum` and `distinct_count` verified. The row
  count pseudo-metric `{"name": "count"}` is NOT accepted on this instance
  (KPI renders "Metric: Unavailable"); use `distinct_count` on a key column.
- **Every metric slot needs `func`, including colour slots.** A `Bar Color`
  entry without `func` fails the whole visual with
  "unsupported metric function".
- **Variable names differ per type:** KPI uses `Metric`/`Comparison Metric`
  (and `Conditional Formatting` entries carry their own metric refs to update);
  UBER_BARS uses `Multi Group By`/`Metric`/`Bar Color`; DONUT uses
  `Group By`/`Size`. Always read the template's variables rather than assuming.
- **SPA routes** (for screenshots/deep links): app root redirects to
  `/discovery/visualization/home`; a dashboard lives at
  `/discovery/visualization/{tenantId}_{dashboardId}`; sources list at
  `/discovery/source/library`. Do not follow the redirect server-side when
  proxying: the SPA computes its asset base from `location.pathname` and
  mis-builds `//app/...` URLs (Spring 400s double-slash paths).
- **Dashboard data flows over a WebSocket**, so a plain HTTP reverse proxy
  renders the shell with spinners forever. Any auth-injecting proxy for
  screenshots must pass the `Upgrade: websocket` handshake through (raw TCP
  byte-pump after the handshake is enough).
- **First write after a pg_restore may hit stale sequences** (ACL tables).
  See backup-restore.md lesson 4.
- **KPI `Comparison Metric` must be non-empty** (26.2): setting it to `[]` to
  hide the comparison row crashes the widget with the classic
  `TypeError: ... (reading 'value')`. Keep it equal to `Metric` and accept the
  cosmetic "$0.00 vs" row, or restyle in the UI.
