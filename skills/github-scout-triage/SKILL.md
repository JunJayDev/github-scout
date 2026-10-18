---
name: github-scout-triage
description: Keep the repositories a search found that show results and have 50+ stars, tag them, and decide how each is read.
license: MIT
---

# GitHub scout: triage

Stage 3 of `github-scout`. Quality first: a repo goes on the shortlist only when it has results
we can look at and 50 stars or more. Then tag it, because different kinds are read in different
ways.

## Input

The candidates from `github-scout-search`.

## Check each candidate

- **Results:** what it has made that we can look at: films, galleries, sample outputs, case
  studies, benchmarks, test results, other projects that use it. Open them and hold them against
  what good looks like in the question. Nothing to look at: `later` (say what would change it)
  or `skip`, never the shortlist.
- **Stars:** under 50, no reference. An exception needs a written reason, such as an official
  organisation's repo released this week.
- **Kind:** skill or prompt pack · cli · mcp server · library · app · framework · example or
  template · awesome list · article or paper · official docs or hosted service.
- **Relevance:** could carry the whole goal (a backbone candidate) · fills one piece · not useful.
- **Route:** how stage 4 will try and read it.

| kind | route |
|---|---|
| skill, prompt pack, rules | try it on one short task; read SKILL.md, its references and scripts in full; judge the method and its safety |
| cli, mcp, library, app | try it on its own smallest example; then map the code and find the module that implements the mechanism |
| example, template | read only the files that show the technique |
| awesome list | expand it into candidates (`scan --expand`); never adopt a list |
| article, paper | take the idea and its evidence |
| official docs, hosted service | read the pages that answer a direction; note limits, cost and lock-in; list as another source |

Pick 3 to 8 for the shortlist: backbone candidates first, then repos that fill a piece. Only
repos with results and 50+ stars go on it. New and fast-growing helped find them; it does not
pick them: their results, stars and fit do.

## With the command line

```bash
github-scout look --q <q> owner/repo other/repo                      # facts, activity, kind, results to check; ~1.3k tokens each
github-scout pick <q> 1 4 7 h2 --rest "<why the rest do not help>"   # numbers from the table, h<#> from the rising list
github-scout pick <q> owner/repo --low-stars "<why it is an exception>"   # a repo under 50 stars
```

`look` lists the links in a README that look like results (demos, galleries, examples, videos):
open them before you pick. Every row you were shown and did not pick is recorded as skipped with
your reason. `pick` refuses a repo under 50 stars without `--low-stars`. Use `--later` for
promising but not now (no results yet, too few stars), `--list` for lists to expand. After picking, run
`github-scout scan <q> --lenses UG`: it follows the owners' stars and the links in the picked
READMEs, which find nothing before you pick.

## Without the command line (cloud chat)

Write section 3 of the report:
- a table of the shortlist: repo URL, kind, results (a link to what it made, or "none"), route,
  verdict (shortlist, later, skip), reason;
- one line on why the rest were left.

A repo without results, or under 50 stars, is `later` or `skip`, not `shortlist`.

This is the only table whose verdicts the local import records.

## Next

`github-scout-dig`.

A defect in this skill that stays unfixed: record it with `scripts/report-problem.sh "<summary>"`.
