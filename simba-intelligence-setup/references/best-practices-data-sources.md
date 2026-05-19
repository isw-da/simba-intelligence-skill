# SI data source and prompting best practices

How to set up a Simba Intelligence data source that holds up under
hostile testing, and how to phrase questions so the chat agent
behaves predictably. Field-tested on the Amplifin May 2026 build.

Companion to `data-source-modelling.md` (mechanics) and
`nlq-stress-testing.md` (verification methodology). This one is the
prescriptive guide for SEs who need a demo that doesn't break.

---

## Five-step setup that survives a hostile audit

### 1. One fact per source

Multi-fact stars produce fan-out on bare aggregates. Even with LEFT
joins to a clean dimension, summing a column across multiple connected
facts inflates by row-count multiplication.

Instead: one source per fact table. All sources share the same
dimension entities (`branch`, `branch_legal_entity`).

```
Source A: branch + branch_legal_entity + idm_branch_perf_v1
Source B: branch + branch_legal_entity + idm_monthly_due_v2
Source C: branch + branch_legal_entity + idm_fee_stats_v3
```

Costs nothing extra in storage. Pays off every time someone asks "what
is the total X".

### 2. Prefix fact-table labels with a source-unique tag

The chat agent picks sources by matching labels to question text.
Bare labels collide across sources. Prefix every fact-table field.

```
VAL_SUCCESS → "Perf Successful Value"   (not "Successful Value")
AMT_DUE     → "Due Amount Due"
TRN_AMT     → "Fee Transaction Amount"
```

This is the single biggest improvement to NLQ disambiguation. Without
it, "what's the transaction amount" reaches across sources and picks
whichever field matches first.

### 3. Populate `fieldMetadata` declaratively

The `fieldMetadata` property on each native field is the per-field
context the LLM reads. Use it. Keep it declarative.

Good:
```json
"fieldMetadata": {
  "description": "Rand value of successful debit-order collections at this branch"
}
```

Bad (steers the LLM into specific query plans):
```json
"fieldMetadata": {
  "description": "Summed by branch per month, grouped by payment stream"
}
```

The UI says "up to 5 properties for optimal performance". One
`description` is enough for almost every field. Add `source` or
`unit` only if a field's label would otherwise be ambiguous.

### 4. Apply tenant-wide and per-source rules

The Rules Management surface (`/api/v1/rules`) accepts plain-English
rules the chat agent honours. Put hallucination prevention and
scoping here. Examples that work:

| Rule name | Content |
|---|---|
| no-invented-fields | "If the user asks about a metric that does not exist in any field of the currently selected source, respond exactly 'I don't have that metric in this data source'. Do not invent, estimate, or substitute." |
| no-synthesised-metrics | "Do not compose business metrics like EBITDA, Customer Lifetime Value, Net Profit Margin from existing fields. If the named metric is not a single field, respond 'That metric is not defined in this data source' and list 3 fields that are available." |
| empty-result-is-empty | "When the SQL returns zero rows, respond 'The query returned no rows for this question'. Do not fabricate." |
| scope-bare-questions-strictly | "If the user asks bare wording like 'what's the total amount', respond by listing the named metrics the user could ask about, rather than picking one." |
| currency-is-rand | "All monetary values in this tenant are South African Rand. Prefix with R, never $." |
| show-grouping-fields | "When grouping by a dimension, always include null values labelled '(unknown)' rather than dropping them." |
| data-window | "Data covers June 2025 to May 2026. Questions outside this range should return 'Data covers June 2025 to May 2026'." |

Apply rules POST `/api/v1/rules` with `{name, content, enabled,
is_tenant_wide, data_source_id}`. Per-source rules scope only to that
source.

### 5. Clean the underlying data before testing NLQ

Most "AI got the wrong number" bugs are actually data quality bugs.
Run these checks against Postgres before letting NLQ see the data:

- Primary key uniqueness on the dimension. Duplicates inflate joins.
- Foreign key coverage. If only 47 of 683 fact branches match the
  dimension, your joins return 47 rows of useful data.
- Column-type consistency on join keys. text vs bigint breaks the SI
  join validator.
- Null density. A field with 998 of 1000 nulls is going to behave
  badly under aggregation. Either backfill or set the field to hidden.
- Date range plausibility. Future dates (2074, 2271) and ancient
  dates both confuse the planner.

---

## How to ask questions that work

The chat agent is sensitive to phrasing. These patterns are reliable.

### Prefix-led phrasings (preferred)

```
Total Perf Successful Value across all months
Top 5 regions by Perf Successful Value
Total Due Amount Due per finance code
Fee Transaction Fee by month
```

### Original column names also work

If a labelled field starts misbehaving, try the underlying column:

```
What is the total VAL_SUCCESS?
Sum of TRN_FEE
```

The SI agent treats these as valid field references.

### Avoid

- Bare wording without a prefix: "what's the total amount" → leaks to
  whichever source has a matching label first.
- Grain-bearing phrasing in metric names: "sum-grouped-by-stream" →
  forces a grouped query when you wanted a total.
- Asking for derived metrics by name: "EBITDA", "Net Profit Margin",
  "Customer Lifetime Value" → either rejected (with no-synthesised
  rule active) or fabricated (without).

### When in doubt, retry

The chat agent is non-deterministic. A question that returns "not
available" on one try often returns the correct answer on the second.
For demos, dry-run each question three times before relying on it.

---

## Eight patterns for demo prep

### A. The opener: row count

Start with a row count from the dimension. It's the simplest test of
"is this thing connected".

```
How many branches are there?
```

### B. The headline aggregate

One bare total per source, prefix-led.

```
Total Perf Successful Value across all months
Total Due Amount Due across all months
Total Fee Transaction Fee across all months
```

### C. The dimensional breakdown

The first "wow" moment. Pick a high-cardinality dimension with clean
data.

```
Top 5 regions by Perf Successful Value
Total Due Amount Due per finance code
Fee Transaction Fee by payment stream
```

### D. The time series

Demonstrates trend. Force a specific year so the time filter behaves.

```
Perf Successful Value by month
Show the monthly Due Amount Due for the last 12 months
```

### E. The drill-in

Verify the audience that the numbers are real. Pick a specific value
that you've cross-checked against the database.

```
What was the Perf Successful Value for May 2026?
[expected: 400,958,439 — pre-verified]
```

### F. The defensible question

Ask something that requires understanding entity relationships.

```
What is the total Perf Successful Value per industry?
```

### G. The boundary check

Show the system declining to answer when the data doesn't support
the question.

```
How many branches are there in California?
[expected: 0]

What was the Perf Successful Value in February 2024?
[expected: out of range]
```

### H. The recovery

If a question misfires mid-demo, recover with the column name.

```
"Total transaction amount" → leaks to FRC
recover with: "Sum the TRN_AMT field"
```

---

## Three things never to do in a demo

1. **Ask a bare-aggregate question without prefix.** "What's the
   total amount" will pick the largest amount-like field across all
   sources, often the wrong one.

2. **Ask for a derived metric by name.** "Show me churn rate" or
   "what's the gross margin" either fabricates a number or returns a
   composition you haven't validated.

3. **Trust a number without seeing the underlying query.** Click the
   `{ }` icon next to every chat answer. If `Response` is `[]` and
   the chat text says "the total is X", you have an invented number.

---

## When SI's behaviour can't be fixed by configuration

These are SI product limitations as of this build. Document them, file
them with product, work around them in demos.

| Limitation | Workaround |
|---|---|
| `sourceId` parameter ignored by the chat agent | Prefix labels and use rules to constrain |
| Chat agent picks sources autonomously based on field-name matches | Make labels source-unique |
| Same question can return different answers on repeated tries | Retry on misfire; pre-verify demo questions |
| Bare-aggregate questions cross sources | Train demo audience to lead with the source word |
| 250-row limit on result sets (trial) | Aggregate, don't list |
| LLM fabricates definitions for unknown business metrics | Apply the no-synthesised-metrics rule |

---

## Setup checklist

Before showing anyone a source, verify:

- [ ] Each entity participates in at least one join (saves UI from
      white-screening)
- [ ] Join column types match (ATTRIBUTE = ATTRIBUTE)
- [ ] Dimension PK is unique (no inflation from duplicates)
- [ ] Each fact's `BRANCH_CD` (or equivalent join key) overlaps with
      the dimension's by at least 95%
- [ ] Each visible field has a `fieldMetadata.description`
- [ ] Each fact-table metric has a source-unique label prefix
- [ ] `global-settings.timebar.enabled = false` (UI noise)
- [ ] Cache flushed after any data change
- [ ] Tenant-wide rules applied: hallucination, synthesis, scoping,
      currency, data window
- [ ] Per-source rules applied: which-fields-only
- [ ] At least 10 NLQ questions dry-run three times each (see
      `nlq-stress-testing.md`)
- [ ] One adversarial test passes (unknown field returns "no
      such field", not a number)

If any box is unchecked, the source isn't demo-ready.

---

## Cross-references

- `data-source-modelling.md` — the underlying mechanics
- `nlq-stress-testing.md` — the 25-test methodology with scoring
- `troubleshooting.md` — cluster-level issues
