# Derived fields

Pre-computed business metrics. Three viable paths, ranked by
preference for a customer tenant.

## Path 1 (preferred, if customer permits): customer's data team adds them

The cleanest answer for a payments processor is to ask their data
team to add the derived columns at source. They control their data;
they should own its shape. Send them the SQL below and let them
decide whether to add as views or generated columns.

## Path 2: separate demo schema you control

If touching customer tables is off the table but you can stand up a
separate schema in their environment that pulls from theirs, do that.
Add the derived columns there. SI points at the demo schema; the
customer's tables are never touched.

## Path 3: live without derived metrics

If neither of the above is possible, accept that:
- Ratios (success rate, failure rate) will be computed via rule-driven
  SUM-numerator-over-SUM-denominator at NLQ time, not as fields
- Net values (collection value, fee revenue) cannot be pre-computed;
  ask for them with explicit subtraction in the question

## Why not SI's own features?

We investigated both. Neither works reliably on this SI build:

- **Derived Field API**: returns HTTP 500 NullPointerException on
  every attempted shape. Bug filed; see
  `simba-intelligence-setup/references/audit-amplifin-bugs.md` #14.
- **Custom SQL Entity**: structurally works but NLQ against it
  returns aggressively sampled/filtered results (off by ~6000x on a
  bare SUM in our test). Bug filed; see #15.

Until either is fixed by SI product, derived fields must be solved
at the data layer, not the platform layer.

## What columns to add (when you can)

For a debit-order processor, add these two columns to the
performance fact table (rate columns deliberately omitted — they
behave badly under SI's default SUM aggregation):

```sql
ALTER TABLE schema.idm_branch_perf_v1
  ADD COLUMN "NET_COLLECTION_VALUE" numeric
    GENERATED ALWAYS AS (
      COALESCE("VAL_SUCCESS",0) - COALESCE("VAL_FAIL",0)
    ) STORED;

ALTER TABLE schema.idm_branch_perf_v1
  ADD COLUMN "NET_REVENUE_FROM_FEES" numeric
    GENERATED ALWAYS AS (
      COALESCE("FEE_SUCCESS",0) + COALESCE("FEE_FAIL",0)
      + COALESCE("FEE_DISP",0) + COALESCE("FEE_SUSP",0)
      + COALESCE("FEE_TRACK",0)
      - COALESCE("COST_SUCCESS",0) - COALESCE("COST_FAIL",0)
      - COALESCE("COST_DISP",0) - COALESCE("COST_SUSP",0)
      - COALESCE("COST_TRACK",0)
    ) STORED;
```

These two work cleanly because they aggregate correctly under `SUM`
(the SI default for NUMBER fields). A user asking "what's the total
net collection value" gets the right answer.

## What NOT to add (rates and ratios)

These look attractive but break SI:

```sql
-- DON'T DO THIS
ADD COLUMN "SUCCESS_RATE" numeric GENERATED ALWAYS AS (
  "NUM_SUCCESS"::numeric / NULLIF("NUM_SUCCESS"+"NUM_FAIL", 0)
) STORED;
```

The problem: SI's default aggregation for NUMBER columns is SUM. A
question like "what's the success rate?" runs `SUM(success_rate)`
across all rows, returning ~183 instead of the actual rate of 0.8358.

If you set `defaultMetric: AVG` on the column in the SI source, you
get the macro-average (average of per-row rates) which is also
wrong: 0.35 instead of 0.84 (the micro rate).

The honest answer is the micro rate
`SUM(NUM_SUCCESS) / SUM(NUM_SUCCESS + NUM_FAIL)`, which neither SUM
nor AVG of a per-row column computes correctly.

**Solution**: don't add the rate column. Add a tenant-wide rule that
tells the LLM to compute rates via the SUM-of-numerator over SUM-of-denominator formula:

```
When the user asks about success rate, failure rate, dispute rate,
or any other rate or percentage that is not a precomputed field, do
not return per-row averages. Instead, compute the overall (micro)
rate as SUM(numerator) / SUM(numerator + denominator).
```

In testing this rule worked: "what is the success rate?" returns
0.8358 correctly.

## Applying after the source already exists

If the source was built before the columns were added, you need to
rebuild the source so SI rediscovers the schema. SI has no "refresh
schema" endpoint.

```python
# 1. DELETE old source (capture its ID first)
# 2. POST new source with same name and entities
# 3. PUT joins + labels + metadata as before
# 4. Update any per-source rules with new source ID
# 5. Flush cache
```

See `simba-intelligence-setup/references/data-source-modelling.md`
for the API recipe.

## Verification

After rebuild and rule deployment, confirm in the Playground:

```
Q: What is the total Perf Net Collection Value?
expected: a single rand value, equal to SUM(VAL_SUCCESS - VAL_FAIL)
          from Postgres directly.

Q: What is the total Perf Net Revenue from Fees?
expected: a single value, equal to the sum-of-fees minus
          sum-of-costs.

Q: What is the success rate?
expected: 0.83-0.84 ish (depending on data), NOT a 3-digit
          integer like 183.
```

If the success-rate question returns 183 or 0.35, the rule isn't
firing. Re-check:

- Rule has `enabled: true`
- Rule content includes the formula (not just "use the precomputed
  field")
- Source cache flushed since rule was added
