"""Skill: db_list_collections — connects to the real Cosmos DB."""

import os

from app import mcp


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
        # Import here so the server still starts even if pymongo isn't installed
        # locally; only this skill needs it.
        from pymongo import MongoClient

        # 8s timeout so a network problem fails fast instead of hanging.
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
        return {"error": f"Could not connect to the database: {e}"}
