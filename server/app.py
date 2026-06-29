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
mcp = FastMCP(
    "llx-skills",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", "8000")),
)
