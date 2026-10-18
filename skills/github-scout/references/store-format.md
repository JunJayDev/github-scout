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
backbone: heygen-com/hyperframes   # the one repo the answer follows as a whole
alternate: null                    # at most one fallback, tried as well
picked: [heygen-com/hyperframes]   # repos the answer relies on: the backbone, then what fills its gaps
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
the answer (one paragraph; backbone; gaps to fill; trial runs; a table against what we have;
next steps; not adopted), and what was searched. `brief` still reads answers written before
2026-10-18 (ideas worth taking; practices and components), and `check` leaves them alone.

`check` holds an answer that names a `backbone` to the gates: the backbone and the alternate
were tried (`level: trial`), and each of them and every picked repo has `results` or a
`no_results` reason, and the star threshold or a `low_stars` reason. An answered question
with an empty Backbone section and no `backbone` gets a warning.

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
results: ["https://opencli.info/"]   # what it made, to look at: films, galleries, sample outputs, benchmarks, users
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

The body starts with the idea (how it does the job), then results and trial (what it made, and
one dated line per trial run: what we ran, what came out), quality, what we take, risks or
safety, and what to read first. `note --trial` writes the trial line; a card from before that
section gets it after its first section.

`results` holds links, http or https. `note` refuses `use`, `adapt` and `learn` for a repo
without `results` (unless `--no-results` gives a reason) or under the star threshold, 50 or
`GITHUB_SCOUT_MIN_STARS` (unless `--low-stars` does); the reason goes on the take and into the
ledger. Cards without `results` stay valid.

`adopted` holds one entry per project, question and set of our paths: recording the same again
replaces it, and `adopt --drop` adds `dropped: <date>` instead of deleting it. `updates` asks
GitHub for the commits on the branch that touched each `from` path since the date of `at`; an
entry without `from` gets only the repo-level report. Cards without `adopted` are valid.

## Ledger

One JSON object per line, append-only; the latest entry per (repo, project/question) is the
current verdict.

```json
{"date": "2026-10-15", "repo": "a/b", "project": "ops", "question": "browser-ops",
 "verdict": "skip", "level": "meta", "reason": "video downloader, not a browser driver",
 "stars": 1200, "pushed": "2026-09-30", "desc": "…", "scan": "20261015-004320", "by": "agent"}
```

Verdicts: `peeked`, `short`, `list`, `later`, `skip`, `card`. A `skip` comes back once the
repo's stars reach twice the recorded count (and at least 200 more). An adoption is a `card`
entry whose reason starts with `adopted:` or `dropped adoption:`. A `short` under the star
threshold, and a `card` that takes such a repo as a reference, carry `low_stars` (the reason);
a reference without results carries `no_results`. `import` records a shortlist under the
threshold as `later`.

## Scan

```json
{"id": "20261015-004320", "date": "2026-10-15", "project": "ops", "question": "browser-ops",
 "lenses": "EPMCQTRHKSDNUG", "dropped": 12,
 "searches": [{"lens": "P", "kind": "repos", "query": "reddit xiaohongshu in:readme pushed:>2026-04-15", "hits": 30}],
 "candidates": [{"repo": "a/b", "desc": "…", "stars": 1, "created": "…", "pushed": "…",
                 "lang": "Go", "topics": [], "archived": false, "fork": false, "lenses": ["E", "P"],
                 "installs": 4200, "fit": 2, "score": 9.1}]}
```

`dropped` counts repos with no push in 12 months; they are not saved. Only the best 400
candidates are kept. `fit` and `score` are recomputed from the question's vocabulary on every view.

## From format 1

Format 1 had `needs/` with `want` and `chosen`, card `uses` with `need` and `relation`, and 13
kinds. Rename `needs/` to `questions/`, `want` to `ask` (and add `stage`, `status`), `chosen`
to `picked`; in cards `need` to `question` and `relation` to `take` (adopt→use, extend,
derive, migrate→adapt, borrow→learn, watch→later, reject→skip); kinds become `kind` + `form`.
