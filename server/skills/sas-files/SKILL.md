---
name: sas-files
description: List and download the raw SAS clinical trial domain datasets (.sas7bdat files) stored in Azure Blob Storage.
---
The user wants to see or fetch one of the raw SAS domain datasets (files like
dm, ae, cm, vs, lb1, lb2, mh, ex, etc — de-identified clinical trial data,
stored as-is, one file per domain).

Do this:
1. Call `list_sas_files` to get the real, live list of files and their sizes.
2. If the user wants a specific file, call `get_sas_file_download_url` with
   the exact filename from step 1 (e.g. "dm.sas7bdat") to get a temporary
   (1-hour) direct download link.
3. Present results as a simple list. Do not guess filenames — always confirm
   against the list from step 1 first.
