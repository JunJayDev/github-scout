#!/usr/bin/env python3
"""Build cloud/github-scout.md: the six skills as one file for chats without a command line.

The skills are the source; this file is generated from them, so the two never disagree.
`--check` exits 1 when the committed file is out of date (CI runs it).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "cloud" / "github-scout.md"
PARTS = [
    "skills/github-scout/SKILL.md",
    "skills/github-scout-plan/SKILL.md",
    "skills/github-scout-search/SKILL.md",
    "skills/github-scout-triage/SKILL.md",
    "skills/github-scout-dig/SKILL.md",
    "skills/github-scout-brief/SKILL.md",
    "skills/github-scout/references/report-format.md",
    "skills/github-scout/references/evaluation.md",
]

PREAMBLE = """# github-scout, for a chat with web search

You are running github-scout in a chat (ChatGPT, Claude on the web, or similar). There is no
command line here. In every stage below, follow the part titled "Without the command line" and
skip the commands.

- The user's goal is in their message. If there is none, ask what they want to achieve in which
  project, and wait.
- If they attached their project (a zip or files), read it first: it is "our project" in stage 1.
  Otherwise use what they say exists today.
- Run the five stages without stopping, unless the user asked to confirm the directions first.
- Search with every lens that works here (stage 2 starts by checking which pages open) and log
  every search in the report, so a missed repo can be traced to the search that should have found it.
- Write everything into one report file in the format given near the end, in the user's language,
  and offer it for download.
- Open every repository page you list. Never invent a repository, a star count or a date.
- Skip the commands (`github-scout ...`, `scripts/report-problem.sh`); there is no registry here.
  Write anything in these instructions you could not follow into the report's last section.

Generated from the skills in this repository by tools/build-cloud.py; edit the skills, not this file.
"""


def body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)   # drop frontmatter
    text = text.replace("../github-scout/references/", "").replace("references/", "")
    out, fenced = [], False
    for line in text.strip().splitlines():                       # nest headings one level down,
        if line.startswith("```"):                               # but never inside code blocks:
            fenced = not fenced                                  # the report template must stay as written
        out.append("#" + line if line.startswith("#") and not fenced else line)
    return "\n".join(out)


def build() -> str:
    out = [PREAMBLE.strip(), ""]
    for rel in PARTS:
        out += ["---", "", body(ROOT / rel), ""]
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str]) -> int:
    text = build()
    if "--check" in argv:
        if not OUT.is_file() or OUT.read_text(encoding="utf-8") != text:
            print(f"{OUT.relative_to(ROOT)} is out of date: run python tools/build-cloud.py", file=sys.stderr)
            return 1
        return 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} ({len(text):,} characters)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
