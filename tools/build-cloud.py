#!/usr/bin/env python3
"""Build cloud/github-scout.md: stages 1 to 4 (plan, search, triage, brief), as one file for chats without a command line.

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
    "skills/github-scout-brief/SKILL.md",
    "skills/github-scout/references/report-format.md",
    "skills/github-scout/references/evaluation.md",
]

PREAMBLE = """# github-scout, for a chat with web search

You are running github-scout in a chat (ChatGPT, Claude on the web, or similar). There is no
command line here. In every stage below, follow the part titled "Without the command line" and
skip the commands.

- **No licences.** We look for reference projects to follow. Do not research, mention or tabulate
  licences, usage rights, stock-media terms, model-weight terms or prices: no licence column,
  no licence notes, no licence or rights section. A report that has them has failed this rule.
- **Keep the report's sections, numbers and order exactly as in the format near the end,**
  starting with section 1, the directions table: the local agent runs its own searches on it.
- The user's goal is in their message. If there is none, ask what they want to achieve in which
  project, and wait.
- If their project is on GitHub and a GitHub connector is connected, or they attached it (a zip
  or files), read it first: it is "our project" in stage 1. Otherwise use what they say exists
  today.
- Run the four stages without stopping, unless the user asked to confirm the directions first.
  They end with the report: what exists, the two or three to try first and how.
- You have web search and maybe a GitHub connector, but no browser. Stage 2 starts by checking
  what they can do; search with every lens through them, and log every search in the report, so a
  missed repo can be traced to the search that should have found it. A search engine misses many
  new repos; the local agent covers them afterwards with GitHub's own search on your directions,
  so write the directions with care.
- Write everything into one report file in the format given near the end, in the user's language,
  and offer it for download.
- List only repositories you have seen (their page, the connector, or a search result naming
  them). Never invent a repository, a star count or a date.
- **You do not try repos or choose one.** Judge each by its verifiable effect (a live site,
  package downloads, screenshots, videos, posts outside the repo) and its stars, and write under
  Try first how the coding agent should try each. Back in the project, and only when the user
  asks, that agent tries them, chooses one to follow and brings it in.
- Without a project, the stage is "idea".
- If the user attaches a candidate table from a local `github-scout scan`, those are the
  candidates: skip the search and start at triage (stage 3).
- Skip the commands (`github-scout ...`, `scripts/report-problem.sh`); there is no registry here.
  Write anything in these instructions you could not follow into the report's last section.

Generated from the skills in this repository by tools/build-cloud.py; edit the skills, not this file.
"""

# Stages 5 and 6 (github-scout-dig, github-scout-adopt) run code and change the project, so only the
# project's own coding agent runs them, never a chat. `quick` needs the command line. Blocks that name them (a
# paragraph, a list item, a table row) are left out of this file; the brief stage says in one plain sentence who does.
LOCAL_ONLY = re.compile(r"github-scout[- ](?:adopt|dig)|`adopt |github-scout quick|`quick ")
BLOCK_START = re.compile(r"#|\||\s*(?:[-*+]|\d+\.)\s")


def drop_local_only(lines: list[str]) -> list[str]:
    out: list[str] = []
    block: list[str] = []
    fenced = dropped = False

    def flush():
        nonlocal dropped
        if block:
            dropped = bool(LOCAL_ONLY.search("\n".join(block)))
            if not dropped:
                out.extend(block)
            block.clear()

    for line in lines:
        if line.startswith("```") or fenced:
            flush()
            fenced ^= line.startswith("```")
            out.append(line)
            dropped = False
        elif not line.strip():
            flush()
            if not (dropped and out and not out[-1].strip()):    # no double blank line where a block went
                out.append(line)
            dropped = False
        elif BLOCK_START.match(line) or not block:
            flush()
            block.append(line)
        else:
            block.append(line)                                   # continues a paragraph or a list item
    flush()
    while out and not out[-1].strip():
        out.pop()
    return out


def body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)   # drop frontmatter
    text = re.sub(r"\n## Improve this skill\n.*?(?=\n## |\Z)", "\n", text, flags=re.S)   # a chat cannot open a pull request
    text = text.replace("../github-scout/references/", "").replace("references/", "")
    out, fenced = [], False
    for line in drop_local_only(text.strip().splitlines()):     # nest headings one level down,
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
