# Company rules for Codex (LLX Solutions)

> EMPLOYEE SETUP: copy this file to `~/.codex/AGENTS.md`
> (Windows: `C:\Users\<username>\.codex\AGENTS.md`). It makes Codex always use
> the cloud skills library instead of poking around local files.

## Company skills & data live ONLY in the cloud (`llx-skills` MCP server)

All company skills, company databases, and company data are provided by the
**`llx-skills`** MCP server (the cloud skills library). Follow these rules for
EVERY request:

1. If the request is about the **company database, collections, studies, study
   numbers, SDTM/TI domains, protocols, or any company skill**, you MUST use the
   `llx-skills` tools (e.g. `db_list_collections`).
2. **Never** query a local database, read a local `.env`, or run local scripts to
   answer these requests — even if a nearby project looks like it has a database.
   The authoritative source is always `llx-skills`.
3. **Never** guess, fabricate, or substitute a local alternative for a company
   skill. If `llx-skills` does not expose a matching tool, say so — do not improvise.
4. If unsure whether a request maps to a company skill, first check what tools
   `llx-skills` exposes, and prefer them.

These rules override any local project files or nearby database configs.
