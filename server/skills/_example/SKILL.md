---
name: example-skill
description: TEMPLATE showing the skill folder layout (follows the Claude Agent Skills standard). This is a reference only — copy this folder to create a real skill. Because the folder name starts with "_", the server ignores it.
---

# Skill folder & subfolder layout (Claude Agent Skills standard)

Every skill is a **directory**. `SKILL.md` is the **required** entry point. This
matches Claude's original Skills structure (the open Agent Skills standard).

## 1. One skill = one folder

```
skills/
└── <skill-name>/          # the folder name is the skill's name/command
    ├── SKILL.md           # REQUIRED — frontmatter + instructions
    ├── reference.md       # optional — detailed docs, loaded only when needed
    ├── examples.md        # optional — example outputs / expected format
    └── scripts/           # optional — code the skill can use
        └── helper.py
```

- `SKILL.md` is required; everything else is optional.
- The **folder name** becomes the skill name (Claude convention). The frontmatter
  `name` is just the display label and defaults to the folder name.
- Keep `SKILL.md` short (under ~500 lines). Move large reference material into
  separate files and point to them from `SKILL.md`, e.g.
  `For full rules, see [reference.md](reference.md).`

## 2. SKILL.md = frontmatter + body

```
---
name: my-skill
description: What it does AND when to use it (this is what Claude reads to decide)
---

(the natural-language instructions Claude follows go here)
```

### Frontmatter fields (all optional; only `description` recommended)

| Field | Meaning |
|---|---|
| `name` | Display name. Defaults to the folder name. |
| `description` | What it does + when to use it. Claude uses this to auto-trigger. Truncated at 1,536 chars. |
| `when_to_use` | Extra trigger phrases / example requests (appended to description). |
| `argument-hint` | Autocomplete hint, e.g. `[protocol-file]`. |
| `arguments` | Named positional args for `$name` substitution in the body. |
| `disable-model-invocation` | `true` = only a person can invoke it (Claude won't auto-run it). |
| `user-invocable` | `false` = only Claude can invoke it (hidden from the `/` menu). |
| `allowed-tools` | Tools pre-approved while this skill is active. |
| `disallowed-tools` | Tools removed while this skill is active. |
| `model` / `effort` | Override model / effort while active. |
| `context: fork` / `agent` | Run the skill in a forked subagent. |
| `paths` | Glob patterns that limit when the skill auto-loads. |

### String substitutions usable in the body

`$ARGUMENTS`, `$0`/`$1`…, `$name`, `${CLAUDE_SKILL_DIR}`, `${CLAUDE_PROJECT_DIR}`,
`${CLAUDE_SESSION_ID}`, `${CLAUDE_EFFORT}`.

## 3. How THIS server reads a skill folder

Our cloud MCP server maps the same folder layout like this:

- **`SKILL.md`** → served over MCP as a **natural-language skill**: when Claude
  calls it, the instructions are handed to the employee's local Claude to follow.
- **any `*.py` in the folder** → loaded on the **SERVER**; functions marked
  `@mcp.tool()` become **code tools** that run in the cloud (so secrets like the
  DB connection string never leave the server). A `SKILL.md` can tell Claude to
  call these tools by name.

So one folder can hold **natural language** ("how to do it") **and code** ("the
parts that need a database or private resource"), for example:

```
skills/
└── database/
    ├── SKILL.md           # natural language: how to describe the database
    └── tools.py           # code: db_list_collections (runs on the server)
```

## 4. To create a real skill

1. Make a new folder: `skills/<your-skill-name>/`
2. Add `SKILL.md` with a `description` and your instructions.
3. (Optional) add `*.py` for code that must run on the server, and/or
   `reference.md`, `examples.md`, `scripts/` for supporting material.
4. Deploy (rebuild + update the container). It is picked up automatically.
