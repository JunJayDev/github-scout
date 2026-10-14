# reuse-first

**Make coding agents look for existing open-source projects before they build, and remember
what they found.**

reuse-first is an agent skill with a small command-line tool. Before an agent writes a new
tool, pipeline or integration, it searches GitHub in dozens of cheap, targeted ways and ranks
the results without reading them. It then reads the source of the few that matter and records
a verdict for every repository it looked at. The registry is shared, so the next agent, on the
next project, starts from those verdicts instead of searching again.

## Why

Agents rebuild things that already exist. Usually the search is the problem, not laziness.

In one real case, a project needed to read and post on Reddit, X and Xiaohongshu through a
logged-in browser. Agents searched for "social media automation" and "自媒体 运营" and found
old bots and tutorials, so they started writing a scraper. The right tool was a
30,000-star project created that year. Its description reads "Make any website into CLI &
use your logged-in browser by AI agent", and none of the agents' words are in it. A person
found it on X.

On that same need, GitHub repository search gives these results:

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
for each need, runs them all, and merges the results. On this need, a full scan put the tool
in the top 10 of 1,237 candidates. The same top 30 held several closely related projects the
team had never heard of, one of them with 97k stars.

## What it does

- **Searches through 13 lenses**: entities, entity pairs in READMEs, mechanisms, combinations,
  problem phrases, topics, the last 12 months, `SKILL.md` files, npm, the stars of builders
  you trust, links from the repos you already use, links you found on the web or X, and
  awesome lists.
- **Ranks without reading.** A `fit` score counts how many of your terms appear in a repo's
  own name, description and topics, so huge READMEs that mention everything sink. Awesome
  lists go to a separate line, as sources to expand.
- **Reads in steps**: metadata table (~25 tokens a row) → API digest (~1.2k tokens) → source
  of the relevant parts only. The digest includes a size map in tokens.
- **Treats skills and software differently.** An agent skill is judged on its method and its
  safety. A tool or library is judged on fit, maturity, permissions and exit cost, and adopted
  through an explicit ladder (use as is → configure → extend → wrap → contribute → fork → build).
- **Keeps a ledger.** Every verdict is recorded with its reason, including "skipped from the
  table". Nobody re-reads a repo unless it has grown a lot since.
- **Tracks upstream.** Each card records the commit it was reviewed at and the paths you depend
  on. `outdated` shows what changed since, and `diff` prints only those paths.

## Install

Requirements: Python 3.9+ (standard library only) and a GitHub token, either in
`GITHUB_TOKEN` or from a logged-in [`gh`](https://cli.github.com/) CLI.

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
reuse-first init ~/oss-registry && export REUSE_FIRST_STORE=~/oss-registry
reuse-first new-project shop --name "Shop backend"
reuse-first new-need shop/payments --want "Take card payments with 3-D Secure from Python"
# edit projects/shop/needs/payments.md: entities, mechanisms, forms, problems
reuse-first plan shop/payments            # the searches, no network
reuse-first scan shop/payments            # ~70 searches, 2–4 minutes, ranked table
reuse-first triage shop/payments --short 1 3 8 --rest "not payments"
reuse-first peek --need shop/payments stripe/stripe-python
reuse-first fetch stripe/stripe-python    # source + size map
reuse-first card stripe/stripe-python --need shop/payments --relation adopt \
  --where services/billing --watch "stripe/_payment_intent.py"
reuse-first index && reuse-first check
```

Later on:

```bash
reuse-first find "3-d secure"             # has anyone looked at this?
reuse-first outdated --project shop       # what changed upstream since review
reuse-first diff stripe/stripe-python     # only the watched paths
reuse-first bump stripe/stripe-python
```

The full procedure for agents is in [`skills/reuse-first/SKILL.md`](skills/reuse-first/SKILL.md),
with a [worked example](skills/reuse-first/references/workflow.md) and the
[evaluation rubric](skills/reuse-first/references/evaluation.md).

## The registry

A directory of Markdown and JSON, best kept in git so several agents and machines share it:

```
projects/<project>/project.md          what the project is; its license and platform rules
projects/<project>/needs/<need>.md     one capability: search vocabulary, landscape, decision
repos/<owner>__<repo>.md               one card per reviewed repository
ledger.jsonl                           every verdict, append-only
scans/<project>/<need>/<stamp>.json    what each search ran and found
INDEX.md                               generated overview
```

One repository has one card, whichever projects use it. Each project records its own
relation to it: `adopt`, `extend`, `derive`, `migrate`, `borrow`, `watch` or `reject`. The
format is specified in [`references/store-format.md`](skills/reuse-first/references/store-format.md).

## Tell your agents

Add [`examples/AGENTS.snippet.md`](examples/AGENTS.snippet.md) to your `AGENTS.md` or
`CLAUDE.md`. The skill tells an agent how to search. The snippet makes searching a rule
before building.

## What it costs

| step | tokens the agent reads |
|---|---|
| `find` in the registry | a few hundred |
| `scan` table, 40 rows | ~2k (the searches themselves cost API calls, not tokens) |
| `peek`, per repo | ~1.2k |
| reading source | whatever the size map says you need, usually a few files |
| a full landscape for one need | ~15–25k |

GitHub allows 30 searches a minute and 10 code searches a minute with a token. A scan
throttles itself and takes 2–4 minutes.

## Limits

- It sees public GitHub, npm, and whatever you `ingest`. GitLab, Codeberg, PyPI-only and
  closed-source options need the web pass described in the skill.
- GitHub search returns at most 1,000 results per query; the tool reads the top 30 of each.
- A clean scan proves nothing is missing only for the sources checked. The scan file lists them.
- Ranking is a heuristic. The `fit` column and the lens letters show why each row is there.

## Related projects

- [`patent`](https://github.com/r14dd/patent): from one plain-English idea, checks 19
  package registries plus GitHub and Hacker News, ranks the matches semantically and gives a
  crowded/open verdict. Good for "has this tool been built?". It does not keep a registry,
  track upstream, or separate skills from software.
- [`neuroarxiv`](https://github.com/UditAkhourii/neuroarxiv): a skill that checks arXiv
  papers before an agent designs something new. It covers research papers; reuse-first covers
  code.
- Repo-to-prompt tools (repomix, gitingest, code2prompt) and DeepWiki fit well after `fetch`,
  when you need to read a large codebase quickly.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md). Tests run
offline: `python -m unittest discover -s tests`.

## License

MIT. See [LICENSE](LICENSE).
