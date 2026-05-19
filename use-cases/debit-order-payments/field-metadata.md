# Field metadata template

Per-field `fieldMetadata.description` values to apply via the
Discovery API. Keep descriptions declarative, not prescriptive.

## How to apply

```python
src = get(f"/discovery/api/sources/{sid}")
for e in src['storage']['dataEntities']:
    for f in e.get('nativeFields',[]):
        orig = f.get('origin',{}).get('nativeOrigin',{}).get('originalName','').upper()
        if orig in META:
            f['fieldMetadata'] = {"description": META[orig]}
put(f"/discovery/api/sources/{sid}", src)
```

## Metadata content

### Branch performance fact

```python
META = {
    "VAL_SUCCESS":"Monetary value of successful debit-order collections at this branch",
    "VAL_FAIL":"Monetary value of failed debit-order collections at this branch",
    "VAL_DISP":"Monetary value of disputed debit-orders at this branch",
    "TOTAL_AMT":"Gross monetary value of debit-orders processed for this branch",
    "INST_AMT":"Instalment amount on the branch performance row",
    "NUM_SUCCESS":"Number of successful debit-order collections at this branch",
    "NUM_FAIL":"Number of failed debit-order collections at this branch",
    "NUM_DISP":"Number of disputed debit-orders at this branch",
    "NUM_SUSP":"Number of suspended debit-orders at this branch",
    "NUM_TRACK":"Number of debit-orders being tracked at this branch",
    "FEE_SUCCESS":"Fee revenue on successful debit-order collections",
    "FEE_FAIL":"Fee revenue on failed debit-order collections",
    "FEE_DISP":"Fee revenue on disputed debit-orders",
    "FEE_SUSP":"Fee revenue on suspended debit-orders",
    "FEE_TRACK":"Fee revenue on tracking activity",
    "IFEE_SUCCESS":"Internal branch-side fees on successful collections",
    "IFEE_INST_AMT":"Internal-fee instalment amount",
    "COST_SUCCESS":"Internal cost to process a successful collection",
    "COST_FAIL":"Internal cost to process a failed collection",
    "COST_DISP":"Internal cost on disputed collections",
    "COST_SUSP":"Internal cost on suspended collections",
    "COST_TRACK":"Internal cost on tracking activity",

    # Precomputed (see derived-fields.md)
    "NET_COLLECTION_VALUE":"Precomputed net collection value: successful value minus failed value. Use this directly when asked about net collections.",
    "NET_REVENUE_FROM_FEES":"Precomputed net revenue from fees: sum of all fee-categories minus all cost-categories. Use this directly when asked about net fee revenue.",
}
```

### Monthly dues fact

```python
META.update({
    "AMT_DUE":"Monetary amount due to be collected from this branch in the month",
    "NUM_DUE":"Number of debit-orders due to be collected from this branch in the month",
})
```

### Fee statistics fact

```python
META.update({
    "TRN_AMT":"Monetary value of fee-bearing transactions at this branch",
    "TRN_COUNT":"Number of fee-bearing transactions at this branch",
    "TRN_FEE":"Total fee revenue collected on the transactions",
    "TRN_DESC":"Free-text description tag on a transaction",
})
```

### Dimension fields (shared across sources)

```python
META.update({
    "BRANCH_CD":"Branch primary identifier",
    "REGION":"Geographic region of the branch",
    "INDUSTRY":"Primary industry classification of the legal entity behind the branch",
    "MONTH_DT":"Calendar month for the fact row",
    "STATUS":"Branch operational status",
    "FIN_CD":"Finance / funder code identifying which lender owns the debit-order",
    "PMT_STREAM":"Payment-stream type",
})
```

## Anti-patterns to avoid

Do NOT include in `fieldMetadata.description`:

- Grain hints like "summed by branch per month, grouped by stream".
  This steers the LLM into specific query plans and breaks bare
  aggregate questions.
- Cross-source disambiguation language ("this is NOT the X from Y
  source"). The LLM reads this as a hint to query the other source.
- Formulas or aggregation instructions ("AVG this", "SUM that").
  defaultMetric on the field already covers this.
- Marketing fluff ("this important metric tracks our value chain").
  Wastes tokens.

The single best description is one declarative sentence: what the
value represents in business English, in the local currency unit,
scoped to the right grain.

## Why only `description`?

The UI surface allows up to 5 properties per field. In our testing,
adding `unit`, `source`, `domain`, `scope` keys made the LLM more
phrasing-sensitive without improving accuracy on the most common
questions. One `description` is the right balance.

If you do add more keys, restrict to:

- `unit`: "rand (ZAR)", "USD", "count", "percentage" — short, factual
- `source`: only if the field name itself is ambiguous across sources

Skip everything else.
