# Data source modelling and known issues

Field-tested learnings from building Amplifin's demo source (May 2026). Covers
the SI Discovery API for sources, semantic-layer behaviour, join validation,
chat-agent quirks, and how to recover when things go wrong. Companion to
`troubleshooting.md` which covers cluster-level issues; this one covers the
**source modelling and NLQ correctness** layer specifically.

The Discovery API is fully usable, but it does not enforce some constraints
the UI does, so an API-built source can validate at POST time and still
crash the editor or produce wrong NLQ answers. The path of least surprise is
to know what the UI implicitly requires and replicate it.

---

## Build path overview

Sources can be built three ways:

| Path | Pros | Cons |
|---|---|---|
| UI canvas (drag and drop) | Validates entity completeness, joins, time fields | Slow, no scripting |
| Data Source Agent | LLM-driven schema discovery and label generation | Heavy compute, opaque heuristics |
| Discovery API (`POST /discovery/api/sources`) | Scriptable, fast, supports bulk relabel | UI validation rules apply only on UI save, not API PUT |

For demo work where you need precise control over labels and joins, the
API is best, but you must reproduce the UI's invariants manually.

---

## The five things the UI enforces that the API does not

These are the most common ways an API-built source ends up broken.

### 1. Every entity must participate in at least one join

The UI refuses to save a source where any entity is unconnected. The
API accepts `storage.joins: []` with multiple entities, but loading
that source in the editor then crashes with
`Cannot read properties of undefined (reading 'id')` and the canvas
white-screens.

**Fix**: ensure `storage.joins` contains at least one join per entity
beyond the hub. For a star schema, every spoke joins to the hub on a
shared key.

### 2. Field name suffixing for duplicate columns

When the same column name appears in multiple entities (e.g. `BRANCH_CD`
in `branch`, `branch_legal_entity`, `idm_branch_perf_v1`), SI auto-suffixes
the later ones: `branch_cd`, `branch_cd_1`, `branch_cd_2`, etc. The suffix
order follows the order entities are listed in the POST payload.

**Fix**: after POST, GET the source and read the actual `fieldName` per
entity before constructing joins. Do not assume the names.

```python
src = get(f"/discovery/api/sources/{SID}")
for e in src['storage']['dataEntities']:
    for f in e['nativeFields']:
        if f['origin']['nativeOrigin']['originalName'] == 'BRANCH_CD':
            print(e['id'], f['fieldName'])
```

### 3. Join column type compatibility

A join condition where the two columns have different `dataType` values
(e.g. `ATTRIBUTE` on one side, `NUMBER` on the other) is rejected at PUT
time with HTTP 400:

```
"Source X has invalid join configuration"
```

The cause is usually a Postgres column type mismatch (one table has
`BRANCH_CD bigint`, another has it as `text`). SI infers
`NUMBER` from `bigint` and `ATTRIBUTE` from `text`.

**Fix**: cast the underlying column. Don't patch the source's `dataType`
field directly — that triggers a different validation error:

```
"Changing field data type is forbidden while field is used"
```

Working pattern:

```sql
ALTER TABLE schema.fact_table
  ALTER COLUMN "BRANCH_CD" TYPE text USING "BRANCH_CD"::text;
```

then rebuild the source so SI re-discovers the column as ATTRIBUTE.

### 4. `description` is not a writable property — but `fieldMetadata` is

Both entity-level (`dataEntities[i].description`) and field-level
(`dataEntities[i].nativeFields[j].description`) are rejected at PUT:

```
"Unrecognized field storage.dataEntities.null.description"
"Unrecognized field storage.dataEntities.null.nativeFields.null.description"
```

However, the API does accept a separate `fieldMetadata` property on
each native field. This is the "Field Metadata (new)" surface exposed
in the UI as "up to 5 properties for optimal performance". Shape is a
flat object of string keys to string values:

```json
{
  "name": "trn_amt",
  "label": "Fee Transaction Amount",
  "fieldMetadata": {
    "description": "Rand value of fee-bearing transactions at this branch",
    "source": "Amplifin Fee Statistics"
  }
}
```

The LLM reads `fieldMetadata` when answering questions about that
field. Empirically: it improves unknown-field handling (the LLM
refuses to invent values for a field that doesn't exist), and helps
disambiguate fields with similar labels across sources. It does
**not** prevent the chat agent from picking a different source
entirely when the question contains no source-scoping clue.

**Practical guidance**:
- Keep metadata declarative. "Rand value of successful collections" is
  better than "summed by branch per month" because the latter steers
  the LLM into a specific query shape.
- One property is enough for most demos: `description`. The UI hint of
  "5 for optimal performance" is upper bound, not target.
- Avoid metadata that constrains grain ("per branch per month",
  "grouped by stream"). It causes phrasing-sensitive regressions:
  bare aggregate questions start returning empty.

There is still no support for entity-level description; encode that in
entity `name`.

### 5. Time bar setting has two distinct layers

`global-settings.timebar.enabled = false` only suppresses the UI time
bar control on dashboards. The chat agent still auto-injects a default
time filter on the first field of `dataType = TIME` it finds:

```json
"time": {
  "timeField": "month_dt",
  "from": "+$start_of_month_-1_month",
  "to": "+$end_of_month"
}
```

For our build there is no documented setting to suppress this
chat-side injection. If your fact dates fall outside the rolling
2-month window the agent picks, queries return empty.

**Fix**: ensure fact-table date columns include rows in the recent
2-month window. If your data is historical, shift dates so the latest
month equals the current month.

---

## The four chat-agent behaviours to know

These are not bugs per se, but they're easy to misread as bugs.

### A. `sourceId` parameter is ignored

The Playground UI's source selector and the `sourceId` parameter on
`POST /api/v1/chat/stream` are advisory. The chat agent picks sources
autonomously based on which fields match the user's question. If two
sources have a field labelled "Transaction Amount", a question about
"transaction amount" may pull from either, and you cannot reliably scope
it.

**Mitigation**: prefix fact-table labels with a source-unique short
tag. Example: `Perf Successful Value`, `Due Amount Due`,
`Fee Transaction Amount`. Then questions phrased with the prefix word
reliably route to the intended source.

**Detection**: when an answer's count or total looks impossible,
check whether SI returned data from a different source. Common
giveaway: a number that exactly matches some other source's stats
(e.g. `1,323,234` is the frc.transactions count).

### B. The agent fabricates plausible answers when SQL returns empty

If `query_data` returns `[]`, the LLM does not always say so. It may
synthesise an answer that looks reasonable but is invented. We have
seen claims of "EU, UK, US" regions when the underlying data was
exclusively South African.

**Mitigation**: cross-check non-trivial answers against the underlying
database directly, or via the Playground's `{ }` icon next to the
response, which exposes the raw query and response. An empty `[]`
response with a confident answer is the signal.

### C. First-try stochasticity

Asking the same question twice can produce one "no data" and one
correct answer. The LLM's tool-calling path is non-deterministic.

**Mitigation**: for critical demo questions, dry-run them 2-3 times
beforehand. If a question is flaky, rephrase using the original column
name (`TRN_AMT`, `COST_FAIL`) — that consistently works because there
is no label-matching ambiguity.

### D. Phrasing variations matter at the grain level

"What is the X" can route to a different query plan than "Sum the X
field" or "What is the total X across all months". The "across all
months" form most reliably returns a single aggregate. Without it the
agent may produce monthly breakdowns or apply the auto-injected time
filter.

---

## Star-schema fan-out

Bare aggregates on a multi-fact star return inflated values. With
`branch` joined LEFT to two fact tables `A` and `B`, the SQL becomes
`branch × A × B` (with NULL-padding), and `SUM(B.amount)` double-counts
for any branch matching multiple `A` rows.

We observed:
- Multi-fact star: `SUM(AMT_DUE)` returns 5.7% inflated.
- Single-fact source (branch + legal_entity + one fact only): exact.

**The robust pattern for the API path**: one source per fact, all
sharing the same dimension entities. Three sources for three facts is
cheaper than one source with planner-side fan-out. Costs no extra
storage; each source is just a view definition.

**The other fan-out trap**: duplicate rows in the dimension. If
`branch_legal_entity` has two rows for some `BRANCH_CD`, every join
through it doubles those branches' contributions. Always check
dimension PK uniqueness:

```sql
SELECT "BRANCH_CD", COUNT(*) FROM schema.branch_legal_entity
GROUP BY 1 HAVING COUNT(*) > 1;
```

---

## API recipe: build a single-fact source end-to-end

This is the pattern that produced exact-match NLQ answers for us:

```python
import json, urllib.request

KEY = "<your-api-key>"
BASE = "https://simba.logisymphony.com"
CONN = "<connection-id>"
SCHEMA = "<schema-name>"
CT = "application/vnd.composer.v3+json"

def req(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE+path, data=data, method=method,
        headers={"Authorization":f"Bearer {KEY}",
                 "Content-Type":CT, "Accept":CT})
    with urllib.request.urlopen(r, timeout=60) as resp:
        return resp.status, json.loads(resp.read().decode() or "null")

# 1) POST with entities, no joins yet
payload = {
    "name": "My Source",
    "description": "...",
    "storage": {
        "dataEntities": [
            {"id":"dim","name":"Dimension","type":"SINGLE_COLLECTION",
             "singleCollection":{"connectionId":CONN,"schema":SCHEMA,
                                 "collection":"dim_table","parameters":{}}},
            {"id":"fact","name":"Fact","type":"SINGLE_COLLECTION",
             "singleCollection":{"connectionId":CONN,"schema":SCHEMA,
                                 "collection":"fact_table","parameters":{}}}
        ],
        "joins": []
    }
}
code, body = req("POST", "/discovery/api/sources", payload)
SID = body['id']

# 2) GET back to read auto-discovered field names
src = req("GET", f"/discovery/api/sources/{SID}")[1]

# 3) Locate the join key on each side
def field_for(entity_id, original_name):
    for e in src['storage']['dataEntities']:
        if e['id'] != entity_id: continue
        for f in e['nativeFields']:
            if f['origin']['nativeOrigin']['originalName'] == original_name:
                return f['fieldName']

# 4) Add the join
src['storage']['joins'] = [{
    "type":"LEFT",
    "leftDataEntity":{"dataEntityId":"dim","dimension":False},
    "rightDataEntity":{"dataEntityId":"fact","dimension":False},
    "conditions":[{
        "leftFieldName": field_for("dim","ID"),
        "rightFieldName": field_for("fact","ID")
    }]
}]

# 5) Apply semantic layer in the same PUT
for e in src['storage']['dataEntities']:
    for f in e['nativeFields']:
        f.pop('description', None)  # not accepted; strip if cloning
        # normalise to match working-source pattern
        if f.get('disabledCapabilities') == ['PLAYING']:
            f['disabledCapabilities'] = []
        no = f.get('origin',{}).get('nativeOrigin',{})
        if 'metaFlags' in no and no['metaFlags'] == []:
            no['metaFlags'] = ['PLAYABLE']
        # set label / visible per your plan
        # f['label'] = ...
        # f['visible'] = ...

req("PUT", f"/discovery/api/sources/{SID}", src)

# 6) Disable timebar
gs = req("GET", f"/discovery/api/sources/{SID}/global-settings")[1]
gs['timebar']['enabled'] = False
req("PUT", f"/discovery/api/sources/{SID}/global-settings", gs)

# 7) Flush cache so query engine picks up subsequent data changes
req("DELETE", f"/discovery/api/sources/{SID}/cache")
```

---

## Recovering from a broken source

If the editor white-screens or NLQ returns wrong answers, work through
this list in order:

1. **Confirm the entity has joins.** GET the source, check
   `storage.joins`. If empty with multiple entities, that is the
   editor-crash cause.
2. **Confirm join column types match.** GET each entity's
   `nativeFields`, check `dataType` of the join keys. Mismatch is the
   most common cause of "invalid join configuration" at PUT.
3. **Flush the source cache.**
   `DELETE /discovery/api/sources/{id}/cache` returns 200 if the
   source exists. This is required after any change to the underlying
   data (the source caches result sets even when
   `cacheSettings.rawCacheEnabled = false`).
4. **Verify the underlying data is reachable.** Hit
   `POST /discovery/api/connections/{conn-id}/preview?limit=3` with
   `{"schema": "...", "collection": "..."}`. If this returns rows, the
   connection is fine and the issue is in the source modelling.
5. **Cross-check the agent's response.** In the Playground, click
   `{ }` next to any answer to see the underlying query and raw
   response. If `Response` is `[]` but the agent reports a non-empty
   answer, the agent is fabricating.

---

## Reference IDs and useful endpoints

| Endpoint | Purpose |
|---|---|
| `GET /discovery/api/sources` | List sources visible to this key |
| `GET /discovery/api/sources/{id}` | Full source definition (including nativeFields and joins) |
| `POST /discovery/api/sources` | Create a source |
| `PUT /discovery/api/sources/{id}` | Update (validates joins) |
| `DELETE /discovery/api/sources/{id}` | Remove a source |
| `DELETE /discovery/api/sources/{id}/cache` | Flush result cache |
| `GET /discovery/api/sources/{id}/fields` | Flat field listing across entities |
| `GET /discovery/api/sources/{id}/global-settings` | Timebar, text search, country format |
| `PUT /discovery/api/sources/{id}/global-settings` | Update settings (e.g. disable timebar) |
| `POST /discovery/api/connections/{id}/preview?limit=N` | Preview rows from a collection |
| `POST /api/v1/chat/stream` | NLQ chat (SSE response) |

Content-Type for all PUT/POST: `application/vnd.composer.v3+json`.
Authorization: `Bearer <api-key>`.

The connection list endpoint returns all connections the key can read,
including ones in other accounts. Source listing is scoped to the
key's home account.

---

## Cross-references

- `troubleshooting.md` for cluster and pod-level issues
- `query-tracing.md` for reconstructing what the LLM did in Datadog
- `enabling-edcs.md` for setting up the EDC connectors that back the
  source's connection
