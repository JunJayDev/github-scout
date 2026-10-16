---
name: github-scout
description: Find what GitHub already solved for a goal in your project, and hand concrete suggestions to your coding agent.
license: MIT
---

# GitHub scout

Before building something, look at what others have built. This skill takes a goal from the
user's project, searches GitHub in English and Chinese, reads the repositories that matter,
and writes a brief for the coding agent: which ideas to take from whom, where in our project
they apply, and what is left to build ourselves. It never changes the project.

The ideas count more than the code. A coding agent writes code at will, but it never writes
an approach it did not think of.

## What the user must give

A goal tied to a project or task, for example "make the product videos our agent renders cut
like an editor's". Without a goal there is nothing to compare against, so ask for one and wait.

Run it inside the project's repository when there is one: the agent then reads our own code to
see what we already have. Without a local project it still runs; the user then says in a few
lines what exists today.

## Five stages

Each stage is its own skill and can run alone. This skill runs them in order.

| stage | skill | does | output |
|---|---|---|---|
| 1 plan | `github-scout-plan` | reads our project, restates the goal, picks the stage, writes search directions in English and Chinese | the question with its directions |
| 2 search | `github-scout-search` | searches along every direction; drops lures, farmed installs and dead repos | ranked candidates |
| 3 triage | `github-scout-triage` | registers and tags each candidate; decides how each one is read | a shortlist with a route per repo |
| 4 dig | `github-scout-dig` | reads inside the shortlisted repos | the ideas, with file paths |
| 5 brief | `github-scout-brief` | compares with our project, writes the answer and the hand-off | a brief for the coding agent |

## Where it runs, and when to stop

- **Local agent with the command line** (Claude Code, Codex and others). Use the commands in
  each stage. After stage 1, show the directions to the user and **stop until they confirm**,
  unless they said not to stop. Then run stages 2 to 5 without stopping.
- **Cloud chat or no Python** (ChatGPT, Claude on the web). Follow each stage's "Without the
  command line" part and write one report file in the format of `references/report-format.md`.
  **Do not stop** between stages unless the user asked to confirm the directions. The local agent
  can take the report over with `github-scout import <report> --q <project>/<question>`.

## Rules

- Never change the user's project. The deliverable is the brief; the coding agent does the work.
- List only repositories whose page you opened. Never invent names, stars or dates.
- Search every direction in English and in Chinese, with the words each community uses.
- Maintenance decides more than stars: no push in 3 months ranks far down, 6 months is set
  aside, 12 months is dropped. New and moving beats old and famous.
- Leave out lures (game cheats, cracks, "Ultimate Trainer 2026") and install counts far beyond a
  repo's stars. Never download them.
- A repo with a non-commercial licence or none: take the idea, not the code.
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
| `pick P/Q 1 4 h2 --rest "why"` | 3 | verdicts on table rows |
| `look --q P/Q a/b [--source]` | 3 / 4 | facts, activity and kind / download one commit and map the code |
| `note a/b --q P/Q --take T --idea "…"` | 4 | the repo's card: the idea first, what we take |
| `brief P/Q` | 5 | write the hand-off for the coding agent |
| `import REPORT --q P/Q` | any | take over a report from a cloud chat; every link is checked |
| `show`, `updates`, `site`, `check` | later | read a question or card; upstream changes; a web page; validate |

Formats: `references/store-format.md`. A worked example: `references/workflow.md`. How to judge
skills and software: `references/evaluation.md`.

A defect in this skill that stays unfixed: record it with `scripts/report-problem.sh "<summary>"`.
