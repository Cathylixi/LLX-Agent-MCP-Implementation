"""
scripts/helper.py (example supporting script)

OPTIONAL. In Claude's standard, a skill can bundle scripts that Claude runs.

In THIS server, code that should run on the cloud (and register as an MCP tool)
goes in a *.py file at the skill folder's TOP level (e.g. tools.py), where the
loader imports it. Files inside scripts/ are NOT auto-loaded as tools — treat
them as plain helper scripts referenced from SKILL.md.
"""


def example_helper():
    return "This is just an example helper — replace with real code."
