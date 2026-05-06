# Simba Intelligence Setup — MCP Server

Exposes the SI deployment knowledge base as tools for Claude Desktop (or any MCP client). Once configured, Claude can read any reference guide, search documentation, and retrieve install scripts without needing the skill files manually uploaded.

## Tools

| Tool | Description |
|---|---|
| `get_skill_overview` | Full SKILL.md — architecture, decision trees, troubleshooting quick-ref |
| `list_guides` | List all available reference guide names |
| `read_guide(name)` | Read a specific guide by name |
| `get_deployment_guide(environment)` | Deployment guide for local / eks / aks / gke / onprem / airgapped |
| `search_docs(query)` | Full-text search across all guides |
| `get_universal_llm_guide` | Consolidated guide for non-Claude LLMs |
| `get_install_script(environment, os_type)` | Pre-built install script content |

## Prerequisites

- Python 3.10+
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) — `brew install uv` on macOS

## Add to Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "simba-intelligence-setup": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/simba-intelligence-skill/mcp-server",
        "run",
        "server.py"
      ]
    }
  }
}
```

Replace `/path/to/simba-intelligence-skill` with the actual path where you cloned the repo. Restart Claude Desktop after saving.

## Verify

Once Claude Desktop restarts, open a new chat and ask:

> "List the available SI setup guides."

Claude should call `list_guides` and return the full list without any skill files uploaded.
