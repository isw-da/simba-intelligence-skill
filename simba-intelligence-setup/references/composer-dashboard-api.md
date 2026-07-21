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

## In-Composer Simba Intelligence assistant + AI visuals (26.2 feature flags)

Two AI capabilities inside Composer dashboards, gated by Composer feature flags
(Confluence "Composer Feature flags"), verified live 2026-07-21:
- `symphony-chat` (default false): the "Open Simba Intelligence Chat" assistant on
  dashboards. When on, it answers governed NL questions against the same sources the
  dashboard uses (numbers match the tiles and any Claude/MCP answer). It DESCRIBES
  (table + NL conclusion; prose varies run-to-run, numbers do not) and returns a
  structured TEXT bar-chart breakdown when asked to "create a chart". Precondition:
  `GET /api/v1/config/llm/status` returns `{"is_configured":true}`. Panel UX: paste then
  click the send arrow (Return does not submit).
- "Create visual with AI" (+ menu, BETA badge): WORKS on this build. It opens the SI
  assistant in build mode and renders a real governed visual (correct numbers) with a
  "Save to Dashboard" button. GOTCHA: the menu item is disabled ONLY while the chat panel
  is open in build mode (frontend `disabled: (saasMode&&limit) || currentComposerType==="Visual"`),
  so CLOSE the chat before opening the + menu. (Earlier note that it needed
  `symphony-ai-visuals-flow` set was wrong — that flag selects a chatflow variant, not the
  on/off gate for this build.)
- `symphony-ai-sql-flow` (none): chatflow for AI SQL generation in source creation.
Full behaviour + capture gotchas: isw-da/logi-si-docs composer-ai-assistant-26.2.md.

## Reskin: theme + logo (verified 2026-07-21)

To reskin Composer (e.g. a purple "Simba Intelligence" / symphony look) and put a
custom logo top-left, all via API, reversible:
- Themes: `POST /discovery/api/customization/themes` (body `{"masterThemeId":"modern",
  "name":"...","content":{...}}`, strip id/system) then
  `POST /discovery/api/customization/themes/activate {"id":"<id>"}`.
  Skin colours: `content.variables.colors.brandColor` (top nav bar), `primary`/
  `intentPrimary`/`accentColor`/`linkColor`; chart colours `variables.palettes.
  DefaultSequential`/`DefaultCategorical`. There is no supplied "symphony" theme;
  the `d+a_light` system theme uses `$symphony.*` tokens if you want that base.
- Logo: `branding.headerLogo` is varchar(40) (a filename ref, not a data URI — a
  data-URI PUT 409s). Clean route is a custom-CSS override:
  `POST /discovery/api/branding/customCss` (NO `.css`), multipart field `fileData`
  = the CSS file (POST replaces; GET current at `/customCss.css`, append, re-POST).
  Rule: `img[src*="headerLogo"]{content:url("data:image/png;base64,...")!important;
  height:34px!important;width:auto!important}`.
Full recipe + revert: isw-da/logi-si-docs composer-theming-branding-26.2.md.
