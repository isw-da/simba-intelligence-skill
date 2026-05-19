# Platform-only modelling (no data-side changes)

What works and what doesn't when you have to deliver an SI source
without touching the underlying data. Critical for customer tenants
where the data is owned by the customer's data team and you cannot
ALTER, UPDATE, or DELETE.

Tested 2026-05-19 on the SI build hosted at simba.logisymphony.com.
Results are specific to that build and may change in future versions.

---

## The two SI features that look like the answer

### Custom SQL Entity

**Promise**: define an entity by SQL instead of a single collection.
The SQL can JOIN, CAST, DISTINCT, COALESCE, compute derived columns,
filter to a date window — anything Postgres accepts. None of it
touches the underlying tables.

**API shape (works)**:

```python
payload = {
    "name": "...",
    "storage": {
        "dataEntities": [{
            "id": "enriched",
            "name": "Enriched",
            "type": "CUSTOM_SQL",
            "customSql": {
                "connectionId": "<conn-id>",
                "sql": "SELECT ... FROM ... LEFT JOIN ..."
            }
        }],
        "joins": []
    }
}
# POST /discovery/api/sources -> 201
```

Field auto-discovery works: every column in the SELECT becomes a
nativeField with inferred dataType (TIME / NUMBER / ATTRIBUTE).
Computed columns (`(VAL_SUCCESS - VAL_FAIL) AS net_collection_value`)
are detected as NUMBER with `defaultMetric: SUM`.

**Empirical issue**: when queried via NLQ, the returned values are
**heavily filtered or sampled** in ways the platform doesn't
document. A Custom SQL Entity sourced from the same underlying tables
as a working single-collection source returned 1,837,000 for a
`SUM(VAL_SUCCESS)` whose truth is 10,833,290,438 — off by a factor of
~6000. Distinct counts came back as 2 when the truth was 1000.

We could not determine whether this is:
- An auto-injected time filter being applied to the Custom SQL's
  inner `MONTH_DT`
- A row-count limit on Custom SQL entities specifically
- A sampling default that doesn't apply to regular collections
- A query-planner bug

**Until this is understood, do not rely on Custom SQL Entity for
production numbers.** It works structurally; it does not work
empirically.

### Derived Field API

**Promise**: define a calculated field at the SI source level by
expression, referencing other fields by name. Visible in the UI as
"Add Derived Field".

**Status**: broken on this build. `POST /discovery/api/sources` and
`PUT /discovery/api/sources/{id}` reject all attempted shapes with
either:
- HTTP 400: unrecognised key combinations
- HTTP 500: NullPointerException on
  `com.zoomdata.model.source.field.NativeOrigin.setDataEntityId`

The only key the validator recognises inside `origin.derivedOrigin`
is `expression`, but supplying it alone triggers the 500. Supplying
it plus any other key (`dataEntityId`, `sourceFields`) triggers the
400.

**Workaround**: until SI fixes this, derived metrics need a different
path. See "What actually works" below.

---

## What actually works in pure platform-only mode

Without `Custom SQL Entity` (semantically broken) and without
Derived Fields (API broken), the SI-only toolkit is reduced to:

1. **Single-collection entities** with field-level labels, visibility,
   metadata
2. **Joins** between collection entities
3. **Rules Management** (`/api/v1/rules`)
4. **Global Settings** (timebar enable/disable)

That toolkit handles:

- Labelling fields
- Hiding noise fields
- Adding `fieldMetadata.description` for LLM disambiguation
- Constraining the chat agent's behaviour through rules
- Disabling the UI time bar

It does **NOT** handle:

- Casting a column type mismatch on a join key
- Deduplicating a dimension with PK violations
- Backfilling sparse columns
- Filtering out orphan facts that don't match the dimension
- Pre-computing derived metrics (Net Collection Value, ratios, etc.)
- Constraining the auto-injected time filter range

For each of those, the only platform-only options are:

1. Accept the data as-is and let the LLM produce sparse or wrong
   answers
2. Ask the customer's data team to apply the fix in their data layer
3. Build a dedicated demo schema you control

---

## Recommended approach for customer tenants

For Amplifin or any tenant where you cannot touch data:

### Phase 1: Data hygiene as a customer ask

Before building any source, send the customer a short list of
preconditions their data must meet. If their data fails any of these,
either ask them to fix it on their side, or build the source on a
copy schema where you do the fix.

The list:

```sql
-- 1. Dimension PK uniqueness
SELECT 'fail' WHERE EXISTS (
  SELECT 1 FROM dim_table GROUP BY pk_col HAVING COUNT(*) > 1
);

-- 2. FK coverage at least 95%
SELECT (COUNT(DISTINCT fk_col)::float
        / NULLIF((SELECT COUNT(*) FROM dim_table), 0)) AS coverage
FROM fact_table;
-- coverage must be ≥ 0.95

-- 3. Join key type consistency
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE column_name = '<join_key>'
GROUP BY 1,2,3;
-- all rows same data_type

-- 4. Date range fits a recent window
SELECT MIN(date_col), MAX(date_col) FROM fact_table;
-- max should be within the last 3 months

-- 5. Null density on numeric columns
SELECT COUNT(metric)::float / NULLIF(COUNT(*),0) FROM fact_table;
-- should be ≥ 0.5 on any metric you intend to demo
```

Hand this list to the customer's DBA the week before. Their fixes
are usually cheap (CAST, DELETE duplicates, refresh dates).

### Phase 2: Single-collection sources with what's there

Once the preconditions are met, build single-collection sources
exactly as documented in `data-source-modelling.md`. Apply labels,
metadata, hide flags, rules.

This is the path that has produced exact-match NLQ answers in our
testing. It's not platform-only in the strict sense (the
preconditions are data-side), but it's the only path that delivers
demo-grade accuracy on this SI build.

### Phase 3: Derived metrics

For business ratios and net values the customer wants but doesn't
have as fields:

Option A: Customer adds them as computed columns or views on their
side. Cleanest.

Option B: Build a separate "demo" schema in their environment that
you populate from their tables, with the derived columns you need.
Refresh nightly. They keep their tables clean.

Option C: Skip derived metrics for the demo. Constrain the question
deck to what their data already has.

### What rules and metadata still buy you

Even with no data-side help, Rules Management and `fieldMetadata`
deliver:

- Hallucination prevention on unknown fields
- Synthesis prevention on derived business metrics (EBITDA etc.)
- Source scoping (when multiple sources exist)
- Currency formatting
- Data-window enforcement
- Null-grouping discipline

These are entirely platform-side and worth applying even without
data-side changes. They just won't fix structural data problems.

---

## Cross-references

- `data-source-modelling.md` — recipe for single-collection sources
- `nlq-stress-testing.md` — the 25-test audit methodology
- `best-practices-data-sources.md` — prompting and setup guidance
- `audit-amplifin-bugs.md` — bug log including the Custom SQL and
  Derived Field issues
