---
name: edc-connector-testing
description: >
  Adversarially test an EDC (External Data Connector) you are building or have
  built for Logi Composer / Simba Intelligence, before it goes anywhere near a
  customer source. Use whenever the user is building, debugging, hardening, or
  signing off a connector: a GraphQL EDC, a JDBC connector (Oracle, Postgres,
  Teradata, Trino), a Microsoft Graph / SharePoint EDC, a SAP HANA / Datasphere
  EDC, or a connector from the Zoomdata/EDC SDK template. Trigger on phrases like
  "test my connector", "is my EDC ready", "test the EDC", "connector QA",
  "EDC conformance", "does my connector pushdown work", "test introspection",
  "my connector returns wrong data", "test it through the Playground", "build an
  EDC connector and test it", or "connector go/no-go". Provides an eight-category
  connector test plan (connectivity, schema/introspection, data fidelity, query
  and aggregation parity, determinism, error handling and security, secrets and
  logging, performance) plus the Composer/SI end-to-end integration layer. Hands
  off to the nlq-testing skill once the pipe is proven, for the query-correctness
  layer on top. Do NOT use for testing the analytics/semantic-layer correctness of
  an already-connected source (that is nlq-testing), nor for SI install/config
  (that is simba-intelligence-setup).
---

<!-- Skill version: 2026-06-01 -->
<!-- Canonical source of truth: https://github.com/isw-da/simba-intelligence-skill (edc-connector-testing/) -->

# EDC connector testing

This skill turns an EDC connector from "it returned some rows in the Playground" into
something you would stake a customer source on. A connector is the pipe; nlq-testing
tests the water. Prove the pipe first.

The discipline, distilled from the GraphQL EDC test suites (`isw-da/edc-graphql`,
`test-suite-v2.sh`): a connector result is only correct if it matches an independent
baseline path. Always have a source-of-truth route (a direct SQL query, a direct API
call, the source's own console) to check the connector's output against. Without a
baseline you are testing that the connector agrees with itself, which proves nothing.

## When to reach for this

Reach for it when the user is building or hardening an EDC connector and wants to know
where it breaks: introspection, type mapping, pushdown, pagination, auth, error
handling, secrets, performance, and the Composer/SI end-to-end path. Output shape: a
PASS/FAIL line per check with a severity (CRITICAL/HIGH/MEDIUM), grouped by category,
ending in a go/no-go verdict.

## Test at two levels, always

1. **Native protocol (direct):** hit the connector at its own interface (Thrift, REST,
   JDBC, the EDC endpoint) without Composer in the way. Isolates connector bugs from
   integration bugs.
2. **Composer/SI integration (end to end):** the same checks through the Composer API
   and the SI Playground, as a real user would. A connector can pass direct and fail
   integrated (registration, type mapping, session, pushdown), so both are required.

## How to use this skill

1. **Establish the target and the baseline.** Capture: the connector name and repo,
   the EDC type (`{EDC_TYPE}`), the backing source (`{SOURCE}`), the independent
   baseline path (`{BASELINE}`, e.g. direct SQL against the same data), and the
   integration surface (Composer API and SI Playground). Do not test until the baseline
   exists.

2. **Work the eight categories** in `references/connector-test-plan.md`. They are, in
   order: connectivity and registration; schema and introspection; data fidelity;
   query and aggregation parity (vs baseline); determinism; error handling and
   security; secrets and logging; performance and concurrency.

3. **Generalise to the source shape.** Flat arrays, nested/Relay (Connection -> Edge ->
   Node), and tabular (JDBC rows) each have different traps. Verify the connector
   extracts the actual records, not the wrapper, and that source-type to Composer-type
   mapping holds (integer, numeric, boolean, enum, timestamp, UTF-8 text).

4. **Run the security category in full.** Injection through query parameters
   (SQL/GraphQL/XSS), malformed bodies, invalid auth, unreachable source with timeout,
   prompt injection through the SI layer, and the non-negotiable: no API keys or
   passwords in connector logs.

5. **Then hand off to nlq-testing.** Once the pipe is proven, the analytics correctness
   on top (does NLQ over this source pick the right columns and aggregations) is the
   nlq-testing skill. The connector kit proves the data arrives intact; nlq-testing
   proves the questions get answered right.

## The non-negotiables (CRITICAL category)

- Connector registers in Composer and reports available=true.
- Introspection exposes the expected collections/tables and their fields.
- Data matches the baseline path, row for row, on a known query.
- Primary keys unique, expected-non-null fields never null, type mapping correct.
- No secret (API key, password, token) ever appears in logs.
- Composer rejects unauthenticated requests; SI rejects an invalid session.

## Guardrails

- Keep customer source specifics out of any committed copy. Use generic placeholders;
  do not bake in a customer's URLs, keys, table names, or row values.
- A connector that can leak a credential in a log line is a NO-GO regardless of how
  well it queries. Treat that as Critical and stop.
- The worked reference implementation is `test-suite-v2.sh` in `isw-da/edc-graphql`.
  Read it for the concrete bash assertions behind these categories.
