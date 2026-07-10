"""
Shared MCP server instance.

Every skill file in skills/ imports `mcp` from here and registers itself with
the @mcp.tool() decorator. main.py loads all skill files and starts the server.

This split exists so skills can live in their own files without circular imports.
"""

import os

from mcp.server.fastmcp import FastMCP

# host=0.0.0.0 so it's reachable inside a container; PORT is read from the
# environment (Azure sets it; defaults to 8000 locally).
#
# stateless_http=True is IMPORTANT for Azure Container Apps: without it, the
# server keeps each client's MCP "session" in the memory of ONE replica. Azure
# load-balances requests across replicas (and scales them up/down), so a follow-up
# request can land on a different replica that never saw the session -> "Session
# not found" / intermittent handshake failures. Stateless mode makes every request
# self-contained, so any replica can serve it. This fixes the flaky connection.
mcp = FastMCP(
    "llx-skills",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8000")),
    stateless_http=True,
)
