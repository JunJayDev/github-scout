---
name: github-scout-brief
description: Choose one repository to follow as a whole, name what fills its gaps, and hand off a brief without changing the project.
license: MIT
---

# GitHub scout: brief

Stage 5 of `github-scout`. Turn the trials and findings into one plan for our project, and hand
it to the agent that will change the code. Do not change the project yourself.

## Input

The trials and findings from `github-scout-dig`, and our project: its code when there is a local
repository, otherwise what the user said exists.

## Steps

1. **Name the backbone:** the one repo whose way we follow as a whole, from dig's trials, and at
   most one alternate. Say why it passed: its results (links), its stars, our trial. If none
   passed, say so and which searches show it; then the answer is to build, and why.
2. **List the gaps:** what the backbone does not do for us. For each: what is missing, where it
   is filled from (another repo and file, or our own code), and why that source.
3. **Compare** the backbone with our code. Read the part of our code each step touches. Write a
   table:

   | we have | the backbone does | the difference | take it or not |
   |---|---|---|---|

4. **Answer in one paragraph:** which repo to follow and why, what fills its gaps, what is left
   to build.
5. **Write the steps for the coding agent, in order.** The first one runs the backbone's own
   smallest example in our project. Each step gives:
   - the files in our project it touches and what to change;
   - why: the backbone's way, or the gap it fills, with repo and file;
   - how to check it worked.

   Keep only what our stage needs.
6. **Not adopted:** ideas from other repos that do not fill a named gap go to this appendix,
   one line each with the reason, so the coding agent leaves them out.
7. **Without a local project,** write the steps as a build plan: the backbone first, then each
   gap, each with its source.

## With the command line

Write the answer into the question file printed by `github-scout show <q>`, in these sections:
- In one paragraph;
- Backbone: which repo and why it passed (results, stars, trial);
- Gaps to fill: gap, source, reason;
- Trial runs;
- Against what we have;
- Next steps in our project;
- Not adopted.

In its frontmatter set `status: answered`, `backbone:` (the repo we follow), `alternate:` (when
there is one) and `picked:` (the backbone, then the repos that fill its gaps). Then:

```bash
github-scout check            # warns when the backbone was not tried, has no results or too few stars
github-scout brief <q>        # writes the hand-off from the answer and the cards
```

Give the user the brief's path, to hand to the coding agent. The project is not touched.

The brief ends with one `github-scout adopt` line per repo to bring in, which the coding agent
fills in as it brings the brief into the project (`github-scout-adopt`, stage 6), then the Not
adopted appendix.

## Without the command line (cloud chat)

Write sections 5 and 6 of the report: the answer (backbone, gaps, the trials to run locally),
then the brief for the coding agent. Offer the whole report as one file to download. To take it
over locally:

```bash
github-scout import report.md --q <project>/<question>
```

Back home, the project's own coding agent adopts the brief; a chat never changes the project.

A defect in this skill that stays unfixed: record it with `scripts/report-problem.sh "<summary>"`.
