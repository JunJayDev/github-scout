---
name: github-scout-search
description: Search GitHub along planned directions in English and Chinese; drop lures, farmed installs, dead repos and those with too few stars.
license: MIT
metadata:
  improve-repo: JunJayDev/github-scout
  improve-path: skills/github-scout-search
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
- **Under 50 stars is no reference, unless the direction is thin.** Leave such repos out of the
  ranking and the candidates, and count them. A direction (one entity or mechanism group) with
  fewer than 5 maintained repos at 50+ keeps its own repos down to 20 stars; still fewer than 5,
  down to 10; never lower. Say which directions were relaxed and why. Awesome lists are exempt:
  they are only for finding. Any other exception needs a reason, such as an official
  organisation's repo released this week.
- **Read the repo's own page** before you list it. Record its stars and last commit as shown there.
- A repo describes what it makes, not every use people found for it. So also look at what is
  new and growing fast in the form you need, even when no search word matches it. New and
  fast-growing is how you find; it does not pick. Picking (triage) goes by fit, project evidence,
  stars and fit; the coding agent's trial settles it later.

## With the command line

```bash
github-scout scan <project>/<question>                  # about 140 searches, 5 to 15 minutes
```

- **What `scan` searches, all merged into one ranked table:**
  - every entity and mechanism, alone and in pairs; a word that matches over 1,000 repos is
    read again in best-match order, where smaller repos that say it plainly come up;
  - GitHub topics;
  - the last 12 months;
  - SKILL.md files;
  - skills.sh, the MCP registry, npm;
  - a rising list: repos new in the last two months and growing fast in the question's forms,
    found without words.
- **Ranking, for finding:** relevance first, then young and moving. It is not a verdict.
- **Left out and counted in the header:** lures, farmed installs, and repos under the star
  floor (`--all` shows them; `pick <q> owner/repo --low-stars "why"` takes one anyway). The floor
  is 50, relaxed per direction: the `relaxed` line names each direction with fewer than 5 repos
  at 50+, the floor it got (20, then 10) and how many it had (`stroke order to 20 stars (only 3 at
  50+)`); its rows carry `relaxed: <direction>` and need no `--low-stars`. The header names the
  first few still hidden that fit four or more vocabulary groups: for a question about who else
  does this, read them.
- **Widen with what the API cannot see:**
  - Do one pass of web search per direction, in English and Chinese: `site:github.com <entity> <mechanism>`.
  - Include Chinese communities (掘金, 知乎, 少数派, V2EX) and any links the user shared.
  - Feed what you find back in: `github-scout scan <q> --add <file|url|text> --note "<where from>"`.
  - Expand a relevant awesome list: `github-scout scan <q> --expand <owner/list>`.

## Without the command line (cloud chat)

A chat has web search and, when the user connected it, a GitHub connector. It has no browser.
Most of the budget goes to finding: at least 40 searches before you read candidates one by one.

**1. Check your tools once** and write the answers in the report's access table:

- Is a GitHub connector connected? Can it search repositories (in ChatGPT:
  `github_search_repositories`), search code (`github_search`), and read a public repo the user
  does not own (`github_fetch`, `github_fetch_file`)? Does it accept GitHub's qualifiers
  (`topic:`, `created:>`, `user:`)? Try one query with a qualifier.
- Does `site:github.com <first term of D1>` on web search return repositories?

Use what works. Never write that a lens ran when it did not.

**2. Search with every lens.** The word lenses run for every direction in each language from
the plan (English and Chinese always, others when the user's audience needs them). Each other
lens runs at least once for the whole question, with its main terms, and the rising lens once
per topic in its row. A third run of this test searched words 40 times and the rising lens once;
the repos it missed were the ones only the other lenses find. Queries of one to three
terms, never a list of tool names you already know: such queries only return those tools, and
a long query returns little at all. A broad word alone (`github`, `开源`, `skill`) returns only
the most-starred repos: search it paired with a narrower word, and where the connector lets you
choose the order, read a search that matches thousands in best-match order too. Search the
Chinese words too: Chinese projects are found by the words their authors use.

With a connector that searches GitHub, it is GitHub's own search: run the lenses as `scan` does.
Dates: six months back for `pushed:>`, twelve for `created:>` in the recent lens, two months for
the rising lens.

| lens | connector query |
|---|---|
| words (E, P, M, C) | `<entity> pushed:>YYYY-MM-DD`; `"<a>" "<b>" in:readme`; `"<mechanism>"`; `"<mechanism>" "<entity>" in:readme` |
| recent (R) | `<term> in:name,description,readme created:>YYYY-MM-DD` |
| topics (T) | `topic:<topic>`, and `topic:<topic> created:>YYYY-MM-DD` |
| rising (H) | `topic:claude-skills created:>YYYY-MM-DD stars:>50`, the same for `agent-skills`, `claude-code-skill`, `codex-skills`, `mcp-server`; sorted by stars |
| skill files (K) | code search: `"<term>" filename:SKILL.md` |
| same author (U) | `user:<owner>` for the owners of shortlisted repos |

Web search covers what GitHub search does not: articles and posts that name repos, and the
directories.

| lens | web query |
|---|---|
| skills (S) | `site:skills.sh <term>` |
| MCP servers (D) | `site:glama.ai <term>`; `site:mcp.so <term>` |
| packages (N) | `site:npmjs.com <term>` |
| lists (L) | `awesome <field> github`; `awesome <中文词>` |
| communities (W) | `<中文词> github 开源`; `site:zhihu.com OR site:juejin.cn OR site:bilibili.com <中文词> github`; `<term> github site:reddit.com` |
| words, without a connector | `site:github.com <terms>`; `site:github.com/topics <topic>` |

Do not spend web searches on repos you already have: read them through the connector. The
community lens in Chinese still runs even with a connector: posts there name repos whose own
words never match the goal.

**3. Follow what you find:**

- **Lists (L):** when an awesome list or catalog for the field turns up, read all of it
  (through the connector, or by opening its README) and screen every repo it links. One list
  often holds more than all your searches together; opening a list and not reading it is the
  most common way to miss the best repos. When a list is too long to screen, screen the
  sections that match the directions and attach every link as a companion file
  (`| repo | category |`, one URL per row): the local import checks and ranks them all.
- **Neighbours of the shortlist (G, U):** for each repo you shortlist, search
  `site:github.com <owner>` for the author's other repos (authors often have a sibling project
  that fits better) and `"<repo name>" alternative`, and screen the repos its README links.

**4. Facts for each candidate you keep:** stars and last commit as the repo page, a search
result or the connector shows them. Under 50 stars, leave it out and name it under the table as
excluded, unless its direction has fewer than 5 candidates at 50+: then keep that direction's
repos down to 20 stars (then 10, never lower) and write the relaxation under the table. If none
shows the stars, write "unknown" and move on: the local import fills in stars and dates, drops
repos with no push in 12 months, and keeps a shortlist under the floor as later.

- A search snippet that does not mention something is no proof the repo lacks it. When it
  matters, read the README.
- Keep 10 to 30 candidates whose pages you read; more if the user asks for a complete register.
  Tools everyone knows (FFmpeg, Blender, Whisper and the like) need no search and are not
  candidates: name them with their links in one line under the table.
- Official documentation and hosted services often answer part of the goal. Keep them as "other
  sources", with their URLs.

**5. Write section 2 of the report** (format in `references/report-format.md`):

- **Access:** each tool check above and its answer.
- **Search log:** one row per search or list you read: number, lens, direction, language, the
  query word for word, how many results you looked at, and which repos you kept from it. All
  seven columns: without "kept", nobody can tell which search found what. This
  is how anyone can see what was searched, repeat it, and find the hole when a repo was missed.
- **Candidates:** one row per repo: URL, kind, direction, language of the project, why it may
  help, last commit, stars, found by (the log number or the list). No verdict column: verdicts
  belong to triage, and the importer ignores them here.
- Under the table: repos you saw but did not read (names only); directions that found nothing;
  directions relaxed below 50 stars, with how many they had at 50+; what you excluded and why.

The local agent can then run the lenses a chat cannot reach (GitHub's API, the rising list,
skills.sh counts) on the same directions with `github-scout scan`; rows without `W` in its table
are the repos this report did not list.

## Output

Locally, a ranked table with 30 to 100 rows worth a glance. In a chat, the access table, the
search log, and 10 to 30 candidates you opened, plus other sources.

## Next

`github-scout-triage`.

## Improve this skill

This skill is open source (`metadata.improve-repo` in its header). When a run goes wrong because of the skill itself, not the user's input or the environment (a wrong or missing step, a command that fails, output that misleads, a case it should cover), fix it at the source instead of working around it.

Run `gh repo view <improve-repo> --json viewerPermission`. With WRITE, MAINTAIN or ADMIN:

1. Work in a clone of the repository, never in the installed copy, on a branch `improve/<short-slug>`.
2. Change the skill or its code, add a test (or an eval case) that fails without the change, and run the repository's checks.
3. Commit, push the branch and open a pull request: what you ran, what went wrong, the evidence, what changed. Do not merge it. Keep personal paths, tokens and account names out of the diff and the text.

With less permission, or without `gh`: tell the user what you found and offer the fix as a patch; open no pull request or issue unasked. If you cannot fix it now, record it: `scripts/report-problem.sh "<summary>"`.
