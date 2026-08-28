# simba-intelligence-skill — coding rules

## Documentation is mandatory, not optional

**Before answering any question about SI, Composer APIs, configuration,
troubleshooting, or behaviour, read the docs first.**

The canonical doc corpus lives in `isw-da/logi-si-docs`:

- SI product docs: `simba-intelligence/llms-full.txt` and `simba-intelligence/pages/*.md`
  (Mintlify corpus; the definitive reference for NLQ, LLM config, EDCs, RLS,
  and all SI product behaviour)
- Composer current docs: `logi-composer-current/v25/` and `v26/`
  (live v25/v26 product docs; the devnet Zendesk covers only legacy v5/v6)
- Composer OpenAPI: `composer-api/composer-openapi.json`, currently the SI-bundled
  26.2.1 pull at 223 paths and 344 operations. The mirror also keeps
  `composer-api/composer-openapi-simba-logisymphony.json`, the hosted pull, at 220
  paths and 338 operations. The two disagree, because an OpenAPI document describes
  the instance that served it rather than the product, so confirm an endpoint against
  the instance in front of you before promising it. Both cover SI Discovery, which is
  served by the Composer backend.
- Composer endpoint index: `composer-api/ENDPOINTS.md`

Clone it locally when you need to work from these docs:

```bash
git clone --depth 1 https://github.com/isw-da/logi-si-docs.git
```

The setup and deployment guides in `simba-intelligence-setup/references/` are
the second doc surface. Read the relevant guide before generating or editing
any setup instruction.

Do not answer from training-data memory. Consulting the docs first and then
answering is slower by seconds; answering from stale training data and being
wrong costs the customer trust.

## SI / Composer architecture facts

- SI is built on Logi Composer. The Helm chart aliases the Composer subchart
  as `discovery`. EDC connectors live in Composer.
- The SI Discovery backend (`/discovery/api/*`) is byte-identical to the
  Composer backend. The Composer OpenAPI spec covers both.
- Composer APIs are available to SI callers at the `/discovery` context by
  default (overridden by `SI_COMPOSER_CONTEXT` in the MCP).
- The Mintlify docs at `insightsoftware.mintlify.app` are the canonical SI
  product reference. The devnet Zendesk (`logi-devnet/`) covers legacy products.

## Companion repos

- `isw-da/simba-intelligence-mcp` — MCP server; consumes this skill's guides
  via `refresh-docs.sh`; also pulls the full logi-si-docs corpus
- `isw-da/logi-si-docs` — canonical doc mirror; always consult before writing
  or editing any SI or Composer content

## Coding rules

- British English in prose, comments, and commit messages.
- Touch only what the task requires.
- No new abstractions unless the task demands it.
