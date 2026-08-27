# LLM Provider Configuration

Simba Intelligence is BYOLLM — Bring Your Own LLM. It does not ship with an
AI model and insightsoftware does not provide one. An external LLM provider
must be configured before AI features (Data Source Agent, Playground natural
language querying, vision analysis) will function.

---

## Supported providers and tested models

| Provider | Model | Status | Quality | Relative Cost |
|---|---|---|---|---|
| Google Vertex AI | Gemini 2.0 Flash | **RETIRED, 404s** | n/a | n/a |
| Google Vertex AI | Gemini 2.5 Flash | Supported | High | Medium |
| Google Vertex AI | Gemini 2.5 Pro | Supported | High | High |
| Azure OpenAI | GPT-4.1 | Supported | High | Medium |
| Azure OpenAI | GPT-4.1-mini | Supported | Standard | Low |
| Azure OpenAI | GPT-5.2 | Supported | High | Medium |
| AWS Bedrock | Nova Pro | Supported | Standard | Medium |
| AWS Bedrock | Claude Sonnet 4 | Supported | High | High |

Not recommended: GPT-3.5 (no structured output), GPT-4o (unreliable query
generation), Gemini 2.5 Flash Lite (unstable).

Recommendation: Vertex AI **Gemini 2.5 Flash** for both evaluation and production.
Gemini 2.0 Flash was the previous recommendation and no longer exists (see below).

---

## Configuration steps

1. Sign in with a supervisor or administrator account
2. Navigate to `/llm-configuration`
3. Select the provider tab
4. Enter credentials (see provider sections below)
5. Enable **Chat** capability (required)
6. Enable **Embeddings** capability (required)
7. Optionally enable **Vision** capability (for Data Agent image analysis)
8. Test the connection
9. Save

Both Chat and Embeddings must be active for Simba Intelligence to function.

---

## Google Vertex AI

**Prerequisites:**
- Google Cloud project with billing enabled
- Vertex AI API enabled
- Service account with `roles/aiplatform.user`
- Service account JSON key file

**Configuration:**
- Paste the complete service account JSON into the credentials field
- Chat model: `gemini-2.5-flash`. Do NOT use `gemini-2.0-flash`, it is retired (see below)
- Embeddings model: `text-embedding-004`
- Location: `us-central1` (or preferred region)

---

## Azure OpenAI

**Prerequisites:**
- Azure subscription with Azure OpenAI resource created
- Models deployed within the Azure OpenAI resource
- API key and endpoint URL

**Configuration:**
- API Key: the Azure OpenAI key
- Azure Endpoint: `https://<resource-name>.openai.azure.com/`
- API Version: `2023-05-15` or latest
- Chat Deployment Name: the name of your GPT-4.1 deployment
- Embeddings Deployment Name: the name of your embedding deployment

Note: use the deployment name, not the model name.

---

## AWS Bedrock

**Prerequisites:**
- AWS account with Bedrock access enabled in the target region
- IAM user or role with `bedrock:InvokeModel` and `bedrock:ListFoundationModels`
- Model access explicitly granted in the Bedrock console

**Configuration:**
- Access Key ID and Secret Access Key
- Region (e.g. `us-east-1`)
- Session Token (optional, for temporary credentials)

---

## OpenAI (direct)

**Configuration:**
- API Key: `sk-...`
- Organisation ID (optional)

---

## Air-gapped / local LLM (Ollama + LiteLLM)

SI only supports three provider types: **Vertex AI**, **Azure OpenAI**, and
**AWS Bedrock**. To use a local model (e.g. Llama via Ollama), configure it
as **Azure OpenAI** with a **LiteLLM proxy** that translates the Azure API
format to Ollama's OpenAI-compatible API.

### Architecture

```
SI → LiteLLM proxy (Azure OpenAI API) → Ollama (OpenAI-compatible API) → Local model
```

### Setup

1. **Install Ollama** (macOS: `brew install ollama && brew services start ollama`)
2. **Pull models:**
   ```bash
   ollama pull gemma4:e4b           # Chat — recommended (native function calling)
   ollama pull nomic-embed-text     # Embeddings (768 dimensions)
   ollama pull llama3.2-vision      # Vision (optional)
   ```
3. **Run LiteLLM proxy:**
   ```bash
   docker run -d --name ollama-azure-bridge \
     -p 8090:4000 \
     -v /path/to/litellm-config.yaml:/app/config.yaml:ro \
     ghcr.io/berriai/litellm:main-latest \
     --config /app/config.yaml --port 4000
   ```

### LiteLLM config file

```yaml
model_list:
  - model_name: "gemma4-e4b"              # deployment name for SI
    litellm_params:
      model: "ollama_chat/gemma4:e4b"     # MUST use ollama_chat/ prefix
      api_base: "http://host.docker.internal:11434"
  - model_name: "nomic-embed-text"
    litellm_params:
      model: "ollama/nomic-embed-text"    # ollama/ OK for embeddings
      api_base: "http://host.docker.internal:11434"
  - model_name: "llama3.2-vision"
    litellm_params:
      model: "ollama_chat/llama3.2-vision"
      api_base: "http://host.docker.internal:11434"
litellm_settings:
  drop_params: true    # Ollama doesn't support encoding_format: base64
general_settings:
  master_key: "sk-ollama-local"
```

**CRITICAL — `ollama_chat/` vs `ollama/` prefix:**
- Chat and vision models MUST use `ollama_chat/` for proper streaming tool
  call support. With `ollama/`, streaming responses return tool calls as
  plain text JSON (`{"name": "query_data", ...}`) instead of proper
  `tool_calls` delta objects, causing SI to display raw JSON in the
  Playground instead of executing queries.
- Embedding models should use `ollama/` (no tool calling needed).

### SI LLM Configuration (Azure OpenAI provider)

| Field | Value |
|---|---|
| API Key | `sk-ollama-local` (matches LiteLLM master_key) |
| Azure Endpoint | `http://host.docker.internal:8090` |
| API Version | `2024-02-01` |
| Chat Deployment Name | `gemma4-e4b` (matches model_name in LiteLLM) |
| Embeddings Deployment Name | `nomic-embed-text` |
| Vision Deployment Name | `llama3.2-vision` |

### Proxy timeout requirement

The SI Playground pipeline makes 5-8 sequential LLM calls per query. With
local models each call takes 7-12 seconds, totalling 60-120 seconds per
query. The default reverse proxy timeout (30s) will cut this short.

If using Caddy as the reverse proxy, increase the timeout:

```
route /* {
    reverse_proxy host.docker.internal:8082 {
        transport http {
            read_timeout 300s
            write_timeout 300s
        }
        flush_interval -1
    }
}
```

If using nginx or another proxy, set equivalent read/write timeouts to 300s.
Without this, queries will show "This request is taking longer than expected"
even though the backend is still processing.

### Model selection guidance — tested results

The following models were tested end-to-end against SI 26.1.1's Playground
with real data sources. "Tool calling" means the model correctly triggers
SI's query_data function. "Start-vis JSON" means it generates valid
Composer start-vis payloads for aggregations, time series, and rankings.

| Model | Size | Tool calling | Start-vis JSON | NLQ quality | Recommendation |
|---|---|---|---|---|---|
| Llama 3.2 3B | 2 GB | Broken — dumps raw JSON | N/A | N/A | Do not use |
| Mistral 7B | 4.1 GB | Works | N/A | Hallucinated — never queried real data | Do not use |
| Gemma 4 e2b | 7.2 GB | Works | Simple queries only, malformed on complex | Partial | Simple demos only |
| **Gemma 4 e4b** | **9.6 GB** | **Works** | **Valid for complex queries** | **7/7 passed with real data** | **Recommended for 32GB** |
| Gemma 4 26b | 18 GB | Untested | Expected better | Expected better | For 64GB+ hardware |

**Why Gemma 4?** Gemma 4 has native function-calling — meaning the model was
trained from the ground up to generate structured tool calls, not just text
responses. This is why it succeeds at generating valid start-vis JSON where
other models fail. Previous models could "see" the tools but couldn't
reliably fill in the structured payloads SI needs.

**Minimum model size:** 7B-class models (Llama 3B, Mistral 7B) can call the
tools but cannot generate valid start-vis queries — they either output raw
JSON as text or hallucinate answers without querying data. Gemma 4 e4b
(9.6GB, 4B active parameters with Google's latest architecture) is the
minimum model that reliably generates valid start-vis for complex queries
(aggregations, time series, rankings, cross-domain correlations).

**Hardware guidance:**
- 32GB RAM: Gemma 4 e4b works but responses take 1-2 minutes. Tight with
  Docker + daily apps.
- 64GB RAM: Gemma 4 26b or Mistral Small 24B — expected to be faster and
  handle more complex queries. Untested, needs hardware.
- Enterprise (128GB+ / GPU cluster): Llama 4 Maverick, DeepSeek V3 — near
  cloud LLM quality, fully airgapped.

### Native Ollama support (coming in 26.2)

Engineering has an unmerged PR for native Ollama support in SI (no LiteLLM
proxy needed). Tracked in Jira PY-516. It will be behind a Composer feature
toggle — hidden by default, enabled per-customer. The LiteLLM proxy approach
documented above works today and remains a valid option alongside native
support.

### Without any LLM

If no LLM is reachable at all, SI will deploy and run but AI features
(Data Source Agent, Playground natural language querying) will not function.
Data connections and manual data source configuration will still work.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "No LLM Configuration Found" | Provider not configured | Go to `/llm-configuration` |
| "Authentication failed" | Credentials invalid or truncated | Re-enter and test |
| "Model not found" | Wrong model or deployment name | Verify exact name with provider |
| "Rate limit exceeded" | Provider quota hit | Check provider dashboard |
| Data Agent fails | LLM not configured | Configure LLM first, then retry |
| Vision not working | Vision capability not enabled | Enable in LLM config (Vertex AI only) |

---

## Security recommendations

- Store credentials in an enterprise secrets manager and rotate per policy
- Use least-privilege IAM roles and service accounts
- Monitor usage and cost in the provider dashboard
- Only supervisor-role users should access `/llm-configuration`

---

## 26.2 update — providers and non-standard models (verified 2026-07-11)

**Four native provider types in 26.2:** Vertex AI, Azure OpenAI, AWS Bedrock, and
**Ollama** (`GET /api/v1/config/llm/providers`). Ollama is now first-class
(PY-516) — a local/air-gapped model with no LiteLLM proxy. There is still **no
native OpenAI-direct or xAI/Grok provider.**

**Running Grok or OpenAI-direct (or any non-native model): use a LiteLLM proxy**
that presents the Azure OpenAI wire format to SI and translates to the real
provider. This is the same bridge pattern already documented for Ollama-via-proxy.
Point SI's Azure OpenAI `azure_endpoint` at the proxy, `deployment_name` at the
proxy's `model_name`. Gotchas:
- SI's save-time probe sends `model: null`; xAI rejects it — the bridge absorbs it.
- **GPT-5.6 (Sol/Terra/Luna) does NOT drive SI's query pipeline** on chat
  completions: function tools require `reasoning_effort=none`, and with reasoning
  off the model is unreliable (fabricates auth errors). It needs the `/v1/responses`
  API, which SI does not call. The newest OpenAI model that works with SI is
  **GPT-5.5**; **GPT-5.4** is the current demo/prospect-parity default (works with
  reasoning + tools, accepts temperature 0, half the token cost of 5.5).

**Different LLMs per agent (26.2, PY-531):** query, source-creation and related
agents can now use different models — configure separate capabilities/configs.

**Embeddings-switch is safer in 26.2:** switching the embeddings provider on an
instance with existing sources now auto-detects and wipes the stale tenant-scoped
vector indexes (PY-557), so source-match vectors are rebuilt rather than silently
mismatched. Still verify source selection after switching. See
`references/si-26.2-release.md` for the full reconciliation.

---

## Shared Azure deployment contention (field lesson, 2026-07-20)

Symptom: persistent `429 rate_limit_exceeded` on a shared Azure OpenAI
deployment (for us: gpt-5.4 on symphony-eastus2) for 10+ minutes, across every
instance pointing at it. This is quota contention with other users of the shared
resource, not a burst; retrying does not clear it, and it can take a live demo
down (it did, org-wide, on 2026-07-16).

Robust demo posture: run chat through a LiteLLM bridge on your own key.
The bridge presents an Azure-compatible endpoint, so SI's Azure provider type
works unchanged:

- `llm_configurations.credentials`: `{"api_key": "<bridge token>",
  "api_version": "2025-01-01-preview", "azure_endpoint": "http://<bridge-host>:8104"}`
- chat capability `parameters`: `{"temperature": 0.0, "deployment_name": "<bridge model_name>"}`
- From a kind-cluster pod, the host bridge is reachable at the docker network
  gateway (typically `172.18.0.1`).
- Keep the original Azure config row for one-UPDATE rollback; restart the SI app
  and worker deployments after switching (config is read at startup).
- Embeddings can stay on Azure (ada-002 is rarely contended); mixed-capability
  configs across providers work.


---

## Verified against a live 26.2.1 instance, 27 August 2026

Configured end to end on a kind cluster with a Vertex AI service account. Everything below
was executed, not read.

### Gemini 2.0 Flash is retired and this document used to recommend it

Calling it through Vertex returns 404:

```
Publisher model projects/<project>/locations/us-central1/publishers/google/models/gemini-2.0-flash
was not found or your project does not have access to it.
```

Tested directly against Vertex with the service account, `us-central1`:

| model | result |
|---|---|
| `gemini-2.0-flash` | **404** |
| `gemini-2.0-flash-001` | **404** |
| `gemini-2.0-flash-lite` | **404** |
| `gemini-2.5-flash` | 200 |
| `gemini-2.5-pro` | 200 |
| `gemini-2.5-flash-lite` | 200 |

Embeddings all still work: `text-embedding-004`, `text-embedding-005`,
`text-multilingual-embedding-002`, `gemini-embedding-001`.

Note that this document lists Gemini 2.5 Flash Lite as "unstable, not recommended", and it
does resolve. That judgement is not retested here.

### SI reports this badly, so recognise it

SI validates a capability by actually calling the model, which is good. But the API returns
only `{"error": "Creation failed: Invalid Model Name"}`. The real cause, including the 404
and the full model path, appears **only in the pod log**:

```bash
kubectl -n simba-intel logs <si-pod> | grep "Validation failed for capability"
```

"Invalid Model Name" reads like a typo in the name. It usually means the model is not
available to that project or region.

### The API payload, which the UI steps do not give you

`POST /api/v1/config/llm`, authenticated, `Content-Type: application/json`:

```json
{
  "provider_id": "VERTEX_AI",
  "name": "Vertex AI Gemini 2.5 Flash",
  "credentials": { ...the ENTIRE service account JSON... },
  "is_active": true,
  "capabilities": [
    {"capability_type": "chat",       "is_active": true,
     "parameters": {"model_name": "gemini-2.5-flash",   "location": "us-central1"}},
    {"capability_type": "embeddings", "is_active": true,
     "parameters": {"model_name": "text-embedding-004", "location": "us-central1"}}
  ]
}
```

Four things that each cost a failed attempt:

1. The field is `provider_id`, not `provider`, and `name` and `capabilities` are required.
2. `capabilities` must be a list of **objects**. Passing `["chat","embeddings"]` gives a 500
   with `AttributeError: 'str' object has no attribute 'get'` in the log.
3. `capability_type` is **lowercase** on the way in (`chat`, `embeddings`, `vision`) and comes
   back uppercase.
4. `credentials` needs the **whole** service account document. Sending only the three
   `required_credentials` that `/api/v1/config/llm/providers` advertises gives
   `Service account info was not in the expected format, missing fields token_uri`.

Confirm with `GET /api/v1/config/llm/status`, which returns `{"is_configured":true}`.

### Authentication, which is not where you would look

SI's own login is `POST /api/v1/auth/login`, **form-encoded**, not JSON. JSON gives a 302 to
`/?error=invalid_credentials`. There is no separate SI admin: SI authenticates against
Composer using `COMPOSER_ADMIN_USERNAME` and `COMPOSER_ADMIN_PASSWORD`, sourced from secret
`si-discovery-web`.

A Composer session cookie cannot be reused for SI. Composer sets `SESSION` with
`Path=/discovery`, so the browser will never send it to SI at `/`. They must share an origin
through a gateway, and even then SI needs its own login.

**This whole `/api/v1/auth/*` family is missing from the reverse-engineered OpenAPI spec:**
`login`, `logout`, `token`, `check-auth`, `features`, `composer-session`. Anything that treats
that spec as complete will wrongly conclude these endpoints do not exist.
