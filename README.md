# LLX Agent — MCP Skills Library

A confidential "skills library": employees use local Claude, which auto-calls these
skills over MCP. The skill code/data run in the cloud and are **never downloaded
locally**, so employees can use the skills but cannot read them.

> **Full architecture & the 7-phase rollout plan:** see
> [`../workflow/mcp structure.md`](../workflow/mcp%20structure.md). This README is
> the operational guide (how to run, change, redeploy); that doc explains the *why*.

## Status: ✅ Live on Azure (since 2026-06-29)

| | |
|---|---|
| **Endpoint** | `https://llx-mcp.delightfuldesert-f5bbaa56.eastus.azurecontainerapps.io/mcp` |
| **Skills** | `search_news`, `get_project_status` (demo) · `db_list_collections` (live Cosmos DB) |
| **Source (public GitHub)** | `Cathylixi/LLX-Agent-MCP-Implementation` |
| **Azure** | RG `LLXSolutions` · app `llx-mcp` · ACR `cafa6fd6c51facr` · env `managedEnvironment-LLXSolutions-b380` (East US) |

## How employees connect

Put this `.mcp.json` in the folder where they open Claude Code. It holds only the
URL — no skill content:

```json
{ "mcpServers": { "llx-skills": {
  "type": "http",
  "url": "https://llx-mcp.delightfuldesert-f5bbaa56.eastus.azurecontainerapps.io/mcp"
} } }
```

Then just ask naturally and Claude auto-calls the matching skill.

## The skills

| Skill | Ask it like | Input | Returns |
|---|---|---|---|
| `get_project_status` | "what's the status of project LLX-204?" | `project_code` (e.g. `LLX-204`) | name, status, owner, deadline, progress % |
| `search_news` | "find today's news about AI" | `keyword` | a news string (demo stub only) |

> Demo data lives in `server/main.py`. `get_project_status` knows `LLX-204` and
> `LLX-117`; anything else returns "Not Found". Real logic/data replaces these later.
>
> Note: `search_news` overlaps with Claude's built-in web search, so Claude may
> prefer the built-in one. Internal skills like `get_project_status` (no built-in
> equivalent) are always auto-selected — that's the normal case for real skills.

## Project layout

```
server/main.py      # the MCP server + skill definitions  (edit skills here)
requirements.txt    # dependency: mcp
Dockerfile          # how Azure packages the server
.mcp.json           # client config (points at the cloud endpoint)
```

## Change a skill & redeploy

Editing GitHub does **NOT** auto-update Azure. The full loop:

1. Edit `server/main.py`, commit, and push to GitHub.
2. Open **Azure Cloud Shell**: go to <https://portal.azure.com>, click the `>_`
   icon in the top bar, choose **Bash**.
3. Run these two commands (no local Docker / CLI needed):

```bash
az acr build --registry cafa6fd6c51facr --image llx-mcp:v1 https://github.com/Cathylixi/LLX-Agent-MCP-Implementation.git
az containerapp up --name llx-mcp --resource-group LLXSolutions --image cafa6fd6c51facr.azurecr.io/llx-mcp:v1 --ingress external --target-port 8000
```

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
- **Skill:** `db_list_collections` in `server/main.py` (section 3). It reads the
  connection string from the `MONGO_URI` env var and lists the collections.
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
            print((await s.call_tool("get_project_status", {"project_code": "LLX-204"})).content[0].text)
asyncio.run(main())
PY
```

Expect it to print the tool names and the LLX-204 status. (Or in Claude Code with
the `.mcp.json` above, just ask for a project's status.)

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

Temporarily point `.mcp.json` at `http://127.0.0.1:8000/mcp`, open Claude Code in
this folder, and try a skill. Restart the server after each code change (a stale
server keeps the old port 8000 and your new skill won't show up).
