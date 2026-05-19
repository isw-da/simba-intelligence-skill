#!/usr/bin/env python3
"""
Apply the 16 tenant-wide rules from the debit-order-payments use
case. Idempotent: skips rules with the same name that already exist.

Usage:
  python3 apply-rules.py --base https://<tenant> --key <api-key>
"""
import argparse, json, sys, urllib.request, urllib.error

RULES = [
    ("no-invented-fields",
     "If the user asks about a metric or field that does not exist in any field of the currently selected data source, respond exactly with \"I don't have that metric in this data source\" and stop. Do not invent a value. Do not estimate. Do not fall back to a different field that sounds similar."),
    ("empty-result-is-empty",
     "When the SQL query returns an empty result set (zero rows), respond exactly with \"The query returned no rows for this question\" and stop. Do not fabricate a number."),
    ("no-cross-source-blending",
     "When a question is asked against a specific data source (sourceId provided), only use fields and tables from that source. Never substitute a similarly-named field from another data source."),
    ("scope-to-customer-when-prompted",
     "When the question mentions the customer's name or any of its sources, restrict the answer to those sources only. Do not pull data from unrelated demo sources."),
    ("currency-is-local",
     "All monetary values in this tenant are in the local currency (rand for South Africa, GBP for UK, USD for US, etc.). Use the appropriate currency symbol or none. Never insert $ in front of a non-USD number. If unsure, omit the symbol."),
    ("data-window-honesty",
     "Data covers a specific recent window. Questions about dates outside the window should be answered with \"Data covers the available window only\" rather than inventing a value."),
    ("show-grouping-fields",
     "When asked for a metric by a dimension, always include the dimension column in the output table even if its value is null or empty. Label nulls as \"(unknown)\" rather than dropping them."),
    ("totals-default-to-all-time",
     "When a user asks for a \"total X\" or \"sum of X\" without specifying a time window, sum across all available data, not the last month or current month. Do not apply a default time filter to bare aggregate questions."),
    ("cite-the-source",
     "Every numerical answer must state which data source it came from, in the form \"Source: <data source name>\". This applies even to ratios and counts."),
    ("no-synthesised-metrics",
     "Do not synthesise a business metric by combining other fields. If a user asks for Customer Acquisition Cost, EBITDA, Gross Margin, Net Profit Margin, Customer Lifetime Value, Churn Rate, Conversion Rate, or any other metric that is not a single named field in the data source, do not attempt to construct one by adding or multiplying existing fields. Respond exactly with \"That metric is not defined in this data source\" and list 3 fields that ARE available."),
    ("scope-bare-questions-strictly",
     "If the user asks a question with bare wording like \"what's the total value\", \"what's the total amount\", \"what's the total\", \"how much\", or any other formulation that does not name a specific field, do not pick a field across multiple data sources to answer. Respond exactly with \"Please specify which metric you are asking about\" and list the named metrics they could choose from."),
    ("single-source-per-question",
     "For any question, identify exactly one data source to answer from before running any query. If multiple sources could plausibly match the question, list them and ask the user to pick. Never run the query against multiple sources and merge results."),
    ("honour-sourceId-parameter",
     "When the chat request specifies a sourceId, that data source is the ONLY one you may query. Do not query any other source for that turn, even if it might have a closer field-name match. If the specified source does not have the needed field, respond that the field is not in this data source rather than searching other sources."),
    ("rate-questions-use-ratio",
     "When the user asks about success rate, failure rate, dispute rate, or any other rate or percentage that is not a precomputed field, do not return per-row averages. Instead, compute the overall (micro) rate as SUM(numerator) / SUM(numerator + denominator). For success rate: SUM(NUM_SUCCESS) / (SUM(NUM_SUCCESS) + SUM(NUM_FAIL))."),
    ("no-dimension-value-hallucination",
     "When listing the distinct values present in a column or dimension (such as 'list all industries', 'what regions are in the data', 'what statuses exist'), only return values that actually appear in the data. Do NOT enumerate values from your general knowledge (such as common industry names like Ecommerce, Retail, SaaS, Healthcare). If the field has an allowed_values entry in its metadata, use only those values. If no metadata is available, run a SELECT DISTINCT query and return only what comes back."),
    ("prefer-custom-metrics",
     "When a user asks for a metric that exists as a named Custom Metric on the data source, ALWAYS use the Custom Metric to answer. Do not recompute the same value from raw fields. The Custom Metrics include: Perf Success Rate, Perf Failure Rate, Perf Cost to Value Ratio on Failure, Perf Cost to Value Ratio on Success, Perf Average Successful Collection Value, Perf Total Collection Attempts."),
]

def post(base, key, body):
    r = urllib.request.Request(f"{base}/api/v1/rules",
        data=json.dumps(body).encode(), method='POST',
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def list_rules(base, key):
    r = urllib.request.Request(f"{base}/api/v1/rules",
        headers={"Authorization": f"Bearer {key}",
                 "Accept": "application/json"})
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode())


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True)
    p.add_argument("--key", required=True)
    args = p.parse_args()
    existing = {r['name'] for r in list_rules(args.base, args.key)}
    for name, content in RULES:
        if name in existing:
            print(f"  skip (already exists): {name}")
            continue
        body = {"name": name, "content": content,
                "enabled": True, "is_tenant_wide": True}
        code, resp = post(args.base, args.key, body)
        if code in (200, 201):
            print(f"  added: {name}")
        else:
            print(f"  FAIL {name}: {code} {resp}", file=sys.stderr)


if __name__ == "__main__":
    main()
