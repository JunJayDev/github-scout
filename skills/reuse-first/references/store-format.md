# Registry format (version 1)

A registry is a directory of Markdown and JSON, usually a git repository so several agents and
machines share it. `reuse-first check` validates it, and `reuse-first index` writes `INDEX.md`.

```
reuse-first.json                      marker: {"format": 1, "name": "...", "default_project": null}
README.md                             what the registry is (written by init)
INDEX.md                              generated overview; do not edit
people.txt                            GitHub logins whose stars feed the people lens
projects/<project>/project.md         a project profile
projects/<project>/needs/<need>.md    one capability: vocabulary, landscape, decision
repos/<owner>__<repo>.md              one card per reviewed repository (lowercase file name)
ledger.jsonl                          every verdict, append-only
scans/<project>/<need>/<stamp>.json   each scan's searches and ranked candidates
cache/                                downloaded source, one dir per commit (gitignored)
```

Ids: projects and needs use lowercase letters, digits, `.`, `_` and `-`. A need is referred to
as `<project>/<need>`. A repository is `owner/repo`, kept in GitHub's capitalisation inside
the card, with a lowercase file name.

## Frontmatter

Frontmatter uses a YAML subset that any YAML parser reads: scalars (plain, `"double"` with
JSON escapes, or `'single'`), inline lists `[a, "b c"]`, and block lists of scalars or of flat
mappings. Nested mappings and block scalars (`|`, `>`) are rejected with a line number.

### Project: `projects/<project>/project.md`

```yaml
id: shop                 # = directory name
name: Shop backend
summary: one line
where: https://github.com/acme/shop     # optional: the repo or path of the project
stack: [python, postgres]
constraints: ["no AGPL in the service", "must run on Linux arm64"]
languages: [en, zh]      # languages to search in
```

The body describes the project for an agent judging fit.

### Need: `projects/<project>/needs/<need>.md`

```yaml
id: payments
project: shop
want: "Take card payments with 3-D Secure from a Python service"
status: open             # open | partial | covered | gap | building
entities: ["stripe", "adyen", "3-d secure|3ds"]
mechanisms: ["payment intent", "webhook signature"]
forms: [library, service]
problems: ["accept card payments python"]
topics: []
chosen: [stripe/stripe-python]     # cards the decision uses
scanned: 2026-10-15                # set by scan
```

The body has two sections: `## Landscape` (the options side by side) and `## Decision`.

### Card: `repos/<owner>__<repo>.md`

```yaml
id: jackwener/OpenCLI
repo: https://github.com/jackwener/OpenCLI
kind: cli                # skill | skill-pack | rules | mcp | cli | app | extension |
                         # library | framework | service | list | example | data
summary: "Turns websites into CLI commands through your logged-in Chrome"
license: Apache-2.0      # SPDX id, or none
stars: 30264             # at review time
pushed: 2026-10-13
created: 2026-03-14
branch: main
commit: b9213a15d63d     # the commit that was reviewed
reviewed: 2026-10-14
level: trial             # meta | peek | read | trial
watch: [src/daemon.ts, "clis/reddit/**"]   # upstream paths we depend on
aliases: [opencli]       # optional short names
uses:
  - project: ops
    need: browser-ops
    relation: adopt      # adopt | extend | derive | migrate | borrow | watch | reject
    where: tools/opencli
    note: "Reddit reads through its fetch adapters; our own adapter for comments"
```

The body follows the template for the card's family (agent-facing, software, other). The
template headings are suggestions; any Markdown is valid.

## Ledger: `ledger.jsonl`

One JSON object per line, append-only. The latest entry per (repo, project/need) is the
current verdict.

```json
{"date": "2026-10-15", "repo": "a/b", "project": "ops", "need": "browser-ops",
 "verdict": "skip", "level": "meta", "reason": "video downloader, not a browser driver",
 "stars": 1200, "pushed": "2026-09-30", "desc": "…", "scan": "20261015-001847", "by": "agent"}
```

Verdicts are `peeked`, `short`, `list`, `defer`, `skip` and `card`. A `skip` comes back in
results once the repo's stars reach twice the recorded count (and at least 200 more).

## Scan: `scans/<project>/<need>/<stamp>.json`

```json
{"id": "20261015-001847", "date": "2026-10-15", "project": "ops", "need": "browser-ops",
 "lenses": "EPMCQTRKNUG",
 "searches": [{"lens": "P", "kind": "repos", "query": "reddit xiaohongshu in:readme", "hits": 30}],
 "candidates": [{"repo": "a/b", "desc": "…", "stars": 1, "created": "…", "pushed": "…",
                 "license": "MIT", "lang": "Go", "topics": [], "archived": false, "fork": false,
                 "lenses": ["E", "P"], "fit": 2, "score": 9.1}]}
```

The search log is the proof of what was checked. Only the best 400 candidates are kept.
