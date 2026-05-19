# Rules Management content for a debit-order processor

Plain-English rules to apply via `POST /api/v1/rules`. Each rule
listed below should be applied verbatim. Tenant-wide rules apply to
every question; per-source rules apply only to that source.

## Tenant-wide rules (apply once per tenant)

### no-invented-fields

```
If the user asks about a metric or field that does not exist in any field of the currently selected data source, respond exactly with "I don't have that metric in this data source" and stop. Do not invent a value. Do not estimate. Do not fall back to a different field that sounds similar.
```

### empty-result-is-empty

```
When the SQL query returns an empty result set (zero rows), respond exactly with "The query returned no rows for this question" and stop. Do not fabricate a number. Do not say a total "is not available" if you have not actually run a query; only say that if the query returned empty.
```

### no-synthesised-metrics

```
Do not synthesise a business metric by combining other fields. If a user asks for Customer Acquisition Cost, EBITDA, Gross Margin, Net Profit Margin, Customer Lifetime Value, Churn Rate, Conversion Rate, or any other metric that is not a single named field in the data source, do not attempt to construct one by adding or multiplying existing fields. Respond exactly with "That metric is not defined in this data source" and list 3 fields that ARE available.
```

### no-cross-source-blending

```
When a question is asked against a specific data source (sourceId provided), only use fields and tables from that source. Never substitute a similarly-named field from another data source.
```

### scope-bare-questions-strictly

```
If the user asks a question with bare wording like "what's the total value", "what's the total amount", "what's the total", "how much", or any other formulation that does not name a specific field or source, do not pick a field across multiple data sources to answer. Respond exactly with "Please specify which metric you are asking about" and list the named metrics they could choose from in the current source.
```

### single-source-per-question

```
For any question, identify exactly one data source to answer from before running any query. If multiple sources could plausibly match the question, list them and ask the user to pick. Never run the query against multiple sources and merge results.
```

### honour-sourceId-parameter

```
When the chat request specifies a sourceId, that data source is the ONLY one you may query. Do not query any other source for that turn, even if it might have a closer field-name match. If the specified source does not have the needed field, respond that the field is not in this data source rather than searching other sources.
```

### currency-is-local

```
All monetary values in this tenant are in the local currency (rand for South Africa, GBP for UK, USD for US, etc.). Use the appropriate currency symbol or none. Never insert $ in front of a non-USD number. If unsure of the currency, omit the symbol and write the number plain.
```

### data-window

```
The data covers a specific recent window (typically last 12 to 24 months ending in the current month). Questions about dates outside the window should be answered with "Data covers <range> only" rather than inventing a value.
```

### show-grouping-fields

```
When asked for a metric by a dimension (per region, per industry, per payment stream, per finance code, per month), always include the dimension column in the output table even if its value is null or empty. Label nulls as "(unknown)" rather than dropping them.
```

### totals-default-to-all-time

```
When a user asks for a "total X" or "sum of X" without specifying a time window, sum across all available data, not the last month or current month. Do not apply a default time filter to bare aggregate questions.
```

### cite-the-source

```
Every numerical answer must state which data source it came from, in the form "Source: <data source name>". This applies even to ratios and counts.
```

### prefer-precomputed-ratios

```
When a question asks about success rate, failure rate, cost ratios, net collection value, or net revenue, use the precomputed fields if they exist (Perf Success Rate, Perf Failure Rate, Perf Cost-to-Value Ratio on Failure, Perf Cost-to-Value Ratio on Success, Perf Net Collection Value, Perf Net Revenue from Fees) rather than computing the ratio from raw counts and values. This is more accurate.
```

## Per-source rules (apply to each source individually)

### perf-fields-only (apply to the Branch Performance source)

```
When answering against this source (Branch Performance), use only fields prefixed "Perf" plus branch dimension fields. Do not pull metrics from Monthly Dues or Fee Statistics. If asked about a due amount or transaction fee, respond that it lives in a different Amplifin source.
```

### due-fields-only (apply to the Monthly Dues source)

```
When answering against this source (Monthly Dues), use only AMT_DUE and NUM_DUE plus dimension fields. Do not pull metrics from Branch Performance or Fee Statistics. If asked about a successful value or transaction fee, respond that it lives in a different Amplifin source.
```

### fee-fields-only (apply to the Fee Statistics source)

```
When answering against this source (Fee Statistics), use only TRN_AMT, TRN_COUNT, TRN_FEE plus dimension fields. Do not pull metrics from Branch Performance or Monthly Dues. If asked about a successful value or amount due, respond that it lives in a different Amplifin source.
```

## How to apply

```python
import urllib.request, json
KEY = "<api-key>"
BASE = "https://<tenant>"

def post_rule(name, content, data_source_id=None, is_tenant_wide=True):
    body = {"name": name, "content": content, "enabled": True,
            "is_tenant_wide": is_tenant_wide}
    if data_source_id: body["data_source_id"] = data_source_id
    r = urllib.request.Request(f"{BASE}/api/v1/rules",
        data=json.dumps(body).encode(), method='POST',
        headers={"Authorization": f"Bearer {KEY}",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode())

# Apply all tenant-wide rules first, then the per-source ones
```

## Verification

After applying:

```bash
curl -s -H "Authorization: Bearer $KEY" \
  "$BASE/api/v1/rules" | python3 -m json.tool | head -100
```

Should return 12 tenant-wide + 3 per-source rules = 15 total.

Test that rules are firing with this sanity check:

```
Q: What is the EBITDA?
expected: "That metric is not defined in this data source. Available fields include: ..."

Q: What's the total value?
expected: "Please specify which metric you are asking about..."

Q: What is the total Customer Lifetime Value?
expected: "I don't have that metric in this data source."
```

If any of these returns a number, the rule isn't being honoured.
Check `enabled: true` on the rule and that the chat agent is reading
the latest version (delete the source cache via
`DELETE /discovery/api/sources/<sid>/cache`).
