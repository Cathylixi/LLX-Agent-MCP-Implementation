---
name: sas-files
description: List and download the company's SAS data files / SAS datasets / SAS domain files (.sas7bdat) — e.g. dm, ae, cm, vs, lb, mh, ex. This data lives ONLY in cloud storage, never on the local machine.
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
2. If the user wants a specific file, call `get_sas_file_download_url` with
   the exact filename from step 1 (e.g. "dm.sas7bdat") to get a temporary
   (1-hour) direct download link.
3. Present results as a simple list. Do not guess filenames — always confirm
   against the list from step 1 first.
