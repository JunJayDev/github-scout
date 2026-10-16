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

- **Maintenance:** no push in 3 months ranks far down; 6 months is set aside unless nothing
  maintained covers the need; 12 months is dropped. For model repositories, the date of the
  latest weights or release counts too.
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

A chat has room for about 60 searches and page fetches. Spread them over the directions and
languages, and keep 10 to 30 candidates whose pages you opened.

For every direction, in each language from the plan (English and Chinese always, others when the
user's audience needs them):

1. **GitHub's own search**, when you can fetch it (JSON, no login, about 10 searches a minute):
   `https://api.github.com/search/repositories?q=<terms>+pushed:>YYYY-MM-DD&sort=stars&per_page=30`,
   with the date six months back. Vary the terms as the command line does:
   - one entity;
   - two entities with `in:readme`;
   - a quoted mechanism;
   - `topic:<topic>`;
   - `created:>YYYY-MM-DD` for the last year.
2. **Web search**, when the API is out of reach and for what it cannot see:
   - `site:github.com <entity> <mechanism>`;
   - the same without `site:` when results drift to package indexes;
   - `<中文词> github 开源`;
   - `site:juejin.cn OR site:zhihu.com <中文词> github`.
3. **Skills:** `https://skills.sh/api/search?q=<term>` returns JSON with install counts (the web
   page needs JavaScript). Distrust installs far beyond the repo's stars.
4. **New and growing fast, without words:**
   `https://api.github.com/search/repositories?q=topic:agent-skills+created:>YYYY-MM-DD&sort=stars`,
   or the topic that fits the form you need.

For each candidate you keep:
- Fetch `https://api.github.com/repos/<owner>/<repo>` for `stargazers_count`, `pushed_at`,
  `license` and `archived`.
- If that fails, read the newest date on `https://github.com/<owner>/<repo>/commits`. Write
  "unknown" rather than guess.
- A page summary that does not mention something is no proof the repo lacks it. When it matters,
  read the raw README: `https://raw.githubusercontent.com/<owner>/<repo>/HEAD/README.md`.
- Official documentation and hosted services often answer part of the goal. Keep them as "other
  sources", with their URLs.

Write section 2 of the report: one row per repo, with these columns:

- repo URL
- kind
- direction
- language of the project (en, zh, ja, ...)
- why it may help
- last commit
- stars
- found by

Under the table, write:

- how many searches each direction got in each language (count each search once, under its main
  direction; page fetches are not counted);
- repos you saw but did not open: names only, no numbers;
- which directions found nothing;
- what you excluded and why.

## Output

Locally, a ranked table with 30 to 100 rows worth a glance. In a chat, 10 to 30 candidates you
opened, plus other sources.

## Next

`github-scout-triage`.

A defect in this skill that stays unfixed: record it with `scripts/report-problem.sh "<summary>"`.
