---
name: sas-files
description: List, download, and preview the contents of the company's SAS data files / SAS datasets / SAS domain files (.sas7bdat) — e.g. dm, ae, cm, vs, lb, mh, ex. This data lives ONLY in cloud storage, never on the local machine.
---
The user wants to see or fetch one of the raw SAS domain datasets (files like
dm, ae, cm, vs, lb1, lb2, mh, ex, etc — de-identified clinical trial data,
stored as-is, one file per domain).

These files are NOT on the local machine and never will be — they live only
in Azure Blob Storage. If a request mentions "SAS files", "SAS data(sets)",
"SAS domain files", `.sas7bdat`, or names of specific domains (dm/ae/cm/vs/
lb/mh/ex/etc), that means THIS skill — do not search local folders first.

Do this:
1. Call `list_sas_files` to get the real, live list of files and their sizes.
2. If the user wants to SEE what's inside a file (columns, sample rows, "what
   does dm look like"), call `preview_sas_file` with the exact filename from
   step 1 and how many rows they want (default 20, max 500). This reads the
   file on the server and returns real column names + real rows — never
   guess or fabricate what a domain "probably" contains.
3. If the user wants the actual FILE (to download it themselves), call
   `get_sas_file_download_url` with the exact filename from step 1 to get a
   temporary (1-hour) direct download link.
4. Always confirm filenames against the list from step 1 first — never guess
   a filename.
