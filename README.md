# LLX Agent — MCP Skills Library

A confidential "skills library": employees use **Codex** locally, which auto-calls
these skills over MCP. The skill code/data run in the cloud and are **never
downloaded locally**, so employees can use the skills but cannot read them.

> **Full architecture & the 7-phase rollout plan:** see
> [`../workflow/mcp structure.md`](../workflow/mcp%20structure.md). This README is
> the operational guide (how to run, change, redeploy); that doc explains the *why*.

## Status: ✅ Live on Azure (since 2026-06-29)

| | |
|---|---|
| **Endpoint** | `https://llx-mcp.delightfuldesert-f5bbaa56.eastus.azurecontainerapps.io/mcp` |
| **Skills** | each skill is its own file in `server/skills/` (auto-loaded) |
| **Source (public GitHub)** | `Cathylixi/LLX-Agent-MCP-Implementation` |
| **Azure** | RG `LLXSolutions` · app `llx-mcp` · ACR `cafa6fd6c51facr` · env `managedEnvironment-LLXSolutions-b380` (East US) |

## How employees connect (Codex)

Each employee needs **Codex** (≥ 0.144, which can connect to a remote MCP server
directly). Two files go in their `.codex` folder:

- **Windows:** `C:\Users\<username>\.codex\`
- **Mac/Linux:** `~/.codex/`

### File 1 — `config.toml` (connects to the cloud)

Add this block to their Codex config file — it holds only the URL, no skill content:

```toml
[mcp_servers.llx-skills]
url = "https://llx-mcp.delightfuldesert-f5bbaa56.eastus.azurecontainerapps.io/mcp"
startup_timeout_sec = 60
tool_timeout_sec = 120
```

(Copy-paste ready template: [`codex-config.toml`](codex-config.toml).)

> **Why `url` and not a `command`/`npx mcp-remote` bridge:** Codex ≥ 0.144 speaks
> streamable HTTP directly. The npx bridge cold-started slowly and intermittently
> dropped the handshake; the direct `url` is more reliable. The timeouts give the
> cloud container time to wake from idle.

### File 2 — `AGENTS.md` (forces Codex to always use the cloud)

Copy [`AGENTS.md`](AGENTS.md) to `~/.codex/AGENTS.md`. **This file is required.**

Without it, a generic request like "list the database collections" can make Codex
query a *local* database it happens to find nearby, instead of the cloud skills.
`AGENTS.md` is a standing company rule that tells Codex: for any company data/skill
request, always use the `llx-skills` cloud tools — never local files. (Verified:
with the rule in place, even a vague prompt from a folder full of local DB configs
correctly routes to the cloud.)

### Then

Save both files, restart Codex, and just ask naturally — Codex auto-calls the
matching skill in the cloud.

## Skills

Each skill is its own file in `server/skills/`. `server/main.py` auto-loads every
file in that folder at startup, so **adding a skill = drop a new `.py` file in
`server/skills/`** (copy an existing one as a template) — nothing else to edit.

## Project layout

```
server/
  main.py        # entry point — auto-loads every skill (rarely touch)
  app.py         # the shared MCP server instance
  skills/        # ONE FILE PER SKILL  ← add / edit skills here
requirements.txt   # Python dependencies
Dockerfile         # how Azure packages the server
codex-config.toml  # employee client config (points at the cloud endpoint)
AGENTS.md          # employee Codex rule — always use the cloud, never local
```

## Change a skill & redeploy

Editing GitHub does **NOT** auto-update Azure. The full loop:

1. Add or edit a file in `server/skills/`, commit, and push to GitHub.
2. Open **Azure Cloud Shell**: go to <https://portal.azure.com>, click the `>_`
   icon in the top bar, choose **Bash**.
3. Run these two commands (no local Docker / CLI needed):

```bash
az acr build --registry cafa6fd6c51facr --image llx-mcp:v2 https://github.com/Cathylixi/LLX-Agent-MCP-Implementation.git
az containerapp update --name llx-mcp --resource-group LLXSolutions --image cafa6fd6c51facr.azurecr.io/llx-mcp:v2
```

> **Why `update` (not `up`):** `update` only swaps the image and **keeps the
> existing ingress and secrets/env vars** (like the database `MONGO_URI`). Use it
> for all redeploys after the first one.
>
> **Why manual:** auto-deploy needs a "service principal", which the org account
> `ai@llxsolutions.com` isn't allowed to create — so we build & deploy by hand.
>
> **Tag note:** we always reuse the same tag (currently `:v2`), so each deploy
> overwrites the last (no version history). Bump to `:v3`, `:v4`, … in both
> commands if you want rollback points.

## Connecting a database (Azure Cosmos DB)

The server can query the company database server-side and return only the results,
so employees never see the database address or password. Connected since 2026-06-29.

- **Database:** Azure Cosmos DB (MongoDB API), database `llxdocument`,
  cluster `llx-solutions-msft5`.
- **Driver:** `pymongo[srv]` in `requirements.txt` (the `+srv` URI needs dnspython).
- **Skill:** the database skill is a file in `server/skills/`. It reads the
  connection string from the `MONGO_URI` env var and queries the DB server-side.
- **Full write-up:** [`../workflow/connecting database.md`](../workflow/connecting%20database.md).

**Golden rules:** (1) the connection string is a **secret** — it lives in an
encrypted Azure secret, never in the code/GitHub; (2) expose **specific, read-only
query skills**, never a generic "run any SQL" skill.

### How it was deployed (run in Azure Cloud Shell)

```bash
# 1. build the image (includes pymongo[srv])
az acr build --registry cafa6fd6c51facr --image llx-mcp:v2 https://github.com/Cathylixi/LLX-Agent-MCP-Implementation.git

# 2. store the connection string as an encrypted secret
#    (copy the value from AI-for-Word/backend/.env line 8; keep the single quotes)
az containerapp secret set --name llx-mcp --resource-group LLXSolutions --secrets mongo-uri='<CONNECTION_STRING>'

# 3. deploy the image AND wire the secret to the MONGO_URI env var
az containerapp update --name llx-mcp --resource-group LLXSolutions --image cafa6fd6c51facr.azurecr.io/llx-mcp:v2 --set-env-vars MONGO_URI=secretref:mongo-uri
```

> To change the connection string later, re-run step 2 only (then restart a
> revision). To add new DB query skills, edit `main.py` and redeploy (steps 1 + 3).
>
> **If the connection times out:** open the Cosmos DB in the portal → Networking →
> allow access from Azure services / public Azure datacenters.

## Verify it's working

After deploying (or any time), check the live server with a quick MCP client:

```bash
pip install mcp        # once
python - <<'PY'
import asyncio
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
URL = "https://llx-mcp.delightfuldesert-f5bbaa56.eastus.azurecontainerapps.io/mcp"
async def main():
    async with streamablehttp_client(URL) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            print([t.name for t in (await s.list_tools()).tools])
            print((await s.call_tool("db_list_collections", {})).content[0].text)
asyncio.run(main())
PY
```

Expect it to print the available tool names and the database collections. (Or in
Codex with the `config.toml` above, just ask it to list the collections.)

## ⚠️ Security gap (fix before real data)

The endpoint has **no authentication** — anyone with the URL can call it.

- ✅ Outsiders **cannot read** the skill code/prompts (those stay server-side).
- ⚠️ But they **can call** the skills, **get the results**, see tool names, and burn cost.

Fine for the fake-data demo. Once skills return real confidential data, add **token
auth** so only employees can call them.

## Local development (optional)

To test changes on your own machine before deploying:

```bash
pip install -r requirements.txt
python server/main.py          # serves at http://127.0.0.1:8000/mcp
```

Temporarily point your Codex `config.toml` at `http://127.0.0.1:8000/mcp` (same
block, just swap the URL), open Codex, and try a skill. Restart the server after
each code change (a stale server keeps the old port 8000 and your new skill won't
show up).
