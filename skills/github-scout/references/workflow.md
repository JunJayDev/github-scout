# Workflow, with a worked example

Sections 1 to 6 follow the stages: plan (1), search (2, 3), triage and dig (4), brief (5),
adopt (6). The order matters: results and a trial decide, before anyone reads code.

The example is a real case. An operations project needed to read and post on Reddit, X and
Xiaohongshu through a logged-in browser, with no model in the loop. Agents searched for
"social media automation" and "自媒体 运营", found old bots and tutorials, and started writing
their own scraper. The right tool, a 30k-star project created that year, described itself as
"Make any website into CLI & use your logged-in browser by AI agent". None of the agents'
words appear in that sentence. A person found it while scrolling X.

## 1. The question

A weak question asks for a tool: "find a social media automation tool". It gets tools for
someone else's problem.

A strong question asks for a result, says where we stand, and what is not good enough:

```
github-scout ask ops/browser-ops "Drive our logged-in accounts on Reddit, X and Xiaohongshu from scripts, no model clicking pages" --stage prototype
```

Then, in the file: what we have (`tools/reddit/chrome.ts` drives Chrome through a model; one run
costs 580k tokens and 16 subreddits get blocked); what good looks like (one command returns a
subreddit's posts as JSON through our own logged-in Chrome, with no model in the loop, and the
same for X and Xiaohongshu); and the vocabulary:

```yaml
langs: [en, zh]
entities: ["reddit", "xiaohongshu|小红书|rednote|xhs", "twitter|x.com|推特", "bilibili|B站|哔哩哔哩", "zhihu|知乎"]
mechanisms: ["logged-in browser|登录态", "chrome extension|浏览器插件|Chrome 插件", "browser cookies", "CDP",
             "browser automation|浏览器自动化"]
forms: [cli, mcp, skill]
problems: ["social media automation", "自媒体 自动化", "website to cli"]
```

Why each part works:

- **What good looks like** is the yardstick for every later stage: triage keeps the repos whose
  results come near it, and the trial checks it on our machine.
- **Entity pairs** find multi-platform tools: a tool that supports both Reddit and Xiaohongshu
  names both in its README; a tutorial about one platform does not. `"reddit xiaohongshu"
  in:readme` put the target first.
- **Mechanisms** find a tool by how it works. `"logged-in browser"` also put it first.
- **Topics plus a 12-month window** find young projects that best-match search buries.
- **Every group in both languages.** Chinese projects describe themselves in Chinese, and in real
  runs they supplied half of the repos picked. Combinations and the capped lenses take turns
  between languages, so a group without a Chinese term leaves Chinese searches unmade.
  Pairs and recent searches fill English first and give Chinese what is left. Mechanisms carry the most: `登录态` found a tool that lets any
  agent drive your own Chrome with its logins, described only in Chinese. Platform pairs are
  noisier in Chinese, because many Chinese READMEs link the author's own 小红书 and B站 accounts,
  which is why Chinese pairs only fill leftover slots.
  Write the name Chinese users write, not a translation: `登录态`, not `已登录的浏览器`. Names
  written the same way (`reddit`, `CDP`) need nothing; `scan --plan` warns about the rest.
- **Problem phrases** find the least. Keep them short.

Writing mechanisms: picture the solution's README. What would it say it uses? "headless
Chrome", "Remotion", "an MCP server", "SQLite FTS5", "whisper.cpp". Write those words.

## 2. Reading the scan table

```
  #  score  stars created   pushed  repo  description  [lenses] fit
  1.  11.6  64.2k  26-01 26-10-13  mvanhorn/last30days-skill  AI agent skill that researches ...  [EPMCTRS] fit 1
  4.   9.5    282  26-10 26-10-14  aindeev/agent-chrome-relay  Let your AI agents use your Chrome ...  [T] fit 3
```

- `score` orders the table for finding; it is not a verdict. Relevance counts most, then life:
  a 282-star repo created this month that matches three vocabulary groups ranks above a famous
  old one. Picking comes later, on results, stars, a trial and fit.
- Rows under 50 stars are left out of the table and counted in the header: they are no
  references. `--all` shows them; `pick <q> owner/repo --low-stars "why"` takes one anyway.
- `fit` is the number of vocabulary groups in the repo's own name, description and topics.
- Lens letters show why a row is there; several letters mean several independent routes found it.
- The header line says how many repos were dropped (no push in 12 months) or hidden (6 months).
- The `languages:` line counts the searches per language and the rows with a Chinese
  description. Few Chinese searches or rows usually mean the vocabulary lacks Chinese terms.
- `seen:skip@other/question` means another question already judged it; read that reason first.
- The `rising` block under the table (`h1`, `h2`...) holds new repos growing fast that match no
  vocabulary. Words cannot find a tool whose description never names your use, so read these
  by what they make. They are counted in `pick --rest` like the table rows.

`look` the promising rows first: about 1.3k tokens each, with the README links that look like
results. Open those and pick 3 to 8 that show results close to what good looks like. A repo
with nothing to look at is `later`, however clever its README.

## 3. Widening the search

The API does not see repos without good metadata, projects announced on social media, or
projects hosted elsewhere. Do one pass outside GitHub search:

| source | query patterns |
|---|---|
| web | `site:github.com <entity> <mechanism>` · `site:github.com <entity> cli OR mcp OR skill` |
| other languages | the same with `小红书`, `自动化`, `开源`, Japanese, Korean terms |
| forums | `<problem> github` on Reddit, Hacker News, V2EX, Zhihu |
| X | posts that mention an entity and link github.com; builders in the field |
| the user | links they shared or bookmarked |

```bash
github-scout scan ops/browser-ops --add notes.txt --note "web: site:github.com xiaohongshu cli"
pbpaste | github-scout scan ops/browser-ops --add - --note "X: xiaohongshu github"
github-scout scan ops/browser-ops --expand someone/awesome-browser-agents
```

## 4. Looking, trying, reading

- `look` shows activity next to the facts: commits in 30 days, releases in 90, the top
  contributor's share. A one-person repo pushing daily is normal now; a team repo gone quiet is
  a warning. It also lists README links that look like results; open them first.
- Try the best two or three before reading their code: install, run the smallest example or one
  short real task, compare with what good looks like. For OpenCLI that was one read command on
  Reddit through our logged-in Chrome. Record each run, the failures too:
  `github-scout note jackwener/OpenCLI --q ops/browser-ops --take use --results <links> --trial "<what ran, what came out>"`.
  Stop at the first wall; a trial is minutes, not a day.
- Then read the code of the one you follow. `look --source` maps the code in tokens, so you read
  `clis/reddit/*.js` and skip the other 100 adapters. Read to follow it and to find its gaps:
  OpenCLI drives the browser through an extension in the user's own profile, so it inherits every
  login and never needs the debugging port, but its `reddit read` drops comment ids.

## 5. The answer

Write it in the question file. A good one, for a project at `prototype`:

> **In one paragraph.** Follow OpenCLI for reads on Reddit and Xiaohongshu (pinned v1.8.8). Its
> `reddit read` drops comment ids: fill that with our own comment adapter on its plugin API.
> Keep posting where it is; nothing found posts without a model and survives rate limits.
>
> **Backbone.** jackwener/OpenCLI: 30k stars; its read commands return JSON on the sites we
> need; our trial read one subreddit through our logged-in Chrome. Alternate: none.
>
> **Gaps to fill.** | comment ids | our adapter on its plugin API, ported from `clis/reddit/read.js` | its reader drops them |
>
> **Against what we have.** | model-driven page reading, 580k tokens a run | one JSON request per subreddit | ... | take |
>
> **Not adopted.** The social-media bots the first searches found: old, and nothing they made
> comes near what good looks like.

Set `backbone: jackwener/OpenCLI` and `picked: [jackwener/OpenCLI]` in the frontmatter. That
tells the next agent what to follow, what not to rebuild, and where the gap is. Then
`github-scout brief ops/browser-ops` packs it, with each source's role, stars, results, trial
level and reviewed commit, into a file for the coding agent. It ends with one `github-scout
adopt` line per repo to bring in, then the Not adopted appendix. The project itself is not
changed.

## 6. Adopting

Stages 1 to 5 never touch the project. When the user asks, the project's coding agent brings the
brief in (`github-scout-adopt`), inside the project's repository and by its rules, one commit
per repo, each step checked the way the brief says. One mode per repo:

| mode | for | traced by |
|---|---|---|
| depend | a package | a pinned version |
| vendor | files copied at the reviewed commit; edits allowed | repo, commit and source path in each file or a manifest beside them; our edits listed |
| port | the idea rewritten in our code | one comment at the top of our file naming the upstream file |
| skill | an agent skill installed as is | its folder unchanged |
| tool | their CLI or app called as is | a pinned version |
| data | datasets, fonts, prompts, assets | repo, commit and source path beside them |

The backbone comes in whole (`depend`, `skill` or `tool`); `port`, `vendor` and `data` take one
piece for a named gap, and say which in `--note`. The answer above gives two adoptions: run
OpenCLI as is for reads (the backbone), and port its Reddit reader into our own comment adapter
(the gap: comment ids). After each commit:

```bash
github-scout adopt jackwener/OpenCLI --q ops/browser-ops --mode tool --into tools/opencli/run.sh --note "pinned v1.8.8"
github-scout adopt jackwener/OpenCLI --q ops/browser-ops --mode port \
  --into tools/opencli/plugin/reddit-comments.ts --from clis/reddit/read.js --note "gap: comment ids"
```

Each writes an `adopted` entry on the card: our paths, their paths, their commit (the reviewed
one unless `--at`) and ours (HEAD unless `--ours`). The same `--q` and `--into` again replace the
entry; `--drop` marks it dropped and keeps it. A brief item the agent did not take gets
`github-scout note` with the reason, so the next search knows why.

## 7. Upkeep

- `updates` lists adopted repos first. For each `--from` path it counts the upstream commits that
  touched it since the commit we took it at, and names the newest:
  `adopted into ops (port tools/opencli/plugin/reddit-comments.ts): upstream clis/reddit/read.js changed 2 times since b9213a1 — newest …`.
  Read `updates --diff <repo>`, update our copy, and record it again with `--at <their new commit>`.
- Before relying on a repo again: `updates --project <p>`.
- A `review` row means a watched path or a file we took changed, a release came out, the repo was archived,
  or it stopped being maintained. `updates --diff <repo>`, update the card, `updates --done <repo>`.
- Rescan a question with `scan`; `scan --show` merges all scans and hides what was decided.
