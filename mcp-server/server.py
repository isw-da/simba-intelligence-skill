#!/usr/bin/env python3
"""
Simba Intelligence Setup MCP Server

Exposes the SI deployment knowledge base as MCP tools for Claude Desktop.
Each tool returns one or more reference guide sections so Claude can guide
users through any part of the SI lifecycle without having the skill files
manually uploaded.
"""

from mcp.server.fastmcp import FastMCP
from pathlib import Path

mcp = FastMCP("simba-intelligence-setup")

_SKILL_DIR = Path(__file__).parent.parent / "simba-intelligence-setup"
_REFS_DIR = _SKILL_DIR / "references"
_SCRIPTS_DIR = _SKILL_DIR / "scripts"

_GUIDE_MAP: dict[str, str] = {
    "prerequisites":       "prerequisites.md",
    "deployment-local":    "deployment-local.md",
    "deployment-eks":      "deployment-eks.md",
    "deployment-cloud":    "deployment-cloud.md",
    "deployment-onprem":   "deployment-onprem.md",
    "deployment-airgapped":"deployment-airgapped.md",
    "local-access":        "local-access.md",
    "production-ingress":  "production-ingress.md",
    "llm-config":          "llm-config.md",
    "enabling-edcs":       "enabling-edcs.md",
    "custom-edc-build":    "custom-edc-build.md",
    "post-install":        "post-install.md",
    "troubleshooting":     "troubleshooting.md",
    "datadog-logs":        "datadog-logs.md",
    "tenant-discovery":    "tenant-discovery.md",
    "gui-install-guide":   "gui-install-guide.md",
    "team-sharing":        "team-sharing.md",
    "teardown":            "teardown.md",
}

_ENV_TO_GUIDE: dict[str, str] = {
    "local":          "deployment-local",
    "docker-desktop": "deployment-local",
    "kind":           "deployment-local",
    "eks":            "deployment-eks",
    "aws":            "deployment-eks",
    "aks":            "deployment-cloud",
    "azure":          "deployment-cloud",
    "gke":            "deployment-cloud",
    "gcp":            "deployment-cloud",
    "onprem":         "deployment-onprem",
    "on-premises":    "deployment-onprem",
    "on-prem":        "deployment-onprem",
    "airgapped":      "deployment-airgapped",
    "air-gapped":     "deployment-airgapped",
}

_SCRIPT_MAP: dict[tuple[str, str], str] = {
    ("local", "macos"):   "install-si.sh",
    ("local", "linux"):   "install-si.sh",
    ("local", "windows"): "install-si.ps1",
    ("aks",   "macos"):   "install-si-aks.sh",
    ("aks",   "linux"):   "install-si-aks.sh",
}


@mcp.tool()
def get_skill_overview() -> str:
    """
    Get the complete Simba Intelligence Setup skill overview.
    Includes architecture, deployment decision trees, post-deploy sequence,
    troubleshooting quick-reference, and available automation scripts.
    Read this first when starting any SI-related task.
    """
    return (_SKILL_DIR / "SKILL.md").read_text()


@mcp.tool()
def list_guides() -> list[str]:
    """List all available reference guide names. Pass any name to read_guide()."""
    return list(_GUIDE_MAP.keys())


@mcp.tool()
def read_guide(name: str) -> str:
    """
    Read a specific reference guide by name.
    Run list_guides() first to see valid names.

    Args:
        name: Guide name, e.g. 'deployment-local', 'llm-config', 'troubleshooting'
    """
    if name not in _GUIDE_MAP:
        return (
            f"Guide '{name}' not found.\n"
            f"Available: {', '.join(_GUIDE_MAP.keys())}"
        )
    path = _REFS_DIR / _GUIDE_MAP[name]
    return path.read_text()


@mcp.tool()
def get_deployment_guide(environment: str) -> str:
    """
    Get the deployment guide for a specific environment.

    Args:
        environment: One of: local, docker-desktop, kind, eks, aws,
                     aks, azure, gke, gcp, onprem, on-prem, airgapped, air-gapped
    """
    key = environment.lower().strip()
    guide = _ENV_TO_GUIDE.get(key)
    if not guide:
        return (
            f"Unknown environment '{environment}'.\n"
            f"Supported: {', '.join(_ENV_TO_GUIDE.keys())}\n\n"
            "Run read_guide('prerequisites') first if this is a fresh machine."
        )
    return (_REFS_DIR / _GUIDE_MAP[guide]).read_text()


@mcp.tool()
def search_docs(query: str) -> str:
    """
    Full-text search across all SI reference guides.
    Returns up to 5 matching excerpts per guide, with context lines.

    Args:
        query: Search term, e.g. 'Helm values', 'Oracle JDBC', 'login loop'
    """
    query_lower = query.lower()
    results: list[str] = []

    for name, filename in _GUIDE_MAP.items():
        content = (_REFS_DIR / filename).read_text()
        lines = content.split("\n")
        excerpts: list[str] = []
        for i, line in enumerate(lines):
            if query_lower in line.lower():
                start = max(0, i - 2)
                end = min(len(lines), i + 3)
                excerpts.append("\n".join(lines[start:end]))
                if len(excerpts) >= 5:
                    break
        if excerpts:
            results.append(f"### {name}\n\n" + "\n\n---\n\n".join(excerpts))

    if not results:
        return f"No matches for '{query}' across SI documentation."
    return "\n\n".join(results)


@mcp.tool()
def get_universal_llm_guide() -> str:
    """
    Get the universal Simba Intelligence LLM guide — a single consolidated
    reference that works with any LLM (ChatGPT, Gemini, Copilot, etc.).
    Use this when the customer's team does not use Claude.
    """
    return (_SKILL_DIR / "universal" / "simba-intelligence-llm-guide.md").read_text()


@mcp.tool()
def get_install_script(environment: str = "local", os_type: str = "macos") -> str:
    """
    Get the contents of a pre-built install script.

    Args:
        environment: 'local' or 'aks'
        os_type: 'macos', 'linux', or 'windows'
    """
    key = (environment.lower().strip(), os_type.lower().strip())
    script = _SCRIPT_MAP.get(key)
    if not script:
        available = ", ".join(f"{e}/{o}" for (e, o) in _SCRIPT_MAP)
        return (
            f"No pre-built script for {environment}/{os_type}.\n"
            f"Available combinations: {available}\n\n"
            "For other environments, ask Claude to generate a custom script "
            "based on get_skill_overview() and the relevant deployment guide."
        )
    return (_SCRIPTS_DIR / script).read_text()


if __name__ == "__main__":
    mcp.run()
