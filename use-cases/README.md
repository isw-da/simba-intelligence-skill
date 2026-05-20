# SI use case library

Reusable starter kits for common Simba Intelligence customer
profiles. Each folder contains:

- A description of the business domain
- The expected data shape (tables, columns, cardinality)
- A suggested question bank (50+ NLQs, tiered by intent and demo flow)
- Suggested rules for Rules Management
- Suggested `fieldMetadata` per field
- Suggested derived fields (precomputed ratios, net values)
- A sample demo flow

The point: when you walk into a new prospect that broadly resembles
one of these profiles, you don't start from a blank source. You apply
the template, swap names, and have a working demo in an hour.

## Current use cases

| Folder | Domain | Built from |
|---|---|---|
| `debit-order-payments/` | Payments processor handling debit-order collections on behalf of lenders / merchants | the customer (May 2026) |

## How to use a use case

1. Read the use case's README to confirm the prospect fits the profile.
2. Check the prospect's data against the "Required data shape" section.
   Anything missing or shaped differently goes on a discovery question.
3. Apply the suggested rules first (Rules Management is the cheapest
   correctness improvement).
4. Build the source via the API recipe in
   `simba-intelligence-setup/references/data-source-modelling.md`,
   substituting the prospect's table names.
5. Apply the field metadata and label conventions from the use case.
6. Run the question bank as the audit suite.
7. Pick 8-12 questions for the demo flow.
