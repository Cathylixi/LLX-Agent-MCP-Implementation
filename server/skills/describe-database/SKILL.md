---
name: describe-database
description: Explain in plain language what data the company database contains.
---
The user wants to understand what data is available in the company database or
how a specific study document is stored.

For a general database question:
1. Call `db_list_collections` to get the real, live list of collections.
2. Briefly describe only what the returned names establish. Do not invent fields.

For a question about one study document (for example how SPI-611 SAP is stored):
1. Call `db_find_documents` with the requested `study_number` and
   `document_type`. Start with `include_content=false` to inspect the field/type
   structure safely.
2. If the user needs exact stored values, call it again with
   `include_content=true`; responses are bounded by the server.
3. Explain the returned structure faithfully. Do not infer fields that were not
   returned and never substitute a local database.
