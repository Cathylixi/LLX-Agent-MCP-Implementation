---
name: sas-files
description: List, download, and read the contents of the company's cloud files — SAS data files / SAS datasets / SAS domain files (.sas7bdat, e.g. dm, ae, cm, vs, lb, mh, ex) AND documents like CRFs (.pdf, e.g. acrf.pdf). Files are organized by study in subfolders (e.g. SPI-611/). This data lives ONLY in cloud storage, never on the local machine.
---
The user wants to see or fetch a file from cloud storage: either a raw SAS
domain dataset (dm, ae, cm, vs, lb1, lb2, mh, ex, etc — de-identified
clinical trial data, stored as-is) or a document like a CRF (.pdf). Files
live in subfolders per study (e.g. `SPI-611/dm.sas7bdat`, `SPI-611/acrf.pdf`)
as well as some ungrouped files at the top level.

These files are NOT on the local machine and never will be — they live only
in Azure Blob Storage. If a request mentions "SAS files", "SAS data(sets)",
"SAS domain files", `.sas7bdat`, names of specific domains (dm/ae/cm/vs/lb/
mh/ex/etc), "CRF", or a study name/number, that means THIS skill — do not
search local folders first.

Do this:
1. Call `list_sas_files` to get the real, live list of files (all types,
   across all study subfolders) and their sizes.
2. For a `.sas7bdat` file — if the user wants to SEE what's inside (variable
   names/labels/types, a data dictionary, row counts, sample or specific
   rows, "what does dm look like"), call `describe_sas_file` with the exact
   filename from step 1. `variables`/`row_count`/`column_count` in the
   response always describe the WHOLE file (never truncated). Row data is
   paginated (`rows`, `start_row`) — to see more than the first page, call
   again with `start_row` advanced past what you've already seen, and keep
   going until you've covered `row_count` rows. Never guess or fabricate what
   a domain "probably" contains — everything must come from this tool.
3. For a `.pdf` file (e.g. a CRF) — if the user wants to read its contents,
   call `read_pdf_text` with the exact filename from step 1. It returns text
   from every page by default; if the file is too large for one response, it
   returns a `pages_returned` range short of `total_pages` — call again with
   the `pages` parameter (e.g. "21-40") to keep reading the rest.
4. If the user wants the actual FILE (to download it themselves), call
   `get_sas_file_download_url` with the exact filename from step 1 to get a
   temporary (1-hour) direct download link — works for any file type.
5. Always confirm filenames against the list from step 1 first — never guess
   a filename.
