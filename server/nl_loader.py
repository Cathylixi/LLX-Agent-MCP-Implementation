"""
Loader for natural-language skills (.md files in the skills/ folder).

STEP 1 (current): each .md skill is exposed as an MCP tool. When the employee's
local Claude calls it, the tool RETURNS the natural-language instructions, and
the local Claude carries them out itself.

  - Skills are authored in plain language (like Claude's SKILL.md).
  - They live on the cloud server and are delivered over MCP.
  - NOT confidential yet: the instructions are sent to the local Claude.

STEP 2 (later): swap the tool body so a cloud AI executes the instructions and
returns ONLY the result — then the instructions never leave the server and the
skill becomes confidential. The employee-facing tool (name + description) stays
the same, so nothing changes on the employee side.

Skill file format (frontmatter + body):

    ---
    name: my-skill
    description: one line telling Claude when to use this skill
    ---
    (the natural-language instructions / rules go here)
"""

import glob
import os

_SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")


def _parse_md(path):
    """Return (name, description, body) parsed from a skill .md file."""
    with open(path, encoding="utf-8") as f:
        text = f.read()

    name = os.path.splitext(os.path.basename(path))[0]
    description = ""
    body = text.strip()

    # Parse YAML-ish frontmatter between the first two '---' markers.
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


def _make_skill(name, instructions):
    """Build a no-arg MCP tool function that returns the skill instructions."""

    def skill() -> str:
        print(f"[NL SKILL SERVED] {name}", flush=True)
        # STEP 1: hand the instructions to the local Claude to follow.
        return (
            "Follow these instructions to complete the user's request:\n\n"
            f"{instructions}"
        )

    skill.__name__ = name.replace("-", "_")
    return skill


def load_nl_skills(mcp):
    """Find every .md skill in skills/ and register it as an MCP tool."""
    for path in sorted(glob.glob(os.path.join(_SKILLS_DIR, "*.md"))):
        name, description, body = _parse_md(path)
        mcp.add_tool(_make_skill(name, body), name=name, description=description)
        print(f"[NL SKILL LOADED] {name}", flush=True)
