"""
LLX Agent — MCP server (the "skills library").

Employees run local Claude Code; it auto-calls these skills over MCP. The skill
code/data run here on the server (Azure Container Apps) and are never sent to the
employee's machine, so employees can use the skills but cannot read them.

This file has 4 sections:
  1. SERVER SETUP      - create the MCP server
  2. DEMO SKILLS       - fake-data examples (search_news, get_project_status)
  3. DATABASE SKILLS   - talk to the real Cosmos DB (db_list_collections)
  4. ENTRY POINT       - start the server

Run locally:
    pip install -r ../requirements.txt
    python main.py            # serves at http://127.0.0.1:8000/mcp
"""

import os

from mcp.server.fastmcp import FastMCP


# ---------------------------------------------------------------------------
# 1. SERVER SETUP
# ---------------------------------------------------------------------------
# Create the MCP server. host=0.0.0.0 makes it reachable inside a container;
# PORT is read from the environment (Azure sets the port, defaults to 8000
# locally). Each function below decorated with @mcp.tool() becomes a "skill"
# that Claude can discover and call automatically.
mcp = FastMCP(
    "llx-skills",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8000")),
)


# ---------------------------------------------------------------------------
# 2. DEMO SKILLS (fake data)
# ---------------------------------------------------------------------------
# These return hard-coded data. They exist only to prove the chain works and
# serve as templates. Replace them with real logic when ready.

@mcp.tool()
def search_news(keyword: str) -> str:
    """Find today's news about a topic.

    Use this whenever the user asks to find, look up, or search today's news.

    Args:
        keyword: the topic to search news for (e.g. "AI", "finance").
    """
    print(f"[SKILL CALLED] search_news(keyword={keyword!r})", flush=True)
    # NOTE: this overlaps with Claude's built-in web search, so Claude may
    # prefer the built-in one. Internal skills (below) have no built-in
    # equivalent and are always auto-selected.
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

    # Fake in-memory data for the demo. Later this can read from the database
    # (see section 3) instead of this dictionary.
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


# ---------------------------------------------------------------------------
# 3. DATABASE SKILLS (real Cosmos DB)
# ---------------------------------------------------------------------------
# These connect to the company's Azure Cosmos DB (MongoDB API), database
# "llxdocument". The connection string is NEVER hard-coded here — it is read
# from the MONGO_URI environment variable, which is set as an encrypted Azure
# secret. That keeps the password out of the (public) source code.

@mcp.tool()
def db_list_collections() -> dict:
    """List the data collections available in the LLX document database.

    Use this to discover what internal data exists in the company database.
    This is internal LLX data and has no public/web equivalent.

    (Connectivity check: confirms the cloud server can reach the Cosmos DB.)
    """
    print("[SKILL CALLED] db_list_collections()", flush=True)

    # Read the secret connection string from the environment (set in Azure).
    uri = os.environ.get("MONGO_URI")
    if not uri:
        return {"error": "Database is not configured on the server (MONGO_URI missing)."}

    try:
        # Import here (not at top) so the server still starts even if pymongo
        # isn't installed locally; only this skill needs it.
        from pymongo import MongoClient

        # Connect with an 8s timeout so a network problem fails fast instead
        # of hanging.
        client = MongoClient(uri, serverSelectionTimeoutMS=8000)
        try:
            db = client["llxdocument"]
            collections = db.list_collection_names()
            return {
                "database": "llxdocument",
                "collections": collections,
                "count": len(collections),
            }
        finally:
            client.close()
    except Exception as e:
        # Return the error as data so Claude can report it instead of crashing.
        return {"error": f"Could not connect to the database: {e}"}


# ---------------------------------------------------------------------------
# 4. ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # streamable-http transport => served at http://<host>:<port>/mcp
    mcp.run(transport="streamable-http")
