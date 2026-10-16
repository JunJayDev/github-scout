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

Run the same lenses as `scan`, through web pages instead of the API. Most of the budget goes to
finding: at least 40 searches across the lenses before you open candidates one by one. Licences,
usage rights and pricing pages are not part of the search; do not spend fetches on them.

**1. Check what you can open.** Try each entry point once, with the first term of direction D1,
and write in the report whether it returned repositories. Use the ones that work. When one fails,
use its fallback and say so; never write that a lens ran when it did not.

| entry point | URL | lenses it serves |
|---|---|---|
| GitHub search page | `https://github.com/search?q=<terms>&type=repositories&s=stars` | words (E, P, M, C, R) |
| GitHub search API | `https://api.github.com/search/repositories?q=<terms>&sort=stars` | the same, as JSON; often unreachable from a chat |
| topic page | `https://github.com/topics/<topic>?o=desc&s=updated` | topics (T), rising (H) |
| trending | `https://github.com/trending?since=monthly` | rising (H) |
| raw file | `https://raw.githubusercontent.com/<owner>/<repo>/HEAD/README.md` | lists (L), links (G) |
| owner's repos | `https://github.com/<owner>?tab=repositories&sort=stargazers` | same author (U) |
| skills.sh | `https://skills.sh/api/search?q=<term>` | installed skills (S) |
| MCP registry | `https://registry.modelcontextprotocol.io/v0/servers?search=<term>` | MCP servers (D) |
| npm | `https://registry.npmjs.org/-/v1/search?text=<term>&size=20` | packages (N) |
| repo facts | `https://ungh.cc/repos/<owner>/<repo>` or `https://api.github.com/repos/<owner>/<repo>` | stars, created, last push |

**2. Search every direction with every lens that works,** in each language from the plan
(English and Chinese always, others when the user's audience needs them):

1. **Words on GitHub's own search (E, P, M, C, R).** Short queries of one to three terms, never
   a list of tool names you already know: such queries only return those tools. Add
   `pushed:>YYYY-MM-DD` (six months back). Per direction and language, at least:
   - each entity alone;
   - two entities together;
   - each mechanism, quoted;
   - a mechanism with an entity;
   - one of these with `created:>YYYY-MM-DD` (twelve months back) and `&s=updated`, for what is new.

   Search the Chinese words on GitHub too: Chinese projects are found by the words their
   authors use (`视频 配音 字幕` puts VideoLingo first). Only when neither the search page nor
   the API opens, fall back to web search: `site:github.com <terms>`.
2. **Topics (T):** the topic page for each entity and form, such as `remotion`, `claude-skills`,
   `agent-skills`, `mcp-server`.
3. **Rising, without words (H):** the topic pages of the form sorted by `updated`, and trending
   (`/trending?since=monthly`, `/trending/<language>?since=weekly`). Screen every repo there
   against the goal, even when no search word matches it.
4. **Curated lists (L):** when a search turns up an awesome list or catalog for the field, read
   its whole README (raw) and screen every repo it links. One list often holds more than all
   your searches together; opening a list and not reading it is the most common way to miss
   the best repos.
5. **Links from the shortlist (G):** read the README of each repo you shortlist and screen the
   repos it links ("see also", "inspired by", "alternatives").
6. **Same author (U):** open the repository list of each shortlisted repo's owner. Authors often
   have a sibling project that fits better.
7. **Skills, MCP servers, packages (S, D, N):** the three registries above. Distrust skills.sh
   installs far beyond the repo's stars.
8. **Web search (W):** articles and posts that name repos GitHub search does not surface:
   `<entity> <mechanism> github`, `<中文词> github 开源`,
   `site:juejin.cn OR site:zhihu.com OR site:bilibili.com <中文词> github`. Follow the repo
   links in them.

**3. Facts for each candidate you keep:** stars, created and last push from "repo facts"; if
neither opens, from the repo page or `https://github.com/<owner>/<repo>/commits.atom` (its first
`<updated>` is the last commit). If nothing loads, write "unknown" and move on: the local import
fills in stars and dates and drops repos with no push in 12 months.

- A page summary that does not mention something is no proof the repo lacks it. When it matters,
  read the raw README.
- Keep 10 to 30 candidates whose pages you opened; more if the user asks for a complete register.
  Tools everyone knows (FFmpeg, Blender, Whisper and the like) need no search: name them with
  their links in one line under the table.
- Official documentation and hosted services often answer part of the goal. Keep them as "other
  sources", with their URLs.

**4. Write section 2 of the report** (format in `references/report-format.md`):

- **Access:** each entry point, whether it worked, and the fallback you used.
- **Search log:** one row per search or list you read: number, lens, direction, language, the
  query or URL word for word, how many results you looked at, and which repos you kept from it.
  This is how anyone can see what was searched, repeat it, and find the hole when a repo was
  missed.
- **Candidates:** one row per repo: URL, kind, direction, language of the project, why it may
  help, last commit, stars, found by (the log number or the list). No verdict column: verdicts
  belong to triage, and the importer ignores them here.
- Under the table: repos you saw but did not open (names only); directions that found nothing;
  what you excluded and why.

## Output

Locally, a ranked table with 30 to 100 rows worth a glance. In a chat, the access table, the
search log, and 10 to 30 candidates you opened, plus other sources.

## Next

`github-scout-triage`.

A defect in this skill that stays unfixed: record it with `scripts/report-problem.sh "<summary>"`.
