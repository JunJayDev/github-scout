---
name: github-scout-plan
description: Turn a goal in your project into GitHub search directions in English and Chinese, after reading the project.
license: MIT
---

# GitHub scout: plan

Stage 1 of `github-scout`. The question decides what the search can find, so this stage
matters most.

## Input

A goal tied to a project or task. If the user gave none, ask "what do you want to achieve, in
which project?" and wait.

## Steps

1. **Read our project** when there is one: README, AGENTS.md or CLAUDE.md, the package files, and
   the code paths the goal touches. Write down what we already have (with paths) and what is not
   good enough. You cannot judge a difference you have not seen. Without a project, use what the
   user says exists today.
2. **Restate the goal as a result**, not as the tool you imagine. Not "find a video generation
   tool" but "make our product videos cut like an editor's, with an agent doing the work".
3. **Set the stage.** It decides what is worth borrowing. Split the question if parts sit at
   different stages.

   | stage | our work | borrow mostly |
   |---|---|---|
   | `idea` | nothing built | how others frame it, their approach, the dead ends |
   | `prototype` | a first version | workflows, architecture, trade-offs |
   | `working` | it works | techniques, parameters, prompts, edge cases, evaluation |
   | `polishing` | refining | details, benchmarks, parts to drop in |

4. **Write 3 to 8 directions.** Each direction is one sub-problem, with:
   - **entities**: the concrete things a solution touches: sites, file formats, APIs, products;
   - **mechanisms**: how a solution would work, in the words its README would use
     ("logged-in browser", "remotion", "MCP server");
   - **forms**: skill, cli, mcp, library, app.

   Write every entity and mechanism in English and in Chinese, as each community writes it, not
   translated: `xiaohongshu|小红书|xhs|红书`, `humanizer|去AI味|活人感|人味`. Chinese projects
   supplied half of the useful repositories in real runs. Single-word names written the same
   way everywhere (`remotion`, `CDP`) need nothing more.

   Problem phrases ("social media automation") find the least: good projects describe
   themselves by what they touch and how they work. Keep two or three short ones, one per language.

## With the command line

```bash
github-scout find <words>                                   # answered before?
github-scout ask <project>/<question> "<the result we want>" --stage working
```

Run `ask` inside the project's repository; it creates the registry and the project when
missing. Fill the question file it prints:
- "Where we are": what we have, what falls short.
- The vocabulary in the frontmatter: `entities` and `mechanisms` are lists of groups,
  synonyms joined with `|`; then `forms` and `problems`.

Then `github-scout scan <project>/<question> --plan` prints the searches and warns about groups
missing a language.

**Stop here.** Show the user the directions and the search plan, and wait for them to confirm or
change them, unless they said not to stop.

## Without the command line (cloud chat)

Write section 1 of the report (`../github-scout/references/report-format.md`): the goal as a
result, where we stand, the stage, and the directions in a table (direction, entities en/zh,
mechanisms en/zh, forms). Then go straight to the search, unless the user asked to confirm the
directions first.

## Next

`github-scout-search`.
