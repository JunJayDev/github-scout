---
name: github-scout
description: Before you build, install or pick a tool, skill or library, find what GitHub already solved, with a quick lookup or the full flow that ends in a report.
license: MIT
metadata:
  improve-repo: JunJayDev/github-scout
  improve-path: skills/github-scout
---

# GitHub scout

Before building something, look at what others have built. This skill takes a goal from the
user's project, searches GitHub in English and Chinese, keeps the repositories whose effect
anyone can check, and writes a report for the coding agent: what exists, which two or three look
most promising for us and how to try each, and what is likely left to build. It never changes
the project, and it does not try repositories or choose one.

Trying and choosing come after the report, and only when the user asks. The project's coding
agent tries the two or three (stage 5, `github-scout-dig`), follows one as a whole and fills its
gaps from others with a reason each, then brings it in (stage 6, `github-scout-adopt`). The
registry records which repo went where, so `updates` can say when upstream changes the files we
took.

Effect comes first. A repo is a reference only when it shows what it does in a way anyone can
check (a live site, a package people download, screenshots, videos, posts outside the repo) and
has 50 stars or more, or the relaxed floor of its direction. An idea from each of a dozen repos
does not add up to a working whole: the coding agent follows one.

## What the user must give

A goal tied to a project or task, for example "make the product videos our agent renders cut
like an editor's". Without a goal there is nothing to compare against, so ask for one and wait.
Then what good looks like: two or three finished results to match, or checks anyone can run on
an output. Without it there is nothing to judge candidates by; propose it and confirm it with
the directions.

Run it inside the project's repository when there is one: the agent then reads our own code to
see what we already have. Without a local project it still runs; the user then says in a few
lines what exists today.

## Quick lookup (`github-scout quick`)

For a small question, run `github-scout quick` instead of the stages: before you build something,
install a tool or skill, or pick a library. It needs no registry, takes one to three minutes and
prints one ranked table with the scan's filters (lures, farmed installs, dead repos, too few
stars). A cheap model can run it. Steps and what to hand back: `references/quick.md`. When the
answer shapes the project, run the stages below.

## Stages

Each stage is its own skill and can run alone. This skill runs stages 1 to 4 and ends with the
report.

| stage | skill | does | output |
|---|---|---|---|
| 1 plan | `github-scout-plan` | reads our project, restates the goal, says what good looks like, picks the stage, writes search directions in English and Chinese | the question with its directions |
| 2 search | `github-scout-search` | searches along every direction; drops lures, farmed installs, dead repos and those with too few stars | ranked candidates |
| 3 triage | `github-scout-triage` | keeps the candidates with a verifiable effect and enough stars; says how each would be tried | a shortlist |
| 4 brief | `github-scout-brief` | compares with our project; writes what exists, the two or three to try first and how, what is left to build | the report for the coding agent |
| 5 dig | `github-scout-dig` | the coding agent tries the two or three, stops early on a dead end, chooses one to follow and names what fills its gaps | trials; the choice |
| 6 adopt | `github-scout-adopt` | the coding agent brings it into our project by its rules, and records it | the change in our project; an `adopted` entry on each card |

## Where it runs, and when to stop

- **Local agent with the command line** (Claude Code, Codex and others). Use the commands in
  each stage. After stage 1, show the user what good looks like and the directions, and **stop
  until they confirm**, unless they said not to stop. Then run stages 2 to 4 without stopping,
  and end with the report's path.
- **Cloud chat or no Python** (ChatGPT, Claude on the web). Follow each stage's "Without the
  command line" part and write one report file in the format of `references/report-format.md`.
  **Do not stop** between stages unless the user asked to confirm the directions. The local agent
  can take the report over with `github-scout import <report> --q <project>/<question>`.
- **Stages 5 and 6, `github-scout-dig` and `github-scout-adopt`,** run only when the user asks
  or hands the report to the coding agent: inside the project's repository, by that agent. A
  search run never includes them, and a cloud chat never runs them.

## Rules

- Never change the user's project, and never try a repo or choose the one to follow. The
  deliverable is the report.
- Trying, choosing and bringing it in are stages 5 and 6 (`github-scout-dig`, `github-scout-adopt`):
  the project's coding agent does them in the project's own repository, by the project's rules.
- List only repositories you have seen yourself: their page, the connector, or a search result
  that names them. Never invent names, stars or dates.
- Search every direction in English and in Chinese, with the words each community uses, and in
  any other language the user's audience needs.
- Judge the verifiable effect before code. **Strong:** a live site that answers, a package with
  real downloads, real installs. **Mid:** screenshots, GIFs or videos in the README, posts outside
  the repo (X, Bilibili, YouTube, blogs, Xiaohongshu). **Weak:** only a text description. A weak
  repo is `later` or `skip`, however good its idea.
- Stars: 50 by default. A direction (one entity or mechanism group) with fewer than 5 such repos
  shows its own repos down to 20 stars, then 10, never lower; the scan header says which
  directions were relaxed. Under the floor a repo is no reference unless you write why (an
  official organisation's new repo, say).
- The report names two or three to try first, each with how to try it (open its live site, run
  its own smallest example, or one short task from our project) and what to look for. The coding
  agent tries them, stops at the first wall, follows one as a whole and fills its gaps from others
  only with a reason each.
- Maintenance is a gate: no push in 3 months ranks far down; 6 months is set aside unless
  nothing maintained covers the need; 12 months is dropped. New and fast-growing helps finding,
  never picking: pick by effect, stars and fit.
- Leave out lures (game cheats, cracks, "Ultimate Trainer 2026") and install counts far beyond a
  repo's stars. Never download them.
- Licences, usage rights and prices are not part of the research: we look for references to
  follow. Leave them out of the searches and the report.
- Locally, every repo you looked at gets a verdict in the registry, so nobody reads it twice.
  Check the registry first: `github-scout find <words>`.

## The command

`github-scout` below means `python3 <this skill's folder>/scripts/github-scout.py`. The stage
skills sit next to this folder and use the same command.

- Needs Python 3.9+, a GitHub token (`GITHUB_TOKEN`, or a logged-in `gh`), and network access to
  api.github.com, codeload.github.com, skills.sh, registry.npmjs.org, api.npmjs.org and
  registry.modelcontextprotocol.io. `look` also sends one short request, without the token, to a
  repo's homepage and the demo links in its README, to see whether they answer.
- The registry (questions, cards for each repo, a ledger of verdicts) is created by the first
  `ask` in `~/.github-scout`. Set `GITHUB_SCOUT_STORE` or pass `--store DIR` to keep it elsewhere,
  for example inside a team repository.
- Writes go to the registry only. If the harness allows writes only inside the project, run the
  commands outside the sandbox or point the registry into the project.

| command | stage | does |
|---|---|---|
| `find WORDS…` | 1 | has anyone looked at this already? |
| `ask [P/]Q "goal" --stage S` | 1 | start a question; creates the registry and the project when missing |
| `scan P/Q --plan` / `scan P/Q` | 1 / 2 | show the searches / run them and print the ranked table, with any relaxed directions |
| `quick "need" -e … -m … -p … [--form F]` | 1 to 3 | a one-off lookup: no registry, one short table |
| `scan P/Q --add FILE\|URL` / `--expand LIST` | 2 | add links found elsewhere / expand an awesome list |
| `pick P/Q 1 4 h2 --rest "why"` | 3 | verdicts on table rows; under the star floor needs `--low-stars "why"` |
| `look --q P/Q a/b [--source]` | 3 / 5 | facts, activity, kind and the verifiable effect (tier and links) / download one commit and map the code |
| `note a/b --q P/Q --take T --results URL…` | 3, 4 | the repo's card: its verifiable effect, what it would do for us; `--trial "…"` records a trial (5) |
| `brief P/Q` | 4 | write the report for the coding agent |
| `adopt a/b --q P/Q --mode M --into PATHS` | 6 | record what came into the project from where; `updates` then watches it |
| `import REPORT --q P/Q` | any | take over a report from a cloud chat; every link is checked |
| `show`, `updates`, `site`, `check` | later | read a question or card; upstream changes; a web page; validate |

Formats: `references/store-format.md`. A worked example: `references/workflow.md`. How to judge
skills and software: `references/evaluation.md`.

## Improve this skill

This skill is open source (`metadata.improve-repo` in its header). When a run goes wrong because of the skill itself, not the user's input or the environment (a wrong or missing step, a command that fails, output that misleads, a case it should cover), fix it at the source instead of working around it.

Run `gh repo view <improve-repo> --json viewerPermission`. With WRITE, MAINTAIN or ADMIN:

1. Work in a clone of the repository, never in the installed copy, on a branch `improve/<short-slug>`.
2. Change the skill or its code, add a test (or an eval case) that fails without the change, and run the repository's checks.
3. Commit, push the branch and open a pull request: what you ran, what went wrong, the evidence, what changed. Do not merge it. Keep personal paths, tokens and account names out of the diff and the text.

With less permission, or without `gh`: tell the user what you found and offer the fix as a patch; open no pull request or issue unasked. If you cannot fix it now, record it: `scripts/report-problem.sh "<summary>"`.
