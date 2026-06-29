"""
LLX Agent — MCP server entry point.

This file is tiny on purpose. The actual skills live in the skills/ folder,
one file per skill. This entry point:
  1. gets the shared MCP server (from app.py),
  2. auto-discovers and loads EVERY skill file in skills/,
  3. starts the server.

To add a skill: drop a new .py file in skills/ (copy an existing one). It is
picked up automatically — no edits needed here.

Run locally:
    pip install -r ../requirements.txt
    python main.py            # serves at http://127.0.0.1:8000/mcp
"""

import importlib
import pkgutil

from app import mcp
import skills

# Auto-discover: import every module in the skills/ package so each file's
# @mcp.tool() decorator runs and registers its skill with the server.
for _module in pkgutil.iter_modules(skills.__path__):
    importlib.import_module(f"skills.{_module.name}")

if __name__ == "__main__":
    # streamable-http transport => served at http://<host>:<port>/mcp
    mcp.run(transport="streamable-http")
