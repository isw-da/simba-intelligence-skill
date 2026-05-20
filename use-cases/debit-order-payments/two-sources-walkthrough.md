# Two sources: build steps, test questions, and why each answer holds up

Two data sources ship with this use case. The simple one teaches the
pattern and answers basic questions accurately. The hardened one is
the production-grade source that survives hostile testing.

Live demo source IDs (VDD tenant, 2026-05-20):
- Simple: `6a0d6b87ed27777725d949f5`
- Hardened: `6a0c5d85ed27777725d949a0`

A note that applies to both: SI's natural-language layer is
phrasing-sensitive. The source design below removes whole *classes*
of error (time-filter bias, metric synthesis, dimension
hallucination, join fan-out). What it cannot remove is the LLM's
own variability between phrasings of the same question. So each test
question below uses a phrasing we have verified returns the right
answer. If a question misfires, click the `{ }` icon in the
Playground to see the raw query, and try the alternate phrasing
noted.

---

## Source 1: the simple source

### What it is

Two entities:
1. **Branches** — the branch dimension, straight from the table.
2. **Branch Performance (All-Time)** — a Custom SQL entity that joins
   branches to the performance fact and sums each branch's figures
   across all months. One row per branch. No date column.

Two Custom Metrics: **Success Rate**, **Failure Rate**.

It deliberately has no monthly entity, so it cannot answer "by month"
trends. That is the first limitation the user will hit, and the first
thing they learn to add (see Source 2).

### How to build it (replication steps)

1. Connections page, confirm the connection to the warehouse exists.
2. Data Sources, Create Source.
3. Drag the **branch** table onto the canvas. That's entity one.
4. Add SQL Entity. Paste this, which pre-aggregates the fact per
   branch:

   ```sql
   SELECT
     b."BRANCH_CD"::text AS branch_cd,
     b."REGION" AS region,
     b."STATUS" AS status,
     SUM(COALESCE(p."NUM_SUCCESS",0)) AS num_success,
     SUM(COALESCE(p."NUM_FAIL",0))    AS num_fail,
     SUM(COALESCE(p."VAL_SUCCESS",0)) AS successful_value,
     SUM(COALESCE(p."VAL_FAIL",0))    AS failed_value
   FROM amplifin_demo.branch b
   LEFT JOIN amplifin_demo.idm_branch_perf_v1 p
     ON p."BRANCH_CD"::text = b."BRANCH_CD"
   GROUP BY b."BRANCH_CD", b."REGION", b."STATUS"
   ```

5. Draw a join from Branches to the SQL entity on Branch Code.
6. Rename the fields to friendly labels (Successful Value, Failed
   Value, etc). Add a one-line description to each via Field Metadata.
7. Global Settings, turn the time bar off.
8. Add two Custom Metrics:
   - Success Rate: `sum(num_success) / (sum(num_success) + sum(num_fail))`
   - Failure Rate: `sum(num_fail) / (sum(num_success) + sum(num_fail))`
9. Save.

### Test questions and why each is accurate

| Question | Answer | Why it holds up |
|---|---|---|
| How many branches are there? | 1000 | Plain count against a clean dimension entity. No join, no aggregation, nothing to get wrong. |
| Top 5 regions by Total Successful Value | Free State 5.7B, ECape 1.4B, WCape 779M, Mpumalanga 337M, KZN West 254M | The all-time entity already summed each branch's value, so grouping by region is a simple second sum. Pre-aggregating in the Custom SQL removes any join fan-out. |
| What is the Success Rate? | 0.8358 | It's a Custom Metric with an explicit formula. The AI picks the named metric instead of trying to invent a success-rate calculation, so the denominator is always right. |
| What is the Failure Rate? | 0.1642 | Same: a defined metric, not a synthesised one. |
| What is the sum of the Total Successful Value field? | 10,833,290,438 | Phrase grand totals as "sum of the X field". Because the entity has no date column, the AI cannot apply its default last-month filter, so the sum covers all data. |

**Phrasing note for the simple source**: "what is the total
successful value" sometimes returns "not available" (an LLM
query-construction quirk on bare grand totals). "What is the sum of
the Total Successful Value field" reliably returns the full figure.
For totals broken down by a dimension (per region, per status), the
plain phrasing works fine.

### What it cannot do (by design)

- Monthly trends ("successful value by month") — there's no monthly
  entity. This is the cue to extend it (Source 2 shows how).
- Dues and fees — only performance is modelled. Same extension
  pattern applies.

---

## Source 2: the hardened source

### What it is

Eight entities:
- **Branches** dimension
- **Legal Entities** — Custom SQL that de-duplicates the legal table
  (one row per branch)
- **Branch Performance Monthly / All-Time** — per-month and
  pre-aggregated
- **Monthly Dues Monthly / All-Time**
- **Fee Statistics Monthly / All-Time**

Six Custom Metrics (success rate, failure rate, cost ratios, total
attempts). Sixteen tenant-wide Rules. `allowed_values` metadata on
every closed-vocabulary dimension.

### How to build it (replication steps)

Don't build it by hand. It's built and maintained by script:

```bash
cd use-cases/debit-order-payments

# Build the eight-entity source + six metrics
python3 sql-templates.py build \
  --base https://<tenant> --key <api-key> \
  --connection <connection-id> --schema <schema>

# Apply the 16 tenant-wide rules (idempotent)
python3 apply-rules.py --base https://<tenant> --key <api-key>
```

The build script holds the SQL for all eight entities, the join
wiring, the labels, the metadata, and the metric definitions. To
adapt to a different customer's table names, edit the SQL constants
at the top of `sql-templates.py`.

### Test questions and why each is accurate

| Question | Answer | Why it holds up |
|---|---|---|
| How many branches are there? | 1000 | Clean dimension count. |
| What is the total val_success across all branches? | 10,833,290,438 | The all-time entity has no date column, so the auto-time-filter can't restrict it. "Across all branches" steers the AI to that entity rather than the monthly one. |
| Total amt_due across all branches | 20,979,420,601 | Same all-time pattern, dues fact. |
| Total trn_fee across all branches | 349,932 | Same all-time pattern, fee fact. |
| Top 5 regions by total_val_success | Free State 5.7B etc. | Pre-aggregated all-time entity joined to the branch dimension. No fan-out because each branch appears once. |
| Total amt_due by finance code | CAPITEC_SO 17.4B, CAPITEC_TPPP 3.5B | Finance code is a real field on the dues entity; the breakdown is a clean group-by. |
| What is the Perf Success Rate? | 0.8358 | Custom Metric referencing the all-time totals, so the rate is the volume-weighted micro rate, not a per-row average. |
| What is the EBITDA? | "Not defined in this data source" | The no-synthesised-metrics rule plus the explicit-refuse rule stop the AI building EBITDA out of cost and value fields. It declines instead of inventing. |
| What is the total Customer Lifetime Value? | "Not defined in this data source" | Same refusal rules. We removed the average-value metric that the AI was previously mapping CLV onto, so there's nothing for it to grab. |
| List all industries in the data | Real values (Debt Collector, NCR Cash Received, Long Term Insurance, etc.) | The industry field carries an `allowed_values` metadata tag listing the real distinct values, plus a no-dimension-hallucination rule. *Caveat: this one is not 100% stable. On roughly one run in three the AI still lists generic industries (Ecommerce, SaaS). Verify with the `{ }` panel before quoting it.* |

### Why the hardened source survives more

The simple source answers basic questions. The hardened source adds
the layers that defend against bad input:

1. **Two entities per fact (monthly + all-time)**: totals come from
   the dateless entity (no time-filter bias), trends from the dated
   entity. The AI picks the right one by question shape.
2. **De-duplicated dimensions** (the Custom SQL `DISTINCT ON` on the
   legal table): a branch with two legal rows would otherwise double
   its numbers in any join through it.
3. **Custom Metrics** for every business ratio: the AI binds to a
   named metric rather than synthesising a formula it might get
   wrong.
4. **Rules** that force refusals: unknown fields, synthesised
   metrics, bare wording, out-of-range dates, currency formatting,
   null-grouping all handled by plain-English rules the engine obeys.
5. **`allowed_values` metadata** on closed dimensions: cuts the
   dimension-value hallucination (mostly; see the industry caveat).

---

## The honest summary to give the customer

Both sources answer the bread-and-butter questions accurately:
counts, totals, top-N rankings, rates, and breakdowns by region,
status, finance code, or payment stream. Numbers match the database
to the rand.

What still needs care:
- Phrasing matters. Lead with the metric name; for a grand total,
  "sum of the X field" is the most reliable form.
- Dimension-value listing ("what industries exist") is mostly fixed
  but not bulletproof; verify before quoting.
- The playground is the floor. In production, wired into Claude, the
  retry-and-reconsider loop pushes accuracy materially higher. The
  playground is for stress-testing the semantic layer, not the final
  experience.

The two sources together let the customer see both ends: how quickly
a simple source gets to a useful answer, and how much a hardened
source defends against the questions designed to break it.
