---
name: github-scout-triage
description: Keep the repositories a search found that show a verifiable effect and enough stars, tag them, and say how each would be tried.
license: MIT
metadata:
  improve-repo: JunJayDev/github-scout
  improve-path: skills/github-scout-triage
---

# GitHub scout: triage

Stage 3 of `github-scout`. Quality first: a repo goes on the shortlist only when anyone can check
what it does and it has enough stars. Then tag it, because different kinds are tried and read in
different ways.

## Input

The candidates from `github-scout-search`.

## Check each candidate

- **Verifiable effect.** Most repos show what they do outside the repo, so look there first, and
  hold what you find against what good looks like in the question:
  - **strong:** a live site that answers (the repo's homepage, a demo, app or playground link), a
    published package with real downloads or an app in a store, real installs (skills.sh);
  - **mid:** screenshots, GIFs or videos in the README (not badges, logos or icons), posts outside
    the repo that show it working (X, Bilibili, YouTube, blogs, Xiaohongshu), projects that use it;
  - **weak:** only a text description, however long the README.

  Weak: `later` (say what would change it) or `skip`, never the shortlist.
- **Stars:** 50, or the relaxed floor of its direction (20, then 10, when the direction has fewer
  than 5 repos at 50+; the scan header names them). Under the floor, no reference: an exception
  needs a written reason, such as an official organisation's repo released this week.
- **Kind:** skill or prompt pack · cli · mcp server · library · app · framework · example or
  template · awesome list · article or paper · official docs or hosted service.
- **Relevance:** could carry the whole goal · fills one piece · not useful.
- **How it would be tried:** the coding agent tries the report's two or three after the report;
  write down now how each kind is tried, so the report can say it.

| kind | how it is tried and read |
|---|---|
| skill, prompt pack, rules | install it, give it one short task; read SKILL.md, its references and scripts in full; judge the method and its safety |
| cli, mcp, library, app | open its live site if it has one; else run its own smallest example, or one short task from our project; then map the code |
| example, template | read only the files that show the technique |
| awesome list | expand it into candidates (`scan --expand`); never adopt a list |
| article, paper | take the idea and its evidence |
| official docs, hosted service | read the pages that answer a direction; note limits, cost and lock-in; list as another source |

Pick 3 to 8 for the shortlist: repos that could carry the whole goal first, then repos that fill
a piece. Only repos with a mid or strong effect and enough stars go on it. New and fast-growing
helped find them; it does not pick them: their effect, stars and fit do.

## With the command line

```bash
github-scout look --q <q> owner/repo other/repo                      # facts, activity, kind, verifiable effect; ~1.3k tokens each
github-scout pick <q> 1 4 7 h2 --rest "<why the rest do not help>"   # numbers from the table, h<#> from the rising list
github-scout pick <q> owner/repo --low-stars "<why it is an exception>"   # a repo under the star floor
```

`look` prints the verifiable effect: its tier, then what to open. It checks with one short
request whether the homepage and the README's demo links answer, asks npm for a package's
downloads last month, counts the installs the scan recorded (with `--q`), and lists the images,
GIFs and videos in the README without badges, logos or icons. Open them before you pick. Posts
outside the repo it cannot find: search for them (`<repo name>` on X, Bilibili, YouTube) when
the tier is weak.

Every row you were shown and did not pick is recorded as skipped with your reason. Numbers refer
to the table printed last (`scan --show --all` numbers hidden rows too). `pick` takes a row shown
by a relaxed direction as is, and records why; a repo under its floor needs `--low-stars`. Use
`--later` for promising but not now (a weak effect, too few stars), `--list` for lists to expand.
After picking, run `github-scout scan <q> --lenses UG`: it follows the owners' stars and the links
in the picked READMEs, which find nothing before you pick.

## Without the command line (cloud chat)

Write section 3 of the report:
- a table of the shortlist: repo URL, kind, verifiable effect (tier and a link to it, or "weak"),
  how it would be tried, verdict (shortlist, later, skip), reason;
- one line on why the rest were left.

A weak repo, or one under the star floor, is `later` or `skip`, not `shortlist`.

This is the only table whose verdicts the local import records.

## Next

`github-scout-brief`.

## Improve this skill

This skill is open source (`metadata.improve-repo` in its header). When a run goes wrong because of the skill itself, not the user's input or the environment (a wrong or missing step, a command that fails, output that misleads, a case it should cover), fix it at the source instead of working around it.

Run `gh repo view <improve-repo> --json viewerPermission`. With WRITE, MAINTAIN or ADMIN:

1. Work in a clone of the repository, never in the installed copy, on a branch `improve/<short-slug>`.
2. Change the skill or its code, add a test (or an eval case) that fails without the change, and run the repository's checks.
3. Commit, push the branch and open a pull request: what you ran, what went wrong, the evidence, what changed. Do not merge it. Keep personal paths, tokens and account names out of the diff and the text.

With less permission, or without `gh`: tell the user what you found and offer the fix as a patch; open no pull request or issue unasked. If you cannot fix it now, record it: `scripts/report-problem.sh "<summary>"`.
