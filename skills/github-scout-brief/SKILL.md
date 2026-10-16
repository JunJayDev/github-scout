---
name: github-scout-brief
description: Compare the findings with your project and write a hand-off brief for the coding agent, without changing the project.
license: MIT
---

# GitHub scout: brief

Stage 5 of `github-scout`. Turn the findings into concrete suggestions for our project, and hand
them to the agent that will change the code. Do not change the project yourself.

## Input

The findings from `github-scout-dig`, and our project: its code when there is a local repository,
otherwise what the user said exists.

## Steps

1. **Compare.** For each idea, read the part of our code it touches. Write a table:

   | ours | theirs | the difference | take it or not |
   |---|---|---|---|

2. **Answer in one paragraph:** what to take from whom, or "build it ourselves, because nothing
   covers X". Name the part nobody covers.
3. **Write the steps for the coding agent, in order.** Each step gives:
   - the files in our project it touches and what to change;
   - why: which idea, from which repo and file;
   - how to check it worked;
   - what not to copy because of its licence.

   Keep only what our stage needs.
4. **Without a local project,** write the steps as a build plan: the parts to build or adopt, in
   order, each with its source.

## With the command line

Write the answer into the question file printed by `github-scout show <q>`, in these sections:
- one paragraph;
- ideas worth taking;
- practices and components;
- against what we have;
- next steps in our project.

Set `status: answered` and `picked:` (the repos the answer relies on) in its frontmatter. Then:

```bash
github-scout check
github-scout brief <q>        # writes the hand-off from the answer and the cards
```

Give the user the brief's path, to hand to the coding agent. The project is not touched.

## Without the command line (cloud chat)

Write sections 5 and 6 of the report: the answer, then the brief for the coding agent. Offer the
whole report as one file to download. To take it over locally:

```bash
github-scout import report.md --q <project>/<question>
```
