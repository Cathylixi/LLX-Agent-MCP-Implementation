# MCP Implementation (Phase 1 — local test)

A minimal MCP server (the "skills library") with one sample skill `search_news`.
Goal: prove that local Claude Code can auto-call a skill over MCP.

## Folder

```
mcp implementation/
├─ server/
│  └─ main.py          # MCP server + the search_news skill
├─ requirements.txt    # dependency: mcp
├─ .mcp.json           # tells Claude Code to connect to the local server
└─ README.md           # this file
```

## How to run

1. (Recommended) create a virtual environment:
   ```
   python -m venv .venv
   .venv\Scripts\activate          # Windows PowerShell
   ```

2. Install the dependency:
   ```
   pip install -r requirements.txt
   ```

3. Start the server (leave this terminal running):
   ```
   python server/main.py
   ```
   It serves at: `http://127.0.0.1:8000/mcp`

4. Open Claude Code **in this folder** (`mcp implementation`) so it reads `.mcp.json`.
   Approve the new MCP server if prompted. Check it connected with `/mcp`.

## How to verify success

In Claude Code, type:

> find today's news about AI

Claude should automatically call the `search_news` skill and reply with:

> Today's news about 'AI': [demo result] The LLX Agent MCP server is working!

✅ If you see that, the full chain works:
local Claude → auto MCP call → skill runs → returns result.

## What changes when we move to the cloud

Nothing in the skill logic. We deploy `server/main.py` to Azure Container Apps,
and the only edit on the employee side is the `url` in `.mcp.json`:

```
"url": "https://<your-azure-app>.azurecontainerapps.io/mcp"
```

(plus an auth token header, added in the security phase).
