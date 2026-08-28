# Company rules for Codex (LLX Solutions)

> EMPLOYEE SETUP: copy this file to `~/.codex/AGENTS.md`
> (Windows: `C:\Users\<username>\.codex\AGENTS.md`). It makes Codex always use
> the cloud skills library instead of poking around local files.

## Company skills & data live ONLY in the cloud (`llx-skills` MCP server)

All company skills, company databases, and company data are provided by the
**`llx-skills`** MCP server (the cloud skills library). Follow these rules for
EVERY request:

1. If a request needs company data — the company database, collections,
   studies, study numbers, SDTM/TI domains, protocols, or anything else
   `llx-skills` provides — **the data itself** must come from `llx-skills`
   tools (e.g. `db_list_collections`, `list_sas_files`, `describe_sas_file`,
   `read_pdf_text`, `get_sas_file_download_url`). This requirement covers
   only *how you source the data*. Once you have it — SAS rows, CRF text,
   database results, anything `llx-skills` returned — reasoning about it,
   transforming it, summarizing it, or writing code against it is ordinary
   agent work: use your full normal capability, exactly as you would with
   any other data already in front of you. `llx-skills` having no tool for a
   specific analysis is never a reason to stop; it only means that
   particular analysis step was never `llx-skills`'s job to begin with.
2. **Never** query a local database, read a local `.env`, run local scripts, or
   search the local filesystem to source this data — even if a nearby
   project looks like it has a database. The authoritative source is always
   `llx-skills`.
3. **Never** guess, fabricate, or substitute a local alternative for company
   data or a company skill's result. If `llx-skills` does not expose a
   matching tool for *sourcing* a piece of company data, say so — do not
   invent the data.
4. If unsure whether a request needs company data, first check what tools
   `llx-skills` exposes, and prefer them.
5. **This file only governs requests that need company data (rule 1).** For
   anything else — general coding help, writing, local file operations,
   general questions — proceed with your own normal analysis exactly as if
   this file didn't exist. Checking `llx-skills` and finding no matching tool
   is not, by itself, a reason to stop: it usually just means the request was
   never a company-data request to begin with. Never end your answer with
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
