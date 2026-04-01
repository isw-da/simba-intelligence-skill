# LLM Provider Configuration

Simba Intelligence is BYOLLM — Bring Your Own LLM. It does not ship with an
AI model and insightsoftware does not provide one. An external LLM provider
must be configured before AI features (Data Source Agent, Playground natural
language querying, vision analysis) will function.

---

## Supported providers and tested models

| Provider | Model | Status | Quality | Relative Cost |
|---|---|---|---|---|
| Google Vertex AI | Gemini 2.0 Flash | Supported | Standard | Low |
| Google Vertex AI | Gemini 2.5 Flash | Supported | High | Medium |
| Google Vertex AI | Gemini 2.5 Pro | Supported | High | High |
| Azure OpenAI | GPT-4.1 | Supported | High | Medium |
| Azure OpenAI | GPT-4.1-mini | Supported | Standard | Low |
| Azure OpenAI | GPT-5.2 | Supported | High | Medium |
| AWS Bedrock | Nova Pro | Supported | Standard | Medium |
| AWS Bedrock | Claude Sonnet 4 | Supported | High | High |

Not recommended: GPT-3.5 (no structured output), GPT-4o (unreliable query
generation), Gemini 2.5 Flash Lite (unstable).

Recommendation: Vertex AI Gemini 2.0 Flash for evaluation and development,
Gemini 2.5 Flash for production workloads.

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
- Chat model: `gemini-2.0-flash` (dev) or `gemini-2.5-flash` (prod)
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
   ollama pull llama3.1:8b          # Chat (minimum 8B for tool calling)
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
  - model_name: "llama-chat"              # deployment name for SI
    litellm_params:
      model: "ollama_chat/llama3.1:8b"    # MUST use ollama_chat/ prefix
      api_base: "http://host.docker.internal:11434"
  - model_name: "nomic-embed-text"
    litellm_params:
      model: "ollama/nomic-embed-text"    # ollama/ OK for embeddings
      api_base: "http://host.docker.internal:11434"
  - model_name: "llama-vision"
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
| Chat Deployment Name | `llama-chat` (matches model_name in LiteLLM) |
| Embeddings Deployment Name | `nomic-embed-text` |
| Vision Deployment Name | `llama-vision` |

### Model selection guidance

| Model | Size | Tool calling | Suitability |
|---|---|---|---|
| Llama 3.2 3B | 2 GB | Poor — outputs raw JSON | NOT recommended |
| Llama 3.1 8B | 4.7 GB | Good — proper function calls | Minimum viable |
| Llama 3.3 70B | 40 GB | Excellent | Best quality, needs 48GB+ RAM |

Llama 3.2 3B is too small for SI's multi-step tool-calling pipeline. It
outputs tool call JSON as text content instead of making structured function
calls. Use 8B minimum.

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
