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

A chat has web search and, when the user connected it, a GitHub connector. It has no browser, so
GitHub's API, its search page and its topic pages are out of reach. Run the lenses of `scan` as
search queries instead. Most of the budget goes to finding: at least 40 searches before you read
candidates one by one. Licences, usage rights and pricing are not part of the search.

**1. Check your tools once** and write the answers in the report's access table:

- Does `site:github.com <first term of D1>` return repositories?
- Can you open a page by its address, for example the raw README of a repo from that search
  (`https://raw.githubusercontent.com/<owner>/<repo>/HEAD/README.md`)?
- Is a GitHub connector connected? If so: can it read the user's project; can it read a public
  repo the user does not own; can it search repositories or code across GitHub?

Use what works. Never write that a lens ran when it did not.

**2. Search with every lens.** The word lenses run for every direction in each language from
the plan (English and Chinese always, others when the user's audience needs them); the other
lenses run once or twice for the whole question, with its main terms. Queries of one to three
terms, never a list of tool names you already know: such queries only return those tools, and
a long query returns little at all.

| lens | queries |
|---|---|
| words (E, P, M, C) | `site:github.com <entity>`; two entities; `"<mechanism>"`; a mechanism with an entity; the same without `site:`, ending in `github` |
| recent (R) | the same with the year: `site:github.com <term> 2026` |
| topics (T) | `site:github.com/topics <topic>`: a topic page lists many repos at once |
| skill files (K) | `site:github.com "SKILL.md" <term>` |
| rising (H) | `site:trendshift.io <term>`; `site:hellogithub.com <中文词>`; `new open source <field> github <month> <year>` |
| skills (S) | `site:skills.sh <term>` |
| MCP servers (D) | `site:mcp.so <term>`; `site:glama.ai <term>` |
| packages (N) | `site:npmjs.com <term>` |
| lists (L) | `site:github.com awesome <field>`; `awesome <中文词>` |
| communities (W) | `<中文词> github 开源`; `site:zhihu.com OR site:juejin.cn OR site:bilibili.com <中文词> github`; `site:news.ycombinator.com <term> github`; `site:reddit.com <term> github` |

If the GitHub connector can search repositories, use it for the word lenses first: that is
GitHub's own search, and it finds repos a search engine has not indexed yet.

Search the Chinese words too: Chinese projects are found by the words their authors use, on
GitHub and in Chinese communities.

**3. Follow what you find:**

- **Lists (L):** when an awesome list or catalog for the field turns up, read all of it
  (through the connector, or by opening its README) and screen every repo it links. One list
  often holds more than all your searches together; opening a list and not reading it is the
  most common way to miss the best repos.
- **Neighbours of the shortlist (G, U):** for each repo you shortlist, search
  `site:github.com <owner>` for the author's other repos (authors often have a sibling project
  that fits better) and `"<repo name>" alternative`, and screen the repos its README links.

**4. Facts for each candidate you keep:** stars and last commit as the repo page, a search
result or the connector shows them. If none shows them, write "unknown" and move on: the local
import fills in stars and dates and drops repos with no push in 12 months.

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
  query word for word, how many results you looked at, and which repos you kept from it. This
  is how anyone can see what was searched, repeat it, and find the hole when a repo was missed.
- **Candidates:** one row per repo: URL, kind, direction, language of the project, why it may
  help, last commit, stars, found by (the log number or the list). No verdict column: verdicts
  belong to triage, and the importer ignores them here.
- Under the table: repos you saw but did not read (names only); directions that found nothing;
  what you excluded and why.

The local agent can then run the lenses a chat cannot reach (GitHub's API, the rising list,
skills.sh counts) on the same directions with `github-scout scan`; rows without `W` in its table
are the repos this report did not list.

## Output

Locally, a ranked table with 30 to 100 rows worth a glance. In a chat, the access table, the
search log, and 10 to 30 candidates you opened, plus other sources.

## Next

`github-scout-triage`.

A defect in this skill that stays unfixed: record it with `scripts/report-problem.sh "<summary>"`.
