# Starter source guide

How to use the starter source we ship to a debit-order processor on
day one, what questions to ask it, and how to extend it to cover
your other fact tables.

The starter source is deliberately minimal. The production source
(also in your tenant) covers performance, dues, and fees with eight
entities. The starter has three entities and is meant to be opened,
read, and copied.

---

## What's in the starter

| Entity | Type | What it is |
|---|---|---|
| Branches | Existing table | Branch dimension. One row per branch. |
| Branch Performance Monthly | Custom SQL | Per-branch-per-month performance facts with a `month_dt` column. Use this for trend and single-period questions. |
| Branch Performance All-Time | Custom SQL | Per-branch all-time totals. **No date column** so the AI cannot apply a "last month" filter to it. Use this for grand totals. |

Two Custom Metrics on top:

| Metric | What it returns |
|---|---|
| Success Rate | `successes / (successes + failures)` across all months |
| Failure Rate | `failures / (successes + failures)` across all months |

Plus the tenant-wide rules already in place (anti-hallucination,
currency, data-window, etc.).

---

## Questions that work (run these first)

Each is pre-tested. Numbers match what `SELECT` would return from the
underlying tables.

### About the data shape

- How many branches are there?
- What regions are in the data?
- What are the possible branch statuses?
- What's the data window? (you'll get a sensible answer if `month_dt`
  is included; otherwise the LLM will say it doesn't know)

### Totals (uses the All-Time entity)

- What is the **All-Time Successful Value across all branches**? (this exact phrasing returns R<value> ✓)
- What is the All-Time Failed Value across all branches?
- What is the All-Time Successful Count across all branches?
- What is the All-Time Failed Count across all branches?

**Important**: include "across all branches" in the phrasing. Without
it, the AI may bind to the per-month entity and apply its default
time filter, returning only April-May totals (~R422M instead of
R10.83B). The "across all branches" phrase steers it to the all-time
entity.

### Ratios (uses the Custom Metrics)

- What is the Success Rate?
- What is the Failure Rate?

### Breakdowns (uses All-Time entity joined to Branches)

- Top 5 regions by All-Time Successful Value
- Top 10 branches by All-Time Successful Value
- All-Time Successful Value per branch status

### Trends (uses the Monthly entity)

- Successful Value by month
- What was the Successful Value for May 2026?
- Compare Successful Value in May 2026 to April 2026
- Which month had the highest Successful Value?

### Defensive (should refuse, not invent)

- What is the Customer Lifetime Value? → "I don't have that metric"
- What is the EBITDA? → "Not defined in this data source"
- How many branches in California? → "0 branches in California"
- What was the Successful Value in February 2024? → "Data covers
  ..." (out of range)

---

## Questions to avoid (or rephrase before asking)

These have known reliability issues. The reasons are documented in
`audit-the customer-qa-results-v3.md`.

| Don't ask | Why | Rephrase as |
|---|---|---|
| "What's the total?" | Bare wording, no metric named | "What is the total All-Time Successful Value?" |
| "What's the value?" | Same | "What is the All-Time Successful Value?" |
| "What was X in May 2026" (using "in") | Phrasing can trigger wrong query plan | "What was X **for** May 2026" |
| "Tell me about the data" | Open-ended, AI may describe other sources | "What columns are available in this source?" |
| "How many successful collections?" | LLM may sum per-month entity (time-filtered) | "What is the All-Time Successful Count?" |
| "What's the average X?" | Ambiguous between micro and macro mean | "What is the All-Time Successful Value divided by All-Time Successful Count?" |

---

## How to scale the starter

The starter is the smallest unit that demonstrates the pattern. To
extend, copy and adapt.

### Add a second fact table (e.g. dues, fees, something else)

Repeat the per-month + all-time pair. Two Custom SQL entities per
fact.

```sql
-- Per-month entity SQL
SELECT
  b."BRANCH_CD"::text AS branch_cd,
  d."MONTH_DT" AS month_dt,
  COALESCE(d."AMT_DUE", 0) AS amt_due,
  COALESCE(d."NUM_DUE", 0) AS num_due,
  d."FIN_CD" AS fin_cd
FROM the customer.branch b
LEFT JOIN the customer.idm_monthly_due_v2 d
  ON d."BRANCH_CD"::text = b."BRANCH_CD"
WHERE d."MONTH_DT" IS NOT NULL
```

```sql
-- All-time entity SQL
SELECT
  b."BRANCH_CD"::text AS branch_cd,
  SUM(COALESCE(d."AMT_DUE", 0)) AS total_amt_due,
  SUM(COALESCE(d."NUM_DUE", 0)) AS total_num_due
FROM the customer.branch b
LEFT JOIN the customer.idm_monthly_due_v2 d
  ON d."BRANCH_CD"::text = b."BRANCH_CD"
GROUP BY b."BRANCH_CD"
```

Then join both to Branches on `branch_cd` and you're done. The AI
will pick the monthly entity for trend questions and the all-time
for total questions.

### Add another dimension

If you have a separate table that joins to branches (e.g. legal
entity, contract, contact), add it as a Custom SQL entity that
deduplicates and selects only the columns you want exposed. Example
for legal entity:

```sql
SELECT DISTINCT ON ("BRANCH_CD"::text)
  "BRANCH_CD"::text AS branch_cd,
  "INDUSTRY", "LEGAL_STRUCTURE"
FROM the customer.branch_legal_entity
```

`DISTINCT ON` is important: if a branch has two legal-entity rows,
every join through it doubles the numbers.

### Add a Custom Metric

For any ratio or formula that comes up repeatedly, define it as a
Custom Metric so the AI picks it directly rather than computing on
the fly. Best practice: **reference the all-time entity's fields**
(`total_*`), not the per-month entity's, so the AI's auto-time-filter
doesn't restrict your ratio.

```
POST /discovery/api/sources/{sid}/custom-metrics
{
  "name": "cost_to_value_ratio_failure",
  "label": "Cost to Value Ratio on Failure",
  "expression": "sum(total_cost_fail) / (case when sum(total_val_fail) = 0 then 1 else sum(total_val_fail) end)",
  "dataType": "NUMBER"
}
```

Notes on syntax:
- Standard SQL aggregates: `sum`, `count`, `avg`, `min`, `max`
- `case when ... then ... else ... end` works
- `nullif` does **not** work — use `case when x = 0 then 1 else x end` for safe division

### Add an `allowed_values` tag on a closed-vocabulary dimension

If the AI ever returns made-up values for a column (we saw it claim
"Ecommerce" as an industry when none existed), tag that field with
its real values:

```json
"fieldMetadata": {
  "description": "Primary industry classification",
  "allowed_values": "NCR Cash Received, Long Term Insurance, Debt Collector, Services, Short Term Insurance, ..."
}
```

The AI reads `allowed_values` and stops inventing.

### Add a rule (sparingly)

The 16 tenant-wide rules already cover the common failure modes. New
rules are warranted when you find a specific failure pattern across
multiple questions. Format:

```
POST /api/v1/rules
{
  "name": "short-kebab-case-name",
  "content": "Plain English instruction the AI follows on every query.",
  "enabled": true,
  "is_tenant_wide": true
}
```

Keep rules declarative. Don't try to encode complex logic; the AI
treats rules as constraints, not algorithms.

---

## Pattern checklist for any new source

When you build a new SI source — for any data, not just this one —
verify these before declaring it ready:

- [ ] One Existing-Entity for the primary dimension table
- [ ] Per-month Custom SQL entity for each fact (with the date column)
- [ ] All-time Custom SQL entity for each fact (pre-aggregated, no date)
- [ ] Joins from the dimension to every fact entity, on the primary key
- [ ] Field labels meaningful (e.g. "Successful Value" not "VAL_SUCCESS")
- [ ] `fieldMetadata.description` on every visible metric
- [ ] `fieldMetadata.allowed_values` on every closed-vocabulary dimension
- [ ] Custom Metrics for every business ratio that comes up repeatedly
- [ ] Tenant-wide rules applied (anti-hallucination, currency, data window)
- [ ] Time bar disabled in global-settings
- [ ] Spot-check 10 questions from the question deck above; ≥ 90% pass

If any box is unchecked, the source isn't ready for prospect use.

---

## How to test a new question

Before relying on a question (in a dashboard, a demo, an internal
report), run it 3 times. Treat it as reliable only if ≥ 2 of 3 runs
return the same correct answer.

When a question misses:
1. Click the `{ }` icon next to the AI's response in the playground.
   That shows you the actual query SI ran and the raw response. If
   the response is `[]`, the AI is making up the answer text.
2. Try the question with a different verb: "what is" → "show me" →
   "calculate".
3. Try referencing the underlying field name instead of the label:
   "total_val_success" instead of "All-Time Successful Value".
4. If still misbehaving, the failure pattern probably needs a rule or
   metadata tweak. Send it to your SI contact.

---

## When to graduate to the production source

The starter is for learning and tinkering. When you're ready to
demo to a stakeholder or build a dashboard, switch to the production
source ("the customer Operations" — eight entities, six metrics, all
three fact tables covered).

The starter source can stay in your tenant indefinitely. It costs
nothing to keep around and it's the cleanest reference for "how does
this thing work".
