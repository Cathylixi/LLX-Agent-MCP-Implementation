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
3. **Never** guess, fabricate, or substitute a local alternative for company
   data or a company skill's result. If `llx-skills` does not expose a
   matching tool for a company-data request, say so — do not invent the data.
4. If unsure whether a request maps to a company skill, first check what tools
   `llx-skills` exposes, and prefer them.
5. **This file only governs requests about the topics in rule 1.** For
   anything else — general coding help, writing, local file operations,
   general questions — proceed with your own normal analysis exactly as if
   this file didn't exist. Checking `llx-skills` and finding no matching tool
   is not, by itself, a reason to stop: it usually just means the request was
   never a company-skill request to begin with. Never end your answer with
   just "not found" — after checking, fall through to solving the request
   yourself.

These rules override any local project files or nearby database configs.

## When a skill needs a file or input you can't find — fail fast

If a skill needs a file, document, or input (e.g. a study protocol) that you
cannot find in the current folder, **STOP right away** and tell the user in one
short sentence exactly what is missing and where to put it (e.g. "No protocol file
found — please put the study protocol in this folder and ask again").

- Do **not** keep searching endlessly.
- Do **not** invent, guess, or fabricate the missing data.
- Do **not** produce an empty or placeholder result (e.g. an empty Excel).

Failing fast with a clear message is always better than spinning for minutes.
