# Importing to a customer tenant

How to deploy the debit-order-payments semantic model in a customer
tenant **without touching their underlying data**, and without
overloading their compute.

Verified 2026-05-19 against the the customer VDD demo, producing 92% NLQ
pass rate (11/12 exact match) on first run.

---

## What gets imported

A single SI data source with eight entities:

| Entity | Type | Compute |
|---|---|---|
| `branch` | SINGLE_COLLECTION (the dim) | one SELECT * |
| `legal` | CUSTOM_SQL (dedup'd) | one DISTINCT ON + SELECT |
| `perf_monthly` | CUSTOM_SQL (per-row, with date) | one LEFT JOIN, no GROUP BY |
| `perf_alltime` | CUSTOM_SQL (one row per branch, no date) | one LEFT JOIN + GROUP BY branch_cd |
| `due_monthly` | CUSTOM_SQL | one LEFT JOIN, no GROUP BY |
| `due_alltime` | CUSTOM_SQL | one LEFT JOIN + GROUP BY branch_cd |
| `fee_monthly` | CUSTOM_SQL | one LEFT JOIN, no GROUP BY |
| `fee_alltime` | CUSTOM_SQL | one LEFT JOIN + GROUP BY branch_cd |

All transformations happen inside the SI source definition. No
ALTER, no UPDATE, no DELETE on the customer's tables.

---

## Why two entities per fact (monthly + all-time)?

This solves the LLM auto-time-filter problem we observed in testing.

- **All-time entity** has no date column. The LLM can't auto-filter by
  date. Returns full all-time totals on bare aggregate questions.
- **Monthly entity** has a date column. The LLM applies its
  "last-month + current-month" filter, which is correct behaviour for
  trend questions and single-month lookups.

When the user asks "what's the total X", the LLM picks the all-time
entity. When they ask "X by month" or "X in May 2026", it picks the
monthly entity. Both behaviours are right.

---

## Compute cost on the customer's data warehouse

Per NLQ chat turn, SI runs one query against their warehouse:

| Question type | Entity used | Cost |
|---|---|---|
| "How many branches?" | `branch` | `SELECT COUNT(*) FROM branch` — index seek |
| "Total X" | `*_alltime` | one full scan + GROUP BY branch_cd |
| "Top regions by X" | `branch JOIN *_alltime` | one full scan + GROUP BY |
| "X by month" | `*_monthly` | one full scan with LEFT JOIN |
| "X for May 2026" | `*_monthly` with month_dt filter | indexed range scan if MONTH_DT indexed |
| "X per industry" | three-table JOIN | full scan + LEFT JOINs |

For Fabric:
- Customer's largest table (`idm_branch_perf_v1` at typical scale)
  is the cost dominator
- Single GROUP BY on a 1M-row fact takes seconds; on a 100M-row fact
  takes 10-30 seconds without indexes
- If the customer has any indexed views over their facts, point the
  Custom SQL at those instead

If compute is tight, mitigate as follows:

1. **Enable rawCacheEnabled on the all-time entities.** Add this to
   each `*_alltime` entity in the source JSON:

```json
"cacheSettings": {
  "rawCacheEnabled": true,
  "rawCacheTtl": 1440
}
```

   First query runs the GROUP BY on Fabric. Subsequent queries within
   the 24-hour TTL hit SI's cache. Cost goes from N×scan to 1×scan
   per day per entity.

2. **Index `BRANCH_CD` and `MONTH_DT` on their fact tables.** If
   their data team can add these, every Custom SQL JOIN gets faster.

3. **For the demo period, materialise once.** Ask their team to run
   the eight Custom SQL queries once as views in their warehouse,
   then point the SI source's entities at those views. Zero query
   cost for SI; warehouse handles refresh.

---

## Step-by-step import to the customer

### Prerequisite: connection already configured

The the customer Fabric Lakehouse connection is at
`/discovery/api/connections/<id>`. Capture the `id` from the SI
Connections page. We'll refer to it as `<CONN_ID>`.

The Lakehouse name in their workspace becomes the `<SCHEMA>` arg
(for Fabric this is typically the database name; for Postgres it's
the schema name).

### Step 1: dry-run the script

```bash
cd ~/simba-intelligence-skill/use-cases/debit-order-payments

python3 sql-templates.py build \
  --base https://<si-host> \
  --key  <your-api-key> \
  --connection <CONN_ID> \
  --schema <SCHEMA_OR_DATABASE>
```

Output is the new source ID. Capture it.

### Step 2: apply rules

```bash
python3 ../../simba-intelligence-setup/scripts/apply_rules.py \
  --base https://<si-host> \
  --key <your-api-key>
```

(Rules are tenant-wide; one-time setup per tenant.)

### Step 3: verify

Open in playground:

```
https://<si-host>/playground?sourceId=<new-source-id>
```

Run the 12-question verification deck from `demo-flow.md`. Target
≥ 90% pass. If failing, check:

- Customer's `BRANCH_CD` column type consistent across tables
  (`text` or all `bigint` — not mixed)
- Customer's fact tables actually have data in the recent month
  range (check `MAX(MONTH_DT)` in their warehouse)
- Connection has SELECT permission on every named table

### Step 4: hand off

The source is now reachable by the CTO's team. URL goes in their
welcome email. No further setup needed on the SI side.

---

## Adapting for differently-named tables

If the customer's tables aren't called `branch`, `branch_legal_entity`,
`idm_branch_perf_v1` etc., edit the SQL templates in
`sql-templates.py` before running build.

The templates are at the top of the file as constants:

```python
LEGAL_SQL = """SELECT DISTINCT ON ("BRANCH_CD"::text)
  "BRANCH_CD"::text AS branch_cd,
  ...
FROM {schema}.branch_legal_entity"""
```

Change the table name and column names inline. Keep the output
column aliases (`branch_cd`, `industry`, etc.) the same — the rest
of the SI semantic layer references those aliases.

---

## What's still required at the data layer

Even with Custom SQL Entity handling cast, dedupe, and derive, three
data preconditions still matter. If they fail, NLQ accuracy will
drop.

| Precondition | Why it matters | Detection |
|---|---|---|
| Fact tables have rows in the last 2 months | LLM auto-time-filters to current month + previous month for monthly entity questions; outside that, returns empty | `SELECT MAX(MONTH_DT) FROM <fact>` ≥ 30 days ago |
| Dimension PK (BRANCH_CD) is unique in the dim | Even with Custom SQL dedupe on legal_entity, if the branch dim itself has dupes, joins fan out | `SELECT COUNT(*), COUNT(DISTINCT BRANCH_CD) FROM branch` should match |
| Numeric columns aren't 100% null | Sparse columns return 0/null on aggregates regardless of layer | `SELECT COUNT(*), COUNT(<col>) FROM <fact>` density ≥ 50% |

If any of these fail on the customer's data, surface to the CTO. The
fixes are owned by their data team, not us.

---

## Compute headroom on the customer's F32

Approximate cost per chat turn assuming their `idm_*` facts have
1M-10M rows:

- All-time aggregate query: 0.5-3 capacity units (1 GROUP BY)
- Monthly query (no aggregation): 1-5 capacity units
- Three-table JOIN per industry: 2-10 capacity units

At F32 (32 capacity units sustained), one chat turn is well within
budget. Concurrent users matter more: 5 concurrent NLQ chats on a
10M-row fact would peak around 50-150 CU, which a F32 can absorb
for short bursts but not sustained.

If sustained concurrent demo usage is the worry: enable
`rawCacheEnabled` per the above. Sustained capacity drops to near
zero once results are cached.
