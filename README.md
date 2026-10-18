**English** · [中文](./README.zh-CN.md)

# github-scout

**Before your agent builds something, it finds what GitHub already solved, keeps the projects
that show what they made, tries the best two or three, and hands your coding agent a brief:
which one to follow as a whole, what fills its gaps, and where it goes in your code.**

Agents rebuild things that exist because they search like newcomers. One project needed to
read and post on Reddit, X and Xiaohongshu through a logged-in browser. The right tool had
30,000 stars and described itself as "Make any website into CLI & use your logged-in browser by
AI agent". GitHub search, sorted by stars, put it here:

| search | where the right tool landed |
|---|---|
| `social media automation` | not in the top 8 |
| `自媒体 运营` | not in the top 8 |
| `"reddit" "xiaohongshu" in:readme` (two concrete sites) | **#1** |
| `"logged-in browser"` (how it works) | **#1** |

Good projects describe themselves by what they touch and how they work. github-scout writes
those searches for you, in English and Chinese, runs about 140 of them, and reads the results.

## Install

```bash
npx skills add JunJayDev/github-scout -g
```

Or tell your agent: *"Install the skills from https://github.com/JunJayDev/github-scout"*.
In Claude Code, the plugin works too: `/plugin marketplace add JunJayDev/github-scout`, then
`/plugin install github-scout@github-scout`.

The command-line part needs Python 3.9+ and a logged-in `gh` (or `GITHUB_TOKEN`). Nothing else
to set up: the first question creates its registry in `~/.github-scout`.

**Nothing to install:** in ChatGPT or Claude on the web, upload
[`cloud/github-scout.md`](cloud/github-scout.md) and write your goal (add a zip of your project
if you can). It runs on web search alone, does not stop unless you ask, and ends with one report
file. Back home, `github-scout import report.md --q <project>/<question>` takes it over and
checks every link against GitHub.

## Use

Open your agent inside your project and say what you want:

> Use github-scout: make the product videos our agent renders cut and move like an editor's.

It reads your project, proposes what good looks like and the search directions, and **stops for
you to confirm them**. Then it searches, keeps the repos with results to look at and 50+ stars,
tries the best two or three, reads the code of the one to follow, and writes a brief for your
coding agent. It does not change your project.

When you want it in your code, tell your coding agent to adopt the brief. It works in your
repository by your project's rules, one commit per repo, and records each one with
`github-scout adopt`: which of your files came from which repo, at which commits. From then on
`github-scout updates` tells you when upstream changes the files you took.

## Six stages

Each stage is a skill and runs on its own. `github-scout` runs the first five in order; the sixth
changes your project, so your coding agent runs it there, when you ask.

| skill | does |
|---|---|
| `github-scout-plan` | reads your project, restates the goal as a result, says what good looks like, sets the stage, writes search directions in English and Chinese |
| `github-scout-search` | searches every direction many ways: names, pairs, mechanisms, topics, SKILL.md files, skills.sh, the MCP registry, npm, fast-rising new repos; leaves out repos under 50 stars |
| `github-scout-triage` | keeps the repos with results to look at and 50+ stars, tags them, decides how to read each (a skill, a CLI and a list are read differently) |
| `github-scout-dig` | tries the best two or three, stops early on dead ends, reads the code of the one to follow |
| `github-scout-brief` | compares with your code; writes the answer (one backbone, what fills its gaps) and the hand-off for your coding agent |
| `github-scout-adopt` | brings the backbone in whole (depend, skill, tool) and each gap filler by your rules (port, vendor, data), and records it with `github-scout adopt` |

## What it believes

- **The goal decides what you find.** "Find a video tool" and "make our videos cut like an
  editor's" find different projects. Say what good looks like before you search: two or three
  finished results to match, or checks anyone can run. The stage of your own work decides what to
  borrow: a whole approach early on, parameters and edge cases later.
- **Results before code.** A repo counts only if you can see what it made: films, galleries,
  sample outputs, benchmarks, projects using it. Under 50 stars it is no reference unless you
  write why.
- **Try before you read.** The best two or three get a short run, their own smallest example or
  one real task, before anyone reads their code. One that does not run is dropped in minutes.
- **One backbone, then its gaps.** Follow one proven repo as a whole; take from others only what
  it lacks, each with a reason. One run took an idea from each of twelve repos, and the film it
  made was wrong.
- **A brief, not a list.** Twenty repos with star counts leave all the work to you.
- **No licence filter.** It looks for references to follow. Licences are left out of the search,
  the ranking and the report: checking them makes an agent drop projects before anyone has looked
  at what they made.
- **New and moving helps you find, not pick.** No push in 3 months ranks far down, 6 months is
  set aside, 12 months is dropped. Fast-rising new repos are searched for; picking goes by
  results, stars, the trial and fit. Lures (game cheats, cracks) and farmed install counts are
  left out.
- **English and Chinese, always.** Chinese projects supplied half the repos picked in real runs,
  and they describe themselves in Chinese.
- **Never read the same repo twice.** Every verdict goes into the registry with its reason; later
  searches start from it, and `updates` shows only what changed in the files you depend on.
- **Know what came from where.** Each adoption records your files, their files and both commits,
  so an upstream fix to code you copied reaches you instead of going unnoticed.

## The registry

A folder of Markdown and JSON, best kept in git:

```
projects/<project>/questions/<q>.md      the goal, its stage, the directions, the answer
projects/<project>/briefs/<q>.md         the hand-off for the coding agent
repos/<owner>__<repo>.md                 one card per repo read closely: the idea, its results and our trial, where we adopted it
ledger.jsonl                             every verdict, append-only
scans/<project>/<q>/<stamp>.json         what each search ran and found
```

`github-scout site` writes one web page to browse it. Formats:
[`store-format.md`](skills/github-scout/references/store-format.md).

## Costs and limits

- Each search costs API calls, not tokens. A full search takes five to fifteen minutes within
  GitHub's free limits. The table the agent reads is about 2,000 tokens; one repo's facts about 1,300.
- It sees public GitHub, npm, skills.sh, the MCP registry, and links you add. GitLab, Codeberg
  and closed-source options need the web pass the search stage describes.
- A clean search proves nothing is missing only for the sources it checked, which it lists.

## Related

Many "search before you build" skills guide one search to one decision, such as ECC's
`search-first` (the most installed on skills.sh), `reuse-before-build` and `oss-scout`.
github-scout adds what comes before and after that decision:
- reading your own project first;
- the stage-based question, with what good looks like;
- a quality gate: results to look at, 50+ stars, a trial run before anyone reads code;
- the registry that remembers every verdict;
- tracking the repos you depend on;
- a brief your coding agent can act on;
- a record of what it adopted, so upstream changes to those files reach you.

## Contributing

Issues and pull requests welcome; see [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).
Tests run offline: `python -m unittest discover -s tests`.

## License

MIT.
