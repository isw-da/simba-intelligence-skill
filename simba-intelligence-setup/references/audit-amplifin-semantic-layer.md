# Amplifin semantic layer methodology

The methodology that produced the Amplifin demo source for the
2026-05-19 hostile audit. Records every decision the layer makes
implicitly, so a senior engineer can reproduce it or fault it.

---

## 1. What is the semantic layer?

A definition file plus runtime configuration that:

- Maps physical Postgres columns to human-readable labels
- Disambiguates fields across sources via `fieldMetadata`
- Constrains the LLM agent's behaviour via `/api/v1/rules`
- Defines join structure for each business source

For Amplifin the layer comprises:

- Three SI data sources, one per fact table, each containing
  `branch` + `branch_legal_entity` + one `idm_*` fact
- 53 `fieldMetadata.description` entries across the three sources
- 13 tenant-wide rules + 3 per-source rules in Rules Management

---

## 2. Why it matters

100% extraction accuracy is wasted if the semantic layer is
incomplete. An exact Postgres value reachable by SQL produces a wrong
NLQ answer if the LLM:

- Picks the wrong source
- Synthesises a metric not in the data
- Applies an implicit time filter the user didn't ask for
- Hallucinates when the SQL returned empty

We verified all four happen on a layer with no `fieldMetadata` and no
rules. The same source with metadata + rules failed roughly half as
often.

---

## 3. Principles

### Defaults over ambiguity

| Ambiguity | Default | Rationale |
|---|---|---|
| "total X" with no time window | sum across all available data | rule: totals-default-to-all-time |
| Question with no sourceId clue | refuse, list named metrics | rule: scope-bare-questions-strictly |
| Metric not present in source | "I don't have that metric" | rule: no-invented-fields |
| Empty SQL result | "The query returned no rows" | rule: empty-result-is-empty |
| Date outside data window | "Data covers June 2025 to May 2026" | rule: amplifin-data-window |
| Null in grouping dimension | label as "(unknown)" | rule: show-grouping-fields |
| Numeric value without currency | rand prefix R | rule: amplifin-currency-is-rand |

### Entity resolution rules

| Source-A name | Source-B name | Match rule |
|---|---|---|
| `BRANCH_CD` in dim | `BRANCH_CD` in fact | inner-join equality, both cast to text |
| Branch in NLQ ("each branch") | `branch.BRANCH_CD` | label match on "Branch" or "Branches" |
| Region ("each region") | `branch.REGION` | label match on "Region" |
| Industry ("each industry") | `branch_legal_entity.INDUSTRY` | label match on "Industry"; nulls labelled "(unknown)" |
| Payment stream | `idm_fee_stats_v3.PMT_STREAM` | label match on "Payment Stream" |
| Finance code | `idm_monthly_due_v2.FIN_CD` | label match on "Finance Code" |

There is no fuzzy match. "Branch code" matches `BRANCH_CD`. "Region"
matches `REGION`. Anything outside the listed labels is rejected (or
should be).

### Date awareness

| User phrase | Resolves to |
|---|---|
| "current month" | 2026-05-01 to 2026-05-31 |
| "last month" | 2026-04-01 to 2026-04-30 |
| "this year" | 2026-01-01 to today (2026-05-19) |
| "last year" | not supported; data is only 12 months |
| "across all months" | 2025-06-01 to 2026-05-31 |
| "year over year" | not supported |
| Specific month (e.g. "May 2026") | first day of that month, exact match |

### Aggregation conventions

| Question pattern | Expected SQL shape | Example |
|---|---|---|
| "Total X" | `SUM(x) FROM fact` | Total Perf Successful Value |
| "Top N regions by X" | `SUM(x) GROUP BY region ORDER BY 2 DESC LIMIT N` | Top 5 regions by Perf Successful Value |
| "X by month" | `SUM(x) GROUP BY month_dt ORDER BY month_dt` | Perf Successful Value by month |
| "X for May 2026" | `SUM(x) WHERE month_dt = '2026-05-01'` | Perf Successful Value for May 2026 |
| "How many X" | `COUNT(*)` or `COUNT(DISTINCT x)` | How many branches |

Joins always use LEFT from `branch` (the hub) to facts. Fan-out
prevention is enforced by single-fact-per-source rather than join
choice. Distinct-count is implicit on dimension keys.

### Error handling

| Condition | Layer response |
|---|---|
| Unknown field | "I don't have that metric in this data source" |
| Synthesised derived metric (EBITDA, etc.) | "That metric is not defined in this data source" + list 3 available fields |
| Empty SQL result | "The query returned no rows for this question" |
| Date outside window | "Data covers June 2025 to May 2026" |
| Ambiguous bare wording | Ask user to specify metric; list options |

---

## 4. Repeatable process for scaling

For each new SI tenant or new fact table:

1. **Data quality first.** PK uniqueness on the dimension; ≥95% FK
   coverage from each fact; consistent join-key column type; null
   density audit; date range plausibility. See
   `best-practices-data-sources.md` step 5.
2. **One fact per source.** Compose with `branch` + any dim entities.
3. **Build via API.** POST source, GET back to read auto-generated
   field name suffixes, then PUT with joins + labels + `fieldMetadata`
   in one shot. See `data-source-modelling.md` for the recipe.
4. **Apply rules** at tenant level (hallucination prevention,
   synthesis prevention, currency, data window) and at source level
   (which fields belong to this source).
5. **Stress test** with the 25-question suite in
   `nlq-stress-testing.md`. Target ≥90% pass rate.
6. **Document** the labels, defaults, and rules in this file's format
   so the next person can audit it.

---

## 5. Storage and versioning

- Source definitions are stored in SI's Postgres metadata DB. Backed
  up via SI's standard backup process.
- Field metadata is stored alongside source definitions.
- Rules are stored in `/api/v1/rules`. They are NOT in source backups;
  back them up via `GET /api/v1/rules`.
- Versioning is implicit: each PUT increments the source's
  `lastModifiedDate` but the previous version is not retained.
- For change tracking: write rule and source definitions as code (the
  scripts under `/scripts/`) and commit them to git. SI is the
  applied state; git is the desired state.

---

## 6. When to graduate from system-prompt-as-tool

The Rules Management surface is system-prompt-as-tool: plain English,
no schema, applied per-request. It's the right tool for:

- Behavioural constraints ("never invent")
- Format directives ("currency is rand")
- Source-scoping ("only use Perf fields here")

Graduate to a structured definition file when:

- The rule set exceeds 20 entries (debugging becomes painful)
- Multiple rules conflict on the same question (precedence is
  undefined in plain English)
- Versioning becomes load-bearing (need rollback)
- More than one person is editing rules (need diff and review)

At that point, externalise the rules to YAML/JSON in git, generate
the rule POSTs from there, and treat SI's Rules Management as a
deployment target.

---

## Cross-references

- `audit-amplifin-nlq-test-suite.md` — the 25 test questions
- `audit-amplifin-qa-results.md` — the audit findings
- `data-source-modelling.md` — the API mechanics
- `best-practices-data-sources.md` — generic guidance
