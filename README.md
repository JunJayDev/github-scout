# reuse-first

**Agents know a lot, then search the web like a newcomer. reuse-first teaches them where good
ideas live on GitHub, how to recognise them, and to remember what they have seen.**

It is an agent skill with a small command-line tool. Before an agent builds a tool, a pipeline
or an integration, it writes down the question (the result we want, and how far our own work
has got), searches GitHub in dozens of targeted ways, reads the few repositories that matter,
and writes an answer: which ideas, practices or parts to take from whom, and what we still
have to build. Every verdict goes into a shared registry, so the next agent starts from it.

## Why

Agents rebuild things that already exist. Usually the search is the problem, not laziness.

In one real case, a project needed to read and post on Reddit, X and Xiaohongshu through a
logged-in browser. Agents searched for "social media automation" and "自媒体 运营" and found
old bots and tutorials, so they started writing a scraper. The right tool was a
30,000-star project created that year. Its description reads "Make any website into CLI &
use your logged-in browser by AI agent", and none of the agents' words are in it. A person
found it on X.

On that same question, GitHub repository search gives these results:

| query | where the right tool lands |
|---|---|
| `social media automation` | not in the top 8 |
| `自媒体 运营` | not in the top 8 |
| `xiaohongshu` | not in the top 8 |
| `"reddit xiaohongshu" in:readme` (two concrete platforms) | **#1** |
| `"logged-in browser"` (how it works) | **#1** |
| `topic:browser-automation created:>2026-01-01` | **#2** |

Good projects describe themselves with concrete nouns and mechanisms, not with the problem a
newcomer types. reuse-first writes those queries for you from a short vocabulary you define
for each question, runs them all, and merges the results. On this question, a full scan found
1,237 candidates, dropped the unmaintained ones (801 left) and ranked the tool ninth. The same
top ten held several closely related projects the team had never heard of, one with 97k stars.

## What it does differently

- **The question comes first.** "Find a video tool" and "make our product videos cut like an
  editor's, with an agent doing the work" find different repositories. A question also carries
  its stage (`idea`, `prototype`, `working`, `polishing`), because what is worth borrowing depends
  on how far you are: framing and approach early on, parameters and edge cases later.
- **The output is an answer, not a list.** A table of twenty repositories leaves all the work
  to you. The answer says what to take from whom, compares it with the code you already have,
  and names the part nobody covers.
- **Ideas before code.** An agent writes code at will; an approach it never thought of, it never
  writes. Cards start with the idea: the design decision, where it lives, why it is not obvious.
- **New and maintained beats old and famous.** Ranking is relevance first, then whether the repo
  is young and moving, and star counts last. No push in 3 months ranks far down, 6 months is hidden,
  12 months is dropped. Searches ask GitHub for maintained repos only, so no slot is wasted.
- **Searches through 14 lenses**: entities, entity pairs in READMEs, mechanisms, combinations,
  problem phrases, topics, the last 12 months, new repos rising fast in your form (found without
  any of your words), `SKILL.md` files, skills.sh (with install counts),
  the official MCP registry, npm, the stars of builders you trust, and links from repos you picked.
  Links found on the web or X and awesome lists feed into the same ranking.
- **Searches in Chinese as much as in English.** In real runs, Chinese projects supplied half of
  the repositories picked, and they describe themselves in Chinese. Each question lists its
  languages (`langs`, default `[en, zh]`); every vocabulary group should hold a term in each, the
  name those users write (`小红书|xhs|红书`, `去AI味|活人感|人味`), not a translation. Pairs and
  combinations are built within one language, the other lenses give each language a fair share
  of their searches, and `check` warns about a group with no term in a listed language.
- **Remembers.** Every verdict is recorded with its reason. Each card keeps the commit it was
  reviewed at and the upstream paths you depend on; `updates` shows only what changed there.

## Install

Requirements: Python 3.9+ (standard library only) and a GitHub token, either in
`GITHUB_TOKEN` or from a logged-in [`gh`](https://cli.github.com/) CLI. Network: api.github.com,
codeload.github.com, skills.sh, registry.modelcontextprotocol.io and registry.npmjs.org.

**Claude Code plugin**

```
/plugin marketplace add <owner>/reuse-first
/plugin install reuse-first@reuse-first
```

**Any agent that reads skills** (Claude Code, Codex and others): copy `skills/reuse-first/`
into your agent's skills directory, for example `~/.claude/skills/` or `.agents/skills/`. The
folder is self-contained. The agent runs `python3 scripts/reuse-first.py <command>` from it.

**The CLI on its own**

```bash
pipx install git+https://github.com/<owner>/reuse-first
# or: uv tool install git+https://github.com/<owner>/reuse-first
```

## Quick start

```bash
reuse-first init ~/oss-registry --lang en && export REUSE_FIRST_STORE=~/oss-registry
reuse-first new-project shop --name "Shop backend" --code ~/code/shop
reuse-first ask shop/payments "Take card payments with 3-D Secure from our Python service" --stage prototype
# edit projects/shop/questions/payments.md: what we have, what is not good enough, the vocabulary
reuse-first scan shop/payments --plan     # the searches, no network
reuse-first scan shop/payments            # ~150 searches, about five minutes, ranked table
reuse-first pick shop/payments 1 3 8 --rest "not payments"
reuse-first look --q shop/payments stripe/stripe-python
reuse-first look stripe/stripe-python --source
reuse-first note stripe/stripe-python --q shop/payments --take use --where services/billing
# write the answer in the question file, then:
reuse-first check && reuse-first site     # INDEX.md and site/index.html
```

Later: `reuse-first find "3-d secure"` (has anyone looked at this?), `reuse-first updates`
(what changed upstream since review), `updates --diff <repo>`, `updates --done <repo>`.

The full procedure for agents is in [`skills/reuse-first/SKILL.md`](skills/reuse-first/SKILL.md),
with a [worked example](skills/reuse-first/references/workflow.md) and the
[evaluation rubric](skills/reuse-first/references/evaluation.md).

## The registry

A directory of Markdown and JSON, best kept in git so several agents and machines share it:

```
projects/<project>/project.md            what the project is and where its code is
projects/<project>/questions/<q>.md      the question, its stage, its vocabulary, and the answer
repos/<owner>__<repo>.md                 one card per repository looked at closely
ledger.jsonl                             every verdict, append-only
scans/<project>/<q>/<stamp>.json         what each search ran and found
INDEX.md, site/index.html                generated overviews
```

One repository has one card, whichever projects use it. Each records what it takes: `use`,
`adapt`, `learn`, `later` or `skip`. Templates come in English or Chinese (`init --lang zh`).
The format is specified in [`references/store-format.md`](skills/reuse-first/references/store-format.md).

## Tell your agents

Add [`examples/AGENTS.snippet.md`](examples/AGENTS.snippet.md) to your `AGENTS.md` or
`CLAUDE.md`. The skill tells an agent how to search. The snippet makes searching a rule
before building.

## What it costs

| step | tokens the agent reads |
|---|---|
| `find` in the registry | a few hundred |
| `scan` table, 40 rows | ~2k (the searches cost API calls, not tokens) |
| `look`, per repo | ~1.3k |
| reading source | whatever the size map says you need, usually a few files |

GitHub allows 30 searches a minute and 10 code searches a minute with a token. A scan
throttles itself (also across processes sharing a registry) and takes a few minutes.

## Limits

- It sees public GitHub, npm, skills.sh, the MCP registry, and whatever you `scan --add`. GitLab, Codeberg, PyPI-only and
  closed-source options need the web pass described in the skill.
- GitHub search returns at most 1,000 results per query; the tool reads the top 30 of each.
- A clean scan proves nothing is missing only for the sources checked. The scan file lists them.
- Ranking is a heuristic. The `fit` column and the lens letters show why each row is there.

## Related projects

"Search before you build" skills are common. Most of them guide one search and end at one
decision. reuse-first keeps going after that: it remembers every verdict, tracks the repos you
chose, and makes the next search start from what is already known.

- [ECC `search-first`](https://github.com/affaan-m/ECC) (the most-installed
  skill of this kind on skills.sh), [`reuse-before-build`](https://github.com/Ai-Eastern/reuse-before-build)
  and [`oss-scout`](https://github.com/Saeyeon-developer/oss-scout): research-then-decide
  workflows for one task at a time. They work well alongside a registry.
- [`deja-vu`](https://github.com/vishnujayvel/deja-vu): keeps an append-only log of decisions
  with review dates. It is the closest in spirit, but it records decisions, not repositories, and
  revalidation is manual.
- [`patent`](https://github.com/r14dd/patent): from one plain-English idea, checks 19 package
  registries plus GitHub and Hacker News with semantic ranking. Good for "has this tool been built?".
- [`neuroarxiv`](https://github.com/UditAkhourii/neuroarxiv): checks arXiv papers before an
  agent designs something new. It covers papers; reuse-first covers code.
- [repomix](https://github.com/yamadashy/repomix) (`look --source --pack`), DeepWiki and gitingest
  help with reading a large codebase after `fetch`.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Tests run
offline: `python -m unittest discover -s tests`.

## License

MIT. See [LICENSE](LICENSE).
