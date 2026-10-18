---
name: github-scout
description: Find what GitHub already solved for a goal in your project, and hand concrete suggestions to your coding agent.
license: MIT
---

# GitHub scout

Before building something, look at what others have built. This skill takes a goal from the
user's project, searches GitHub in English and Chinese, keeps the repositories that show what
they made, tries the best two or three, and writes a brief for the coding agent: which one to
follow as a whole, what fills its gaps and from where, and what is left to build ourselves. It
never changes the project.

Stage 6, `github-scout-adopt`, is where the brief reaches the code: when the user asks, the
project's coding agent brings it in by the project's own rules, and the registry records which
repo went where, so `updates` can say when upstream changes the files we took.

Results come first. A repo is a reference only when it shows what it made (films, galleries,
sample outputs, benchmarks, projects using it), has 50 stars or more, and runs for us in a short
trial. The answer follows one such repo as a whole and takes from others only what it lacks: an
idea from each of a dozen repos does not add up to a working whole.

## What the user must give

A goal tied to a project or task, for example "make the product videos our agent renders cut
like an editor's". Without a goal there is nothing to compare against, so ask for one and wait.
Then what good looks like: two or three finished results to match, or checks anyone can run on
an output. Without it there is nothing to judge candidates by; propose it and confirm it with
the directions.

Run it inside the project's repository when there is one: the agent then reads our own code to
see what we already have. Without a local project it still runs; the user then says in a few
lines what exists today.

## Stages

Each stage is its own skill and can run alone. This skill runs stages 1 to 5 in order.

| stage | skill | does | output |
|---|---|---|---|
| 1 plan | `github-scout-plan` | reads our project, restates the goal, says what good looks like, picks the stage, writes search directions in English and Chinese | the question with its directions |
| 2 search | `github-scout-search` | searches along every direction; drops lures, farmed installs, dead repos and those under 50 stars | ranked candidates |
| 3 triage | `github-scout-triage` | keeps the candidates with results to look at and 50+ stars; decides how each one is read | a shortlist with a route per repo |
| 4 dig | `github-scout-dig` | tries the best two or three, stops early on a dead end, reads the code of the one to follow | trial runs; the backbone and its gaps |
| 5 brief | `github-scout-brief` | compares with our project; writes the answer (one backbone, what fills its gaps) and the hand-off | a brief for the coding agent |
| 6 adopt | `github-scout-adopt` | brings the backbone in whole, and what fills its gaps, into our project by its rules, and records it | the change in our project; an `adopted` entry on each card |

## Where it runs, and when to stop

- **Local agent with the command line** (Claude Code, Codex and others). Use the commands in
  each stage. After stage 1, show the user what good looks like and the directions, and **stop
  until they confirm**, unless they said not to stop. Then run stages 2 to 5 without stopping.
- **Cloud chat or no Python** (ChatGPT, Claude on the web). Follow each stage's "Without the
  command line" part and write one report file in the format of `references/report-format.md`.
  **Do not stop** between stages unless the user asked to confirm the directions. The local agent
  can take the report over with `github-scout import <report> --q <project>/<question>`.
- **Stage 6, `github-scout-adopt`,** runs only when the user asks for the integration or hands
  over the brief: inside the project's repository, by its coding agent. A search run never
  includes it, and a cloud chat never runs it.

## Rules

- Never change the user's project. The deliverable is the brief; the coding agent does the work.
- That work is stage 6, `github-scout-adopt`: stages 1 to 5 never change the project; the coding
  agent adopts in the project's own repository, by the project's rules, and records each repo it
  took from.
- List only repositories you have seen yourself: their page, the connector, or a search result
  that names them. Never invent names, stars or dates.
- Search every direction in English and in Chinese, with the words each community uses, and in
  any other language the user's audience needs.
- Judge results before code. A repo with nothing to look at is `later` or `skip`, however good
  its idea. Under 50 stars a repo is no reference unless you write why (an official
  organisation's new repo, say).
- Try the best two or three before choosing, skills too: install, run its own smallest example
  or one short real task. Stop at the first wall instead of spending the day on it.
- One backbone, followed as a whole, and at most one alternate. Other repos fill only the gaps
  you name, each with what is missing, where it comes from and why.
- Maintenance is a gate: no push in 3 months ranks far down; 6 months is set aside unless
  nothing maintained covers the need; 12 months is dropped. New and fast-growing helps finding,
  never picking: pick by results, stars, the trial and fit.
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
  api.github.com, codeload.github.com, skills.sh, registry.npmjs.org and
  registry.modelcontextprotocol.io.
- The registry (questions, cards for each repo, a ledger of verdicts) is created by the first
  `ask` in `~/.github-scout`. Set `GITHUB_SCOUT_STORE` or pass `--store DIR` to keep it elsewhere,
  for example inside a team repository.
- Writes go to the registry only. If the harness allows writes only inside the project, run the
  commands outside the sandbox or point the registry into the project.

| command | stage | does |
|---|---|---|
| `find WORDS…` | 1 | has anyone looked at this already? |
| `ask [P/]Q "goal" --stage S` | 1 | start a question; creates the registry and the project when missing |
| `scan P/Q --plan` / `scan P/Q` | 1 / 2 | show the searches / run them and print the ranked table |
| `scan P/Q --add FILE\|URL` / `--expand LIST` | 2 | add links found elsewhere / expand an awesome list |
| `pick P/Q 1 4 h2 --rest "why"` | 3 | verdicts on table rows; under 50 stars needs `--low-stars "why"` |
| `look --q P/Q a/b [--source]` | 3 / 4 | facts, activity, kind and results to check / download one commit and map the code |
| `note a/b --q P/Q --take T --results URL… --trial "…"` | 4 | the repo's card: results, our trial, what we take |
| `brief P/Q` | 5 | write the hand-off for the coding agent |
| `adopt a/b --q P/Q --mode M --into PATHS` | 6 | record what came into the project from where; `updates` then watches it |
| `import REPORT --q P/Q` | any | take over a report from a cloud chat; every link is checked |
| `show`, `updates`, `site`, `check` | later | read a question or card; upstream changes; a web page; validate |

Formats: `references/store-format.md`. A worked example: `references/workflow.md`. How to judge
skills and software: `references/evaluation.md`.

A defect in this skill that stays unfixed: record it with `scripts/report-problem.sh "<summary>"`.
