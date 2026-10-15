# Registry format (version 2)

A registry is a directory of Markdown and JSON, usually a git repository so several agents and
machines share it. `reuse-first check` validates it and writes `INDEX.md`; `reuse-first site`
writes `site/index.html`.

```
reuse-first.json                         {"format": 2, "name": "...", "lang": "en" | "zh", "default_project": null}
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
entities: ["remotion", "after effects"]
mechanisms: ["programmatic video", "html to video"]
forms: [skill, library]
problems: ["agent video editing"]
topics: []
picked: [heygen-com/hyperframes]   # repos the answer relies on
scanned: 2026-10-15
```

Body sections (template in the registry's language): where we are (what we have, what is not
good enough), the answer (one paragraph; ideas worth taking; practices and components; a
table against what we have; next steps), and what was searched.

## Card

```yaml
id: jackwener/OpenCLI
repo: https://github.com/jackwener/OpenCLI
kind: software           # skill | software | list | other
form: cli                # detail: skill-pack, mcp, cli, library, framework, app, extension, ...
summary: "Turns websites into CLI commands through your logged-in Chrome"
license: Apache-2.0
stars: 30264
created: 2026-03-14
pushed: 2026-10-13
branch: main
commit: b9213a15d63d     # the commit that was reviewed
reviewed: 2026-10-14
level: trial             # meta | look | read | trial
watch: [src/daemon.ts, "clis/reddit/**"]
aliases: [opencli]
uses:
  - project: ops
    question: browser-ops
    take: use            # use | adapt | learn | later | skip
    where: tools/opencli
    note: "Reddit reads through its fetch adapters"
```

The body starts with the idea (the design decision that makes the repo worth knowing), then
quality, what we take, risks or safety, and what to read first.

## Ledger

One JSON object per line, append-only; the latest entry per (repo, project/question) is the
current verdict.

```json
{"date": "2026-10-15", "repo": "a/b", "project": "ops", "question": "browser-ops",
 "verdict": "skip", "level": "meta", "reason": "video downloader, not a browser driver",
 "stars": 1200, "pushed": "2026-09-30", "desc": "…", "scan": "20261015-004320", "by": "agent"}
```

Verdicts: `peeked`, `short`, `list`, `later`, `skip`, `card`. A `skip` comes back once the
repo's stars reach twice the recorded count (and at least 200 more).

## Scan

```json
{"id": "20261015-004320", "date": "2026-10-15", "project": "ops", "question": "browser-ops",
 "lenses": "EPMCQTRHKSDNUG", "dropped": 12,
 "searches": [{"lens": "P", "kind": "repos", "query": "reddit xiaohongshu in:readme pushed:>2026-04-15", "hits": 30}],
 "candidates": [{"repo": "a/b", "desc": "…", "stars": 1, "created": "…", "pushed": "…", "license": "MIT",
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
