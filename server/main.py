"""
LLX Agent — MCP server entry point.

Skills live in the skills/ folder, ONE FOLDER PER SKILL (like Claude's Skills):

    skills/<skill-name>/SKILL.md   natural-language instructions
    skills/<skill-name>/*.py       optional code the skill uses (runs on server)

To add a skill: make a new folder under skills/ with a SKILL.md (and optional
.py code). It is picked up automatically — no edits needed here.

Run locally:
    pip install -r ../requirements.txt
    python main.py            # serves at http://127.0.0.1:8000/mcp
"""

from app import mcp
from skill_loader import load_skills

# Load every skill folder under skills/ (natural-language SKILL.md + any code).
load_skills(mcp)

if __name__ == "__main__":
    # streamable-http transport => served at http://<host>:<port>/mcp
    mcp.run(transport="streamable-http")
