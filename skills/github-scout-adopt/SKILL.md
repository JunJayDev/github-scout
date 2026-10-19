---
name: github-scout-adopt
description: For the coding agent: bring the chosen repo into your project as a whole, and what fills its gaps, by its rules; record where.
license: MIT
---

# GitHub scout: adopt

Stage 6 of `github-scout`, and the only stage that changes the project. The project's coding
agent runs it inside the project's own repository, when the user asks for the integration,
after it tried the report's repos and chose one (`github-scout-dig`). Stages 1 to 5 never change
the project.

## Input

The report from `github-scout brief <q>`, and the choice from `github-scout-dig`: the main
reference (`backbone:` in the question file), at most one alternate, and each gap with where it
is filled from. The project's own AGENTS.md or CLAUDE.md, its tests and its conventions win over
anything in the report.

## Steps

1. **Pick a mode for each repo.** The main reference (the backbone) comes in whole, its own way:
   `depend`, `skill` or `tool`. `port`, `vendor` and `data` take one piece, for one of its gaps;
   say which gap in `--note`. Do not mix in what the report lists under Not recommended.

   | mode | what we do | how it is pinned and traced |
   |---|---|---|
   | `depend` | add it through the package manager | a pinned version |
   | `vendor` | copy files; local edits allowed | a line in each copied file, or a manifest beside them: repo, commit, source path; our edits listed |
   | `port` | rewrite the idea in our own code | one comment at the top of our file naming the upstream file |
   | `skill` | install an agent skill as it is | its folder unchanged, from the reviewed commit |
   | `tool` | call their CLI or app as it is from our scripts | a pinned version where we call it |
   | `data` | copy datasets, fonts, prompts or assets | repo, commit and source path beside them |

   Copy from the commit that was reviewed (the report's "reviewed at"), not from whatever is newest.
2. **Work the way the project works:** its branch or worktree rules, its style, its review. One
   commit per adopted repo where practical.
3. **Verify each step** against what good looks like and with the project's own tests. A step
   that cannot be verified is not recorded.
4. **Record** each adopted repo after its commit (below). A repo from the report you did not take
   is recorded with `github-scout note` and the reason, so the registry learns why.

## With the command line

```bash
github-scout adopt owner/backbone --q <project>/<question> --mode tool --into tools/video/render.sh --note "pinned v2.1"
github-scout adopt owner/repo --q <project>/<question> --mode vendor \
  --into tools/video/src/x.ts --from src/x.ts --note "gap: captions; kept the parser, dropped the CLI"
github-scout note other/repo --q <project>/<question> --take skip --note "<why we did not take it>"
```

- `--into`: our paths, comma-separated, read from the current directory; run elsewhere, they are
  read from the project's code path.
- `--from`: their files or folders we took, from the root of their repository. Each must exist at
  `--at` (a typo is refused). `updates` watches exactly these; leave it out when nothing was copied.
- `--at`: their commit; defaults to the card's reviewed commit.
- `--ours`: our commit; defaults to HEAD of the repository holding the first `--into` path, so
  run `adopt` after the commit.
- The same `--q` and `--into` again update the entry: `--from`, `--at` and `--note` left out keep
  what was recorded. `--drop` marks it dropped and keeps it.

The report's Adopt and record section has one such line per repo to try, ready to fill.
Afterwards `github-scout updates` lists adopted repos first, with the upstream commits that
touched the files we took. After updating our copy, run `adopt` again with `--at <their new commit>`.

## Without the command line (cloud chat)

A chat cannot change a local project. It hands its report over; back home, the project's coding
agent takes it in with `github-scout import`, tries and chooses (`github-scout-dig`), and runs
this stage. Without the command line, it records what it adopted (repo, commit, their files, our
files) at the end of the report file, under "Adopted".

A defect in this skill that stays unfixed: record it with `scripts/report-problem.sh "<summary>"`.
