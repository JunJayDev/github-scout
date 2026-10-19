# Registry format (version 2)

A registry is a directory of Markdown and JSON, usually a git repository so several agents and
machines share it. `github-scout check` validates it and writes `INDEX.md`; `github-scout site`
writes `site/index.html`.

```
github-scout.json                         {"format": 2, "name": "...", "lang": "en" | "zh", "default_project": null}
README.md                                what the registry is (written by init)
INDEX.md                                 generated overview; do not edit
people.txt                               GitHub logins whose stars feed the people lens
projects/<project>/project.md            a project profile
projects/<project>/questions/<q>.md      one question: stage, vocabulary, answer
repos/<owner>__<repo>.md                 one card per repository looked at closely (lowercase file name)
ledger.jsonl                             every verdict, append-only
scans/<project>/<q>/<stamp>.json         each scan's searches and ranked candidates
site/index.html                          generated viewer
cache/                                   downloaded source, one dir per commit (gitignored)
```

`lang` picks the language of new templates. Ids use lowercase letters, digits, `.`, `_` and
`-`; a question is referred to as `<project>/<q>`; a repository as `owner/repo`.

Frontmatter uses a YAML subset any YAML parser reads: scalars (plain, `"double"` with JSON
escapes, `'single'`), inline lists `[a, "b c"]`, and block lists of scalars or flat mappings.

## Project

```yaml
id: shop
name: Shop backend
summary: one line
code: https://github.com/acme/shop       # where its code is: agents read it to compare
stack: [python, postgres]
constraints: ["no AGPL in the service", "Linux arm64"]
languages: [en, zh]
```

## Question

```yaml
id: video-agent
project: ops
ask: "Make product videos that cut and move like an editor's, with an agent doing the work"
stage: working            # idea | prototype | working | polishing
status: open              # open | answered
langs: [en, zh]           # en | zh | ja | ko; default [en, zh]
entities: ["remotion", "product video|宣传片|产品视频"]
mechanisms: ["programmatic video|代码做视频", "html to video"]
forms: [skill, library]
problems: ["agent video editing", "AI 视频 剪辑"]
topics: []
picked: [heygen-com/hyperframes, remotion-dev/remotion]   # the report's two or three to try first
backbone: null                     # optional: the one repo to follow as a whole, set by the coding agent after trying
alternate: null                    # optional: at most one fallback, tried as well
scanned: 2026-10-15
```

`langs` lists the languages the vocabulary must cover; a question without it searches `[en, zh]`,
because in real runs Chinese projects supplied half of the repos picked. A term's language is told
by its script: CJK ideographs are `zh`, kana `ja`, hangul `ko`, anything else `en` (so a
Latin-script language counts as `en`). Each entity and mechanism group should hold a term in every
language listed, written as those users write it, not translated. `check` warns about a group that
lacks one; a name written the same way in every language, like `remotion` above, needs nothing.
The scan builds pairs and combinations within one language. Combinations and the capped lenses
take turns between languages; pairs and recent searches serve the first language in `langs` first
and give the others what is left. Topics and the MCP registry take Latin-script terms only (both are ASCII names).

Body sections (template in the registry's language): where we are (what we have, what is not
good enough), what good looks like (2–3 finished results to match, or checks anyone can run),
the answer, which is the report (in one paragraph; candidates; try first; not recommended; and
trials and choice, which the coding agent fills after trying), and what was searched. `brief`
still reads answers from 2026-10-18 (backbone; gaps to fill; trial runs; against what we have;
next steps; not adopted) and from before (ideas worth taking; practices and components), and
writes them as it did.

`check` holds every picked repo to the gates: a verifiable effect (a mid or strong link in
`results`, or a `no_results` reason) and the star threshold (or a `low_stars` reason, which a
relaxed direction writes itself). A report is not asked for a backbone or for trials. When the
coding agent sets `backbone` (and `alternate`), each must also have been tried (`level: trial`).
An answered question with an empty Try first section and no `picked` gets a warning.

## Card

```yaml
id: jackwener/OpenCLI
repo: https://github.com/jackwener/OpenCLI
kind: software           # skill | software | list | other
form: cli                # detail: skill-pack, mcp, cli, library, framework, app, extension, ...
summary: "Turns websites into CLI commands through your logged-in Chrome"
stars: 30264
created: 2026-03-14
pushed: 2026-10-13
branch: main
commit: b9213a15d63d     # the commit that was reviewed
reviewed: 2026-10-14
level: trial             # meta | look | read | trial
results: ["https://opencli.info/"]   # its verifiable effect: a live site, package or store pages, media, posts
watch: [src/daemon.ts, "clis/reddit/**"]
aliases: [opencli]
uses:
  - project: ops
    question: browser-ops
    take: use            # use | adapt | learn | later | skip
    where: tools/opencli
    note: "Reddit reads through its fetch adapters"
    low_stars: "..."     # only under the star threshold: why it is a reference anyway
    no_results: "..."    # only without results: why it counts anyway
adopted:                 # what came into our projects (github-scout adopt, stage 6)
  - project: ops
    question: browser-ops
    mode: port           # depend | vendor | port | skill | tool | data
    into: [tools/opencli/plugin/reddit-comments.ts]   # our paths, from the root of our git repository
    from: [clis/reddit/read.js]                       # their files or folders; updates watches these
    at: b9213a15d63d     # their commit we took it at
    ours: 4f0c2e1        # our commit that brought it in
    date: 2026-10-17
    note: "comment ids kept"
```

The body starts with the idea (how it does the job), then verifiable effect and trial (what it
does that anyone can check, and one dated line per trial run: what ran, what came out), quality,
what we take, risks or safety, and what to read first. `note --trial` writes the trial line, into
"Results and trial" on cards from before 2026-10-19; a card without either section gets it after
its first section.

`results` holds links, http or https, each graded without fetching it:

| tier | links |
|---|---|
| strong | a package or store page (npm, PyPI, App Store, Chrome Web Store and similar); `look` also grades as strong a homepage or README demo link that answers, npm downloads and the installs a scan recorded |
| mid | images, GIFs and videos (by extension, or GitHub's attachment hosts); posts on X, Bilibili, YouTube, blogs, Xiaohongshu; any other site not checked by `look` (it may be a blog as well as a live app); another GitHub repository |
| weak | pages of the repo itself on GitHub that are not media: its README and other text |

`note` refuses `use`, `adapt` and `learn` for a repo whose best tier is weak (unless
`--no-results` gives a reason; installs of 100 or more recorded by a scan count as strong) or
under its star floor (unless `--low-stars` does); the reason goes on the take and into the
ledger. The floor is the threshold, 50 or `GITHUB_SCOUT_MIN_STARS`, or the relaxed floor of the
repo's direction in the question's scans, in which case `note` writes the relaxation as the
`low_stars` reason itself. Cards without `results` stay valid.

`adopted` holds one entry per project, question and set of our paths: recording the same again
updates it (fields not given keep their value; after a drop it starts afresh), and `adopt --drop`
adds `dropped: <date>` instead of deleting it. `updates` asks GitHub for the commits on the
repo's current default branch that touched each `from` path since the date of `at`, and says when
a path is no longer there; an entry without `from` gets only the repo-level report. Cards without
`adopted` are valid.

## Ledger

One JSON object per line, append-only; the latest entry per (repo, project/question) is the
current verdict. Readers split lines on `\n` alone, and U+2028, U+2029 and U+0085 inside a
string are written escaped (`\u2028`), so text pasted from a web page cannot break an entry.

```json
{"date": "2026-10-15", "repo": "a/b", "project": "ops", "question": "browser-ops",
 "verdict": "skip", "level": "meta", "reason": "video downloader, not a browser driver",
 "stars": 1200, "pushed": "2026-09-30", "desc": "…", "scan": "20261015-004320", "by": "agent"}
```

Verdicts: `peeked`, `short`, `list`, `later`, `skip`, `card`. A `skip` comes back once the
repo's stars reach twice the recorded count (and at least 200 more). An adoption is a `card`
entry whose reason starts with `adopted:` or `dropped adoption:`. A `short` under the star
threshold, and a `card` that takes such a repo as a reference, carry `low_stars` (the reason,
`relaxed: <direction> had under 5 repos at 50+ stars (floor 20)` when its direction was relaxed);
a reference without a verifiable effect carries `no_results`. `import` records a shortlist under
the floor as `later`.

## Scan

```json
{"id": "20261015-004320", "date": "2026-10-15", "project": "ops", "question": "browser-ops",
 "lenses": "EPMCQTRHKSDNUG", "dropped": 12,
 "searches": [{"lens": "P", "kind": "repos", "query": "reddit xiaohongshu in:readme pushed:>2026-04-15", "hits": 30}],
 "candidates": [{"repo": "a/b", "desc": "…", "stars": 31, "created": "…", "pushed": "…",
                 "lang": "Go", "topics": [], "archived": false, "fork": false, "lenses": ["E", "P"],
                 "installs": 4200, "fit": 2, "score": 9.1, "floor": 20, "relaxed": "xiaohongshu"}],
 "relaxed": [{"group": "xiaohongshu", "floor": 20, "counts": {"50": 3, "20": 6}}]}
```

`relaxed` lists the directions whose star threshold was lowered: an entity or mechanism group
(named by its first term) with fewer than 5 maintained repos at the threshold in their own words
(name, description, topics; archived repos, lures, farmed installs and lists not counted). Its
rows are shown down to 20 stars, then 10 when 20 still leaves fewer than 5, never lower;
`counts` gives the repos at each level tried. Each row of such a group carries `floor` (the
lowest floor among its groups) and `relaxed` (that group). Scans from before have neither.

The id is the second the scan ran (`YYYYMMDD-HHMMSS`); a second scan of the question in the same
second gets `-2`, `-3` ... (`20261015-004320-2`), sorted after it. `dropped` counts repos with no
push in 12 months; they are not saved. Only the best 400 candidates are kept. `fit`, `score`,
`relaxed` and `floor` are recomputed from the question's vocabulary and all its scans on every
view, so `pick`, `note`, `look` and `brief` see the same relaxation the table shows.

## From format 1

Format 1 had `needs/` with `want` and `chosen`, card `uses` with `need` and `relation`, and 13
kinds. Rename `needs/` to `questions/`, `want` to `ask` (and add `stage`, `status`), `chosen`
to `picked`; in cards `need` to `question` and `relation` to `take` (adopt→use, extend,
derive, migrate→adapt, borrow→learn, watch→later, reject→skip); kinds become `kind` + `form`.
