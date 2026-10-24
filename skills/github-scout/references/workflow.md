# Workflow, with a worked example

Sections 1 to 5 follow github-scout's stages: plan (1), search (2, 3), triage (4), the report
(5). Sections 6 and 7 are the coding agent's, after the report and when the user asks: trying and
choosing, then adopting. The order matters: an effect anyone can check decides what is tried, and
a trial decides what is followed, before anyone reads code.

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
  stated capabilities and examples come near it, and the coding agent's trial checks it on our machine.
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
- **Several words per idea.** A repo names an idea in its own words, and a group that says it
  one way misses the rest: a Chinese repo that offers "已经存在的产品、开源项目和可复用组件" is not
  found by `现成方案` alone. `scan --plan` names the mechanism groups said one way in a language.
- **Narrow words, not broad ones.** `github`, `开源`, `skill`, `tool` say what any repo is. Alone,
  a search for one returns only the most-starred of hundreds of thousands, so they take no slot in
  the capped lenses and `scan --plan` warns about them; so does any term an earlier scan found
  matching 10,000 repos or more. Say what the repo does instead, and keep shape words (skill,
  cli, mcp) in `forms`. A search that matches over 1,000 repos is read again, 100 rows in
  best-match order, which brings up smaller repos that say the words plainly.
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
  old one. Picking comes later, on fit, project evidence and stars.
- Rows under 50 stars are left out of the table and counted in the header: they are no
  references. A niche direction may not have five repos that big, so each entity and mechanism
  group is counted: under 5 maintained repos at 50+ in its own words, its rows are shown down to
  20 stars, then 10, never lower. The `relaxed` line names them (`xiaohongshu to 20 stars (only 3
  at 50+)`) and such rows carry `relaxed: <group>`; `pick` and `note` take them without a reason
  and record the relaxation. `--all` shows the rest; `pick <q> owner/repo --low-stars "why"` takes
  one anyway. The header names the first few still hidden that match four or more vocabulary
  groups: for a question about who else does this (competitors, the whole field) they are what
  you came for.
- `fit` is the number of vocabulary groups in the repo's own name, description and topics.
- Lens letters show why a row is there; several letters mean several independent routes found it.
- The header line says how many repos were dropped (no push in 12 months) or hidden (6 months).
- The `languages:` line counts the searches per language and the rows with a Chinese
  description. Few Chinese searches or rows usually mean the vocabulary lacks Chinese terms.
- The `broad words` line names terms whose own search matched 10,000 repos or more: only their
  most-starred came back. `scan --plan` says what to do about them.
- `seen:skip@other/question` means another question already judged it; read that reason first.
- The `rising` block under the table (`h1`, `h2`...) holds new repos growing fast that match no
  vocabulary. Words cannot find a tool whose description never names your use, so read these
  by what they make. They are counted in `pick --rest` like the table rows. Only rows that show
  one of the question's forms in their name, description or topics are listed (a question for
  skills and CLIs does not list a graphics driver); `--all` shows the rest.

`look` the promising rows first: about 1.3k tokens each, with the project evidence listed without grading.
Open what it lists and pick 3 to 8 whose effect comes close to what good looks like. A repo
with only a text description is `later`, however clever its README.

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

## 4. Looking

`look` shows activity next to the facts: commits in 30 days, releases in 90, the top
contributor's share. A one-person repo pushing daily is normal now; a team repo gone quiet is a
warning. Then project evidence, without a quality grade:

```text
project evidence (not a quality verdict): · reachable site (homepage) https://example.org/demo
  project-provided links: 1 image in the README: https://github.com/owner/repo/blob/main/demo.png
```

Review the README, examples and useful links briefly for obvious mismatches. Reachability only
means accessible; actual output is tried after the report. Missing demo links do not block a
reference. Record useful links with `note --results` when available; they remain ungraded.

Before recommending the top two or three, make one focused independent search per repo in
English and Chinese. Open relevant sources about real use, recommendations, outputs and
problems; confirm they refer to this project. Author promotion, reposts and directory listings
alone do not count. Use x-scout for X when available; otherwise record the access limit and use
other sources. Record a short finding with links, "no independent usage feedback found", or
"not checked" if search was unavailable. Missing feedback alone does not reject a repo.

## 5. The report

Write it in the question file. github-scout does not try the repos or choose one: it says what
exists and what to try first. A good one, for a project at `prototype`:

> **In one paragraph.** OpenCLI drives our own logged-in Chrome through an extension and returns
> JSON for Reddit, X and Xiaohongshu reads; xiaohongshu-mcp does one site well. Try OpenCLI first,
> xiaohongshu-mcp second. Posting without a model is likely left to build: nothing found posts
> and survives rate limits.
>
> **Candidates.** | jackwener/OpenCLI | cli | 30k | 2026-10-17 | project site: opencli.info, npm 87k a
> month | one command per site, JSON | replaces tools/reddit/chrome.ts | ...
>
> **Try first.** 1. OpenCLI: install it, run `opencli reddit hot` through our logged-in Chrome;
> look for JSON with post and comment ids, no model in the loop. Independent feedback: <finding
> and source links, or none found; record queries under Searched>. 2. xiaohongshu-mcp: ...
>
> **Not recommended.** The social-media bots the first searches found: old, and they do not drive our
> logged-in browser.

Set `picked: [jackwener/OpenCLI, xpzouying/xiaohongshu-mcp]` and `status: answered` in the
frontmatter, and leave `backbone:` empty. Then `github-scout brief ops/browser-ops` packs it into
the report for the coding agent: the answer, each repo's take, stars, evidence links and
reviewed commit, how to try and choose, one `note --trial` line and one adopt line per repo, Not
recommended, and what was searched (the scans' coverage, every relaxed star threshold). The
project itself is not changed.

## 6. Trying and choosing (the coding agent)

When the user asks, the project's coding agent takes the report (`github-scout-dig`):

- It tries each repo under Try first the way the report says, outside the project: a throwaway
  directory or a container, no tokens or keys. For OpenCLI that was one read command on Reddit
  through our logged-in Chrome. Each run is recorded, the failures too:
  `github-scout note jackwener/OpenCLI --q ops/browser-ops --take use --trial "<what ran, what came out>"`.
  It stops at the first wall; a trial is minutes, not a day.
- It chooses one main reference, the one whose trial worked and whose output comes closest to
  what good looks like, and at most one alternate; it sets `backbone: jackwener/OpenCLI` in the
  question file.
- Then it reads that repo's code to follow it and find its gaps. `look --source` maps the code in
  tokens, so it reads `clis/reddit/*.js` and skips the other 100 adapters. OpenCLI drives the
  browser through an extension in the user's own profile, so it inherits every login and never
  needs the debugging port, but its `reddit read` drops comment ids: a gap, filled by our own
  comment adapter on its plugin API. It writes the trials, the choice and each gap with its
  source and reason under Trials and choice.

## 7. Adopting

Stages 1 to 5 never touch the project. When the user asks, the coding agent brings its choice in
(`github-scout-adopt`), inside the project's repository and by its rules, one commit per repo,
each step checked against what good looks like and the project's tests. One mode per repo:

| mode | for | traced by |
|---|---|---|
| depend | a package | a pinned version |
| vendor | files copied at the reviewed commit; edits allowed | repo, commit and source path in each file or a manifest beside them; our edits listed |
| port | the idea rewritten in our code | one comment at the top of our file naming the upstream file |
| skill | an agent skill installed as is | its folder unchanged |
| tool | their CLI or app called as is | a pinned version |
| data | datasets, fonts, prompts, assets | repo, commit and source path beside them |

The main reference comes in whole (`depend`, `skill` or `tool`); `port`, `vendor` and `data`
take one piece for a named gap, and say which in `--note`. The choice above gives two adoptions:
run OpenCLI as is for reads (the main reference), and port its Reddit reader into our own comment
adapter (the gap: comment ids). After each commit:

```bash
github-scout adopt jackwener/OpenCLI --q ops/browser-ops --mode tool --into tools/opencli/run.sh --note "pinned v1.8.8"
github-scout adopt jackwener/OpenCLI --q ops/browser-ops --mode port \
  --into tools/opencli/plugin/reddit-comments.ts --from clis/reddit/read.js --note "gap: comment ids"
```

Each writes an `adopted` entry on the card: our paths, their paths, their commit (the reviewed
one unless `--at`) and ours (HEAD unless `--ours`). Their paths must exist at their commit. The
same `--q` and `--into` again update the entry (`--from`, `--at` and `--note` left out keep what was
recorded); `--drop` marks it dropped and keeps it. A repo from the report the agent did not
take gets `github-scout note` with the reason, so the next search knows why.

## 8. Upkeep

- `updates` lists adopted repos first. For each `--from` path it counts the upstream commits that
  touched it since the commit we took it at, and names the newest:
  `adopted into ops (port tools/opencli/plugin/reddit-comments.ts): upstream clis/reddit/read.js changed 2 times since b9213a1 — newest …`.
  Read `updates --diff <repo>`, update our copy, and record it again with `--at <their new commit>`.
- Before relying on a repo again: `updates --project <p>`.
- A `review` row means a watched path or a file we took changed, a release came out, the repo was archived,
  or it stopped being maintained. `updates --diff <repo>`, update the card, `updates --done <repo>`.
- Rescan a question with `scan`; `scan --show` merges all scans and hides what was decided.
