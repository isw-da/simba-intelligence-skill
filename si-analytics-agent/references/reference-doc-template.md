# [Domain] Tables

Written for retrieval by an LLM. Describe tables and gotchas and routing triggers,
not prescriptive recipes that go stale.

## Quick Reference
### Business Context
[What this domain means in plain words.]
### Entity Grain
[What one row represents.]
### Standard Hygiene Filter
[The filter every query in this domain applies, e.g. exclude internal test accounts.]

## Dimensions
- [How the key dimensions are encoded, and how the same concept is named
  differently across tables.]

## Key Tables
### [table_name]
- Grain: [...]
- Scope / exclusions: [...]
- Usage: [when to use it, when NOT to, join keys, required filters]

[... one short section per governed table ...]

## Gotchas
- [The wrong-answer modes a senior analyst would warn you about. Example:
  "exclude known free-email domains but keep custom ones like the customer's own".]

## Routing Triggers
- IF the question is about [X] DO NOT use this table for [Y].

## Best Practices / Common Query Patterns
- [Default choices, standard cuts, worked patterns where the query form is the hard part.]

## Cross-References
- [Neighbouring domain docs that own adjacent questions.]
