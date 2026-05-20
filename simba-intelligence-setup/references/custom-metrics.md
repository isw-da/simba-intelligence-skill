# Custom Metrics

The SI Discovery API supports per-source custom metrics — calculated
fields defined by a SQL-like expression that the LLM can pick
directly when answering questions. This is the proper "derived
field" surface; my earlier attempts to define derived fields via
`nativeFields[].origin.type=DERIVED` on the source PUT path were
using the wrong endpoint and that path is server-side broken.

The correct endpoint is per-source:

```
POST /discovery/api/sources/{sourceId}/custom-metrics
```

---

## Shape

```json
{
  "name": "success_rate",
  "label": "Success Rate",
  "visible": true,
  "expression": "sum(num_success) / (sum(num_success) + sum(num_fail))",
  "dataType": "NUMBER",
  "numberFormat": {
    "type": "PLAIN",
    "decimals": 2,
    "separator": true,
    "negative": "SIGNED",
    "standardUnit": "NONE"
  }
}
```

`numberFormat` is set automatically if you omit it. The minimal
required fields are `name`, `label`, `expression`, `dataType`.

Response is 201 Created with the full metric body. The metric is
immediately visible to NLQ.

---

## Expression syntax

Supports basic SQL aggregations and arithmetic:

| Pattern | Works |
|---|---|
| `sum(field)`, `count(field)`, `avg(field)`, `min(field)`, `max(field)` | yes |
| `field_a / field_b`, `field_a + field_b` | yes |
| `case when ... then ... else ... end` | yes |
| `nullif(x, 0)` | **no** — use `case when x = 0 then 1 else x end` |
| References to fields from any entity in the source | yes (the field name disambiguates) |
| Comments | no |

The validator returns a useful error if your expression references
non-existent fields, e.g.:

```
"Failed to validate expression: ... Field num_disp doesn't exist in
the data source."
```

So make sure your expression uses field names that actually exist in
one of the source's entities. Fields appear as their `name`
attribute (lowercased, suffixed with `_1`, `_2` etc. for duplicates).

---

## Crucial: which entity's fields to reference

If your source uses the two-entity pattern (per-month and all-time,
see `data-source-modelling.md`), the LLM auto-time-filter behaviour
depends on which entity supplies the metric's fields.

**Reference all-time entity fields (`total_*`) for ratios and
overall statistics.** The all-time entity has no date column, so the
metric isn't auto-filtered. Bare aggregate questions hit the full
data:

```json
{"expression": "sum(total_num_success) / (sum(total_num_success) + sum(total_num_fail))"}
```

This gave us 0.8358 on the first try, exact to Postgres truth.

**Reference per-month entity fields (`num_success` etc.) only when
you specifically want recent-period defaults.** The LLM applies the
time filter to those references, restricting the calculation to the
last 2 months.

---

## Recipe for the demo metrics we use

For the debit-order payments use case, six metrics cover the
business questions that previously had to be synthesised by the LLM
(and were therefore unreliable). All reference all-time fields:

```python
CUSTOM_METRICS = [
    {"name":"success_rate","label":"Success Rate",
     "expression":"sum(total_num_success) / (sum(total_num_success) + sum(total_num_fail))",
     "dataType":"NUMBER"},
    {"name":"failure_rate","label":"Failure Rate",
     "expression":"sum(total_num_fail) / (sum(total_num_success) + sum(total_num_fail))",
     "dataType":"NUMBER"},
    {"name":"cost_to_value_ratio_failure","label":"Cost to Value Ratio on Failure",
     "expression":"sum(total_cost_fail) / (case when sum(total_val_fail) = 0 then 1 else sum(total_val_fail) end)",
     "dataType":"NUMBER"},
    {"name":"cost_to_value_ratio_success","label":"Cost to Value Ratio on Success",
     "expression":"sum(total_cost_success) / (case when sum(total_val_success) = 0 then 1 else sum(total_val_success) end)",
     "dataType":"NUMBER"},
    {"name":"average_collection_value","label":"Average Successful Collection Value",
     "expression":"sum(total_val_success) / (case when sum(total_num_success) = 0 then 1 else sum(total_num_success) end)",
     "dataType":"NUMBER"},
    {"name":"total_collection_attempts","label":"Total Collection Attempts",
     "expression":"sum(total_num_success) + sum(total_num_fail)",
     "dataType":"NUMBER"},
]
```

Test results against the the customer demo data:

| Question | Truth | NLQ answer | Match |
|---|---|---|---|
| What is the success rate? | 0.8358 | 0.8358 | ✅ exact |
| What is the failure rate? | 0.1642 | 0.1642 | ✅ exact |
| What is the total collection attempts? | 108,308 | 108,308 | ✅ exact |
| Cost to value ratio on failure | 0.003217 | network ERR on first try | ⚠️ retry |
| Cost to value ratio on success | 0.005993 | network ERR on first try | ⚠️ retry |

---

## Other endpoints worth knowing

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/discovery/api/sources/{sid}/custom-metrics` | List all metrics on this source |
| `POST` | `/discovery/api/sources/{sid}/custom-metrics` | Create a metric |
| `DELETE` | `/discovery/api/sources/{sid}/custom-metrics/{name}` | Remove a metric |
| `PUT` | `/discovery/api/sources/{sid}/custom-metrics/{name}` | Update (we haven't verified this works yet; safer to DELETE and re-POST) |

---

## Why this replaces "derived fields"

What the customer's data team would otherwise add as a generated
column (e.g. `success_rate` as `NUM_SUCCESS / (NUM_SUCCESS +
NUM_FAIL)`), you can now define inside the SI source as a custom
metric. The customer's data is never touched. The expression runs at
query time against the entity's data.

This unlocks all the "derived metric" use cases:

- Business ratios (success, failure, dispute, conversion rate)
- Net values (revenue minus costs, value minus failures)
- Per-unit averages (cost per attempt, value per success)
- Totals across logical sub-groups

Importantly, it gives the LLM something to **pick** when asked about
"the success rate" — rather than synthesise the formula on the fly
(which is what the no-synthesised-metrics rule otherwise forces it
to refuse to do). The metric is a real, named field; the LLM uses it.

---

## Cross-references

- `data-source-modelling.md` — the underlying source structure
- `platform-only-modelling.md` — the customer-tenant deployment path
- `use-cases/debit-order-payments/sql-templates.py` — the metrics
  applied to the debit-order use case
- `audit-the customer-bugs.md` — earlier entries on broken
  `nativeFields.origin.type=DERIVED` are now superseded by this doc
