"""
Skill loader — Claude-style, ONE FOLDER PER SKILL.

Each subfolder of skills/ is a skill bundle, like Claude's Skills:

    skills/<skill-name>/
        SKILL.md      natural-language instructions (frontmatter: name, description)
        *.py          optional code the skill uses (runs on the server)

- SKILL.md is registered as an MCP tool that serves its instructions to the
  local Claude. (STEP 1: not confidential yet — instructions go to the client.)
- Any .py file self-registers its @mcp.tool() code tools. These run on the
  SERVER, so secrets (like the DB key) never leave the cloud. A SKILL.md can
  tell Claude to call these code tools by name.
"""

import glob
import importlib.util
import os
import sys

_SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")


def _parse_skill_md(path):
    """Return (name, description, body) from a SKILL.md file."""
    with open(path, encoding="utf-8") as f:
        text = f.read()

    name = os.path.basename(os.path.dirname(path))  # default to folder name
    description = ""
    body = text.strip()

    if text.lstrip().startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            front, body = parts[1], parts[2].strip()
            for line in front.splitlines():
                if ":" in line:
                    key, _, val = line.partition(":")
                    key = key.strip().lower()
                    val = val.strip()
                    if key == "name" and val:
                        name = val
                    # accept the common misspelling "desciption" too
                    elif key in ("description", "desciption") and val:
                        description = val

    return name, description or f"Skill: {name}", body


def _make_nl_tool(name, instructions):
    """A no-arg MCP tool that hands the skill instructions to the local Claude."""

    def skill() -> str:
        print(f"[NL SKILL SERVED] {name}", flush=True)
        return (
            "Follow these instructions to complete the user's request:\n\n"
            f"{instructions}"
        )

    skill.__name__ = name.replace("-", "_")
    return skill


def _load_code_file(path):
    """Import a skill's .py file so its @mcp.tool() code tools register."""
    mod_name = "skillcode_" + os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)


def load_skills(mcp):
    """Walk skills/, and for each skill folder load its code + SKILL.md."""
    if not os.path.isdir(_SKILLS_DIR):
        return

    for entry in sorted(os.listdir(_SKILLS_DIR)):
        folder = os.path.join(_SKILLS_DIR, entry)
        if not os.path.isdir(folder) or entry.startswith(("_", ".")):
            continue

        # Let this skill's own files import each other as plain sibling
        # modules (e.g. `import sdtmig_metadata` from another file in the same
        # folder). Appended (not inserted at position 0) so it can't shadow
        # stdlib or another skill's module of the same name.
        if folder not in sys.path:
            sys.path.append(folder)

        # 1. load any code tools in this skill folder (they self-register)
        for py in sorted(glob.glob(os.path.join(folder, "*.py"))):
            stem = os.path.splitext(os.path.basename(py))[0]
            if stem in sys.modules:
                # Already imported as a side effect of a sibling file's own
                # `import` statement (e.g. the skill's main module importing
                # its helper modules) - loading it again would just re-parse
                # the same file for no benefit.
                continue
            _load_code_file(py)

        # 2. load SKILL.md as a natural-language skill
        md = os.path.join(folder, "SKILL.md")
        if os.path.exists(md):
            name, description, body = _parse_skill_md(md)
            mcp.add_tool(_make_nl_tool(name, body), name=name, description=description)
            print(f"[SKILL LOADED] {entry}/ -> {name}", flush=True)
