---
name: github-scout-triage
description: Register and tag the repositories a search found, and decide how each one should be read.
license: MIT
---

# GitHub scout: triage

Stage 3 of `github-scout`. Different kinds of repositories are read in different ways, so tag
each one before reading.

## Input

The candidates from `github-scout-search`.

## Tag each candidate

- **Kind:** skill or prompt pack · cli · mcp server · library · app · framework · example or
  template · awesome list · article or paper · official docs or hosted service.
- **Relevance:** answers a direction directly · adjacent · not useful.
- **Route:** how stage 4 will read it.

| kind | route |
|---|---|
| skill, prompt pack, rules | read SKILL.md, its references and scripts in full; judge the method and its safety |
| cli, mcp, library, app | map the code and find the module that implements the mechanism; check the licence; if we would run it, try it on one real task |
| example, template | read only the files that show the technique |
| awesome list | expand it into candidates (`scan --expand`); never adopt a list |
| article, paper | take the idea and its evidence |
| official docs, hosted service | read the pages that answer a direction; note limits, cost and lock-in; list as another source |
| non-commercial licence, or none | idea only; never copy the code |

Pick 5 to 12 for the shortlist. Prefer repos that answer a direction directly, are young and
maintained, and come from different approaches; three variants of one idea teach less than three ideas.

## With the command line

```bash
github-scout pick <q> 1 4 7 h2 --rest "<why the rest do not help>"   # numbers from the table, h<#> from the rising list
github-scout look --q <q> owner/repo other/repo                      # facts, activity, kind; about 1.3k tokens each
```

Every row you were shown and did not pick is recorded as skipped with your reason. Use `--later`
for promising but not now, `--list` for lists to expand. After picking, run
`github-scout scan <q> --lenses UG`: it follows the owners' stars and the links in the picked
READMEs, which find nothing before you pick.

## Without the command line (cloud chat)

Write section 3 of the report:
- a table of the shortlist: repo URL, kind, route, verdict (shortlist, later, skip), reason;
- one line on why the rest were left.

## Next

`github-scout-dig`.

A defect in this skill that stays unfixed: record it with `scripts/report-problem.sh "<summary>"`.
