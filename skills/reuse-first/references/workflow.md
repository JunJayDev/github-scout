# Workflow, with a worked example

The example is a real case. An operations project needed to read and post on Reddit, X and
Xiaohongshu through a logged-in browser, with no model in the loop. Agents searched for
"social media automation" and "自媒体 运营", found old bots and tutorials, and started writing
their own scraper. The right tool, a 30k-star project created that year, described itself as
"Make any website into CLI & use your logged-in browser by AI agent". None of the agents'
words appeared in that sentence. A person found it while scrolling X.

## 1. Vocabulary

Bad, because it has only problem words:

```yaml
problems: ["social media automation", "post to social media"]
```

Good:

```yaml
want: "Drive logged-in sites (Reddit, X, Xiaohongshu) from scripts without a model in the loop"
entities: ["reddit", "xiaohongshu|小红书|rednote", "twitter|x.com", "bilibili", "zhihu"]
mechanisms: ["logged-in browser", "chrome extension", "browser cookies", "CDP"]
forms: [cli, mcp, skill]
problems: ["social media automation", "自媒体 自动化", "website to cli"]
```

Why each part works:

- **Entity pairs** find multi-platform tools. A tool that supports both Reddit and Xiaohongshu
  names both in its README; a tutorial about one platform does not. `"reddit xiaohongshu
  in:readme"` put the target first.
- **Mechanisms** find the tool by how it works. `"logged-in browser"` also put it first.
- **Topics plus a 12-month window** find young projects that best-match search buries under
  old ones.
- **Other-language synonyms** (`小红书`) reach communities that do not write in English.
- **Problem phrases** are kept, but they find the least.

Writing good mechanisms: picture the solution's README. What would it say it uses? "headless
Chrome", "Playwright", "the Web Speech API", "an MCP server", "SQLite FTS5", "whisper.cpp".
Write those words, not what the solution is for.

## 2. Reading the scan table

```
  #  score  stars   stars/mo  pushed  license      repo  description  [lenses]
  1.  14.7  97.2k 12.7k/mo 26-10-08  MIT          Panniantong/Agent-Reach  Give your AI agent eyes ...  [EPMTR]  fit 4
  7.   9.7  30.3k  4.3k/mo 26-10-13  Apache-2.0   jackwener/OpenCLI  Make Any Website into CLI & ...  [PMCR]  fit 1
```

- `score` combines fit, stars, stars per month since creation, how many lenses found the repo,
  and recent activity. It decides the order of the table. It is not a verdict.
- `fit` is the number of vocabulary groups in the repo's own name, description and topics.
- The lens letters show why a row is there. Several letters mean several independent routes
  found it.
- `seen:skip@other/need` means another need already triaged the repo. Read that reason before
  you look at it again.

Shortlist about 5–10 rows. One irrelevant shortlisted row costs a ~1.2k-token peek. One
relevant row you skip is the whole reason this skill exists, so when in doubt, shortlist.

## 3. Widening the search

The API does not see repos without good metadata, projects announced on social media, or
projects hosted outside GitHub. One pass outside GitHub search takes about 5 minutes:

| source | query patterns |
|---|---|
| web search | `site:github.com <entity> <mechanism>` · `site:github.com <entity> cli OR mcp OR skill` · `"<entity>" "github.com" <mechanism>` |
| other languages | the same queries with `小红书`, `自动化`, `开源`, or Japanese, Korean and other terms |
| forums | `<problem> github` on Reddit, Hacker News, V2EX, Zhihu |
| X | posts that mention an entity and link github.com, plus posts from builders in the field |
| the user | links they shared in chat or bookmarked |

Pipe each result list into the registry, so the same ranking and triage apply:

```bash
reuse-first ingest ops/browser-ops notes.txt --note "web: site:github.com xiaohongshu cli"
pbpaste | reuse-first ingest ops/browser-ops - --note "X search: xiaohongshu github"
```

For awesome lists, `expand` keeps only the links that match the need's vocabulary. Add `--all`
to keep every link.

## 4. Peek, read, try

- `peek` shows a kind guess with its evidence. A repo can be a CLI that also ships skills
  (OpenCLI ships four). Record the kind that describes how you would use it.
- `fetch` prints the size of each part in tokens, so you can read `clis/reddit/*.js` and
  skip the other 100 adapters.
- For software: install it on the machine where it will run, do one real task with it, and
  write down what happened (exit codes, failures, speed). That moves the card to `level: trial`.

## 5. Writing the decision

A good Decision section names, for each part of the need, what covers it and how:

> Reads on Reddit and Xiaohongshu: jackwener/OpenCLI (adopt, pinned v1.8.8). Reddit comments
> with ids and parents: our own adapter on OpenCLI's plugin API (extend; 60 lines), because
> its `reddit read` drops comment ids. Posting stays on the existing scheduler; no tool found
> that posts without a model and survives rate limits (scans 20261015-001847, web pass
> 2026-10-15). Watch Tencent/BrowserSkill for the same job with a smaller permission set.

That one paragraph tells the next agent what to run, what not to rebuild, and where the gap is.

## 6. Upkeep

- Weekly, or before relying on a repo again: `outdated --project <p>`.
- A `review` row means a watched path changed, a release came out, or the repo was archived
  or relicensed. Run `diff`, update the card if anything you use changed, then `bump`.
- Rescan a need with `scan`. `results` merges all scans, and repos already triaged stay hidden.
