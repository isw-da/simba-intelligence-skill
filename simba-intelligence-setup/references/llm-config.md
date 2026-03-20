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

## Air-gapped environments

If the cluster cannot reach external LLM endpoints, options include:
- Self-hosted model with an OpenAI-compatible API — configure as OpenAI
  provider with the internal endpoint URL
- Network exception for outbound 443 to the specific provider endpoint
- AWS Bedrock via VPC endpoint (no public internet required)

Without any LLM provider, SI deploys and runs but AI features will not
function. Manual data source configuration and data connections still work.

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
