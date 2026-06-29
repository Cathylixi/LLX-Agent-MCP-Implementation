"""
LLX Agent — minimal MCP server (Phase 1).

This is the "skills library". For now it runs locally over HTTP so we can prove
the chain: local Claude Code -> auto MCP call -> skill runs -> returns result.

Later this exact server moves to Azure Container Apps; only the URL in
.mcp.json changes on the employee side.

Run:
    pip install -r ../requirements.txt
    python main.py
Then it serves at: http://127.0.0.1:8000/mcp
"""

import os

from mcp.server.fastmcp import FastMCP

# The name shown to the MCP client.
# host=0.0.0.0 so it's reachable inside a container; PORT is configurable
# (Azure Container Apps / local both work). Locally still reachable at 127.0.0.1.
mcp = FastMCP(
    "llx-skills",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8000")),
)


@mcp.tool()
def search_news(keyword: str) -> str:
    """Find today's news about a topic.

    Use this whenever the user asks to find, look up, or search today's news.

    Args:
        keyword: the topic to search news for (e.g. "AI", "finance").
    """
    # Phase 1: return a fake line just to prove the chain works.
    # Later, the real (confidential) logic lives here and runs in the cloud.
    print(f"[SKILL CALLED] search_news(keyword={keyword!r})", flush=True)
    return (
        f"Today's news about '{keyword}': "
        f"[demo result] The LLX Agent MCP server is working!"
    )


@mcp.tool()
def get_project_status(project_code: str) -> dict:
    """Look up the current status of an internal LLX project.

    Use this whenever the user asks about the status, owner, deadline, or
    progress of an LLX project / study by its project code (e.g. "LLX-204").
    This is internal company data and has no public/web equivalent.

    Args:
        project_code: the LLX project code, e.g. "LLX-204".
    """
    print(f"[SKILL CALLED] get_project_status(project_code={project_code!r})", flush=True)

    # Phase 1: fake in-memory data. Later this reads from the real internal
    # source (database / SAS server) and runs in the cloud.
    fake_db = {
        "LLX-204": {
            "name": "Phase III TOC Automation",
            "status": "On Track",
            "owner": "Xi Li",
            "deadline": "2026-08-15",
            "progress_pct": 65,
        },
        "LLX-117": {
            "name": "SAS Macro Library Refresh",
            "status": "At Risk",
            "owner": "Data Eng Team",
            "deadline": "2026-07-10",
            "progress_pct": 40,
        },
    }

    code = project_code.strip().upper()
    if code in fake_db:
        return {"project_code": code, **fake_db[code]}
    return {
        "project_code": code,
        "status": "Not Found",
        "note": f"No LLX project with code '{code}' (demo data only).",
    }


if __name__ == "__main__":
    # streamable-http transport => served at http://127.0.0.1:8000/mcp
    mcp.run(transport="streamable-http")
