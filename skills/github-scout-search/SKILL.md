---
name: github-scout-search
description: Search GitHub along planned directions in English and Chinese; drop lures, farmed installs and dead repos.
license: MIT
---

# GitHub scout: search

Stage 2 of `github-scout`. The aim is not to miss an important reference: search every
direction, in both languages, in several ways.

## Input

The directions from `github-scout-plan`. Without directions, run that stage first.

## Rules

- **Maintenance:** no push in 3 months ranks far down, 6 months is set aside, 12 months is dropped.
- **Exclude lures:** game cheats, cracks, key generators, "Ultimate Trainer 2026" and the like.
  They are bait, often malware. Never download them.
- **Exclude farmed installs:** a skill directory count far beyond the repo's stars (for example
  two million installs on a repo with three stars, often a copy of a famous pack).
- **Read the repo's own page** before you list it. Record its stars and last commit as shown there.
- A repo describes what it makes, not every use people found for it. So also look at what is
  new and growing fast in the form you need, even when no search word matches it.

## With the command line

```bash
github-scout scan <project>/<question>                  # about 140 searches, 5 minutes
```

- **What `scan` searches, all merged into one ranked table:**
  - every entity and mechanism, alone and in pairs;
  - GitHub topics;
  - the last 12 months;
  - SKILL.md files;
  - skills.sh, the MCP registry, npm;
  - a rising list: repos new in the last two months and growing fast, found without words.
- **Ranking:** relevance first, then young and moving, stars last.
- **Left out and counted in the header:** lures and farmed installs.
- **Widen with what the API cannot see:**
  - Do one pass of web search per direction, in English and Chinese: `site:github.com <entity> <mechanism>`.
  - Include Chinese communities (掘金, 知乎, 少数派, V2EX) and any links the user shared.
  - Feed what you find back in: `github-scout scan <q> --add <file|url|text> --note "<where from>"`.
  - Expand a relevant awesome list: `github-scout scan <q> --expand <owner/list>`.

## Without the command line (cloud chat)

For every direction, in English and in Chinese:

1. Search the web: `site:github.com <entity> <mechanism>`, `site:github.com <entity> skill OR cli OR mcp`.
2. Open GitHub topic pages sorted by recent updates: `https://github.com/topics/<topic>?o=desc&s=updated`.
3. For skills, search `https://skills.sh`; distrust install counts far beyond the stars.
4. Look for recent posts and articles that link GitHub projects for this need.

Open each candidate's page, apply the rules above, and write section 2 of the report: one row per
repo, with these columns:

- repo URL
- kind
- direction
- language of the project (en or zh)
- why it may help
- last commit
- stars
- found by

Under the table, write:

- how many searches each direction got in each language;
- which directions found nothing;
- what you excluded and why.

## Output

A ranked list of candidates, about 30 to 100 worth a glance.

## Next

`github-scout-triage`.
