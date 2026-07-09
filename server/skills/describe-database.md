---
name: describe-database
description: Explain in plain language what data the company database contains.
---
The user wants to understand what data is available in the company database.

Do this:
1. Call the `db_list_collections` tool to get the real, live list of collections.
2. For each collection returned, write one short, friendly sentence explaining
   what it most likely contains.
3. Present the result as a simple bulleted list.
4. End by asking whether they want to look into any specific collection.
