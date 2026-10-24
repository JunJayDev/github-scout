---
name: github-scout-brief
description: "Check independent feedback on the top two or three repos, then write what to try first and how for the coding agent."
license: MIT
metadata:
  improve-repo: JunJayDev/github-scout
  improve-path: skills/github-scout-brief
---

# GitHub scout: brief

Stage 4 of `github-scout`, and its last. Turn the shortlist into a report for the agent that
will change the code: what exists, which two or three to try first and how, what is likely left
to build. Do not try them, choose one or change the project yourself: the coding agent tries and
chooses after the report, when the user asks.

## Input

The shortlist from `github-scout-triage`, and our project: its code when there is a local
repository, otherwise what the user said exists.

## Steps

1. **Look at our side.** Read the part of our code each candidate would touch, so the report can
   say how it relates to our project: replaces a module, plugs into one, or needs one built.
2. **Pick two or three to try first:** the ones whose stated capabilities and examples fit what
   good looks like and our project, with enough stars. Prefer one that could carry the whole
   goal. If none qualifies, say so and which searches show it; then the answer is to build, and why.
   **Before recommending each, run one focused independent search outside its repository.**
   Search the exact project name or `owner/repo` with terms for usage, review, recommendation,
   output or problems in English and Chinese. Open the relevant hits and check they refer to
   this repository, not a namesake. Look for real usage experiences, third-party recommendations,
   concrete outputs and negative feedback. The author's promotion, reposts of the same announcement
   and directory listings alone do not count as independent usage. Use x-scout for X when
   available; otherwise record the X access limit and use other sources.
   Keep this bounded to the two or three recommendations; do not audit every candidate or chase
   a quota of positive reviews. Record what was searched, a short finding with source links and
   material problems. If nothing independent was found, write "no independent usage feedback
   found"; if tools were unavailable, write "not checked" and why. Neither alone disqualifies a
   repo. Reconsider a recommendation when feedback reveals an actual mismatch; check any
   replacement in the same way. Actual output is verified in the later trial.
3. **Say how to try each one,** the cheapest way that shows whether it reaches what good looks
   like: open its live site; or run its own smallest example (the command from its README); or one
   short task from our project. Then what to look for in the output, against what good looks
   like.
4. **Answer in one paragraph:** what exists, which two or three look most promising for us and
   why, what is likely left to build.
5. **List the candidates** in a table: repo, kind, stars, last push, project evidence (a brief observation and
   links, if available), what it does for our goal, how it relates to our project.
6. **Not recommended:** the rest you looked at closely, one line each with the reason, so the
   coding agent leaves them out.
7. **What was searched:** the directions, the coverage, and every direction whose star threshold
   was relaxed (from the scan header).

## With the command line

Note each repo to try first, with what it would do for us. Optionally add project evidence or
independent feedback links with `--results`; summarize the feedback in `--note`:

```bash
github-scout note owner/repo --q <q> --take use|adapt|learn --results <project evidence or independent feedback links> \
  --note "<what it does for our goal; independent feedback or none found>" --where "<where it would land in our project>"
```

`note` keeps the star floor (`--low-stars "<why>"` for an exception). Links are optional and
carry no automatic quality grade; no evidence exception is needed. The take is your expectation;
the coding agent settles it after a trial.

Then write the answer into the question file printed by `github-scout show <q>`, in these
sections: In one paragraph; Candidates; Try first; Not recommended; and anything about the web or
X pass under Searched. Under Try first, put the independent feedback and source links beside each
recommendation, including "no independent usage feedback found" or "not checked" when applicable.
Record the independent queries and access limits under Searched. Leave Trials and choice to the coding agent. In its frontmatter set
`status: answered` and `picked:` (the repos to try first). Leave `backbone:` and `alternate:`
empty: the coding agent sets them after trying.

```bash
github-scout check            # warns when a repo to try lacks enough stars
github-scout brief <q>        # writes the report: the answer, the cards' facts, the coverage of the scans
```

Give the user the report's path, to hand to the coding agent. The report tells it how to try,
choose and record: one `github-scout note --trial` line and one adopt line per repo to try. The
project is not touched.

## Without the command line (cloud chat)

Write section 4 of the report (`../github-scout/references/report-format.md`): the paragraph,
the candidate table, Try first (including the independent feedback for each recommendation), the part for the coding agent, Not recommended and what was
searched. Then section 5, what you could not verify. Offer the whole report as one file to
download. To take it over locally:

```bash
github-scout import report.md --q <project>/<question>
```

Back home, the project's coding agent tries the repos under Try first, chooses one to follow and
brings it in; a chat never runs code or changes the project.

## Improve this skill

This skill is open source (`metadata.improve-repo` in its header). When a run goes wrong because of the skill itself, not the user's input or the environment (a wrong or missing step, a command that fails, output that misleads, a case it should cover), fix it at the source instead of working around it.

Run `gh repo view <improve-repo> --json viewerPermission`. With WRITE, MAINTAIN or ADMIN:

1. Work in a clone of the repository, never in the installed copy, on a branch `improve/<short-slug>`.
2. Change the skill or its code, add a test (or an eval case) that fails without the change, and run the repository's checks.
3. Commit, push the branch and open a pull request: what you ran, what went wrong, the evidence, what changed. Do not merge it. Keep personal paths, tokens and account names out of the diff and the text.

With less permission, or without `gh`: tell the user what you found and offer the fix as a patch; open no pull request or issue unasked. If you cannot fix it now, record it: `scripts/report-problem.sh "<summary>"`.
