**English** · [中文](./README.zh-CN.md)

# github-scout

Agent skills and a CLI that find what GitHub already solved for a goal in your project, try the top candidates, and hand your coding agent an implementation brief.

[![CI](https://github.com/JunJayDev/github-scout/actions/workflows/ci.yml/badge.svg)](https://github.com/JunJayDev/github-scout/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## How it works

When you give your agent a goal, `github-scout` reads your project first to see what you already have and where it falls short. It restates the goal as a concrete outcome, defines what good looks like, sets the project stage, and plans search directions in English and Chinese. Then it pauses for you to confirm the plan.

After you confirm, it searches GitHub and package directories in both languages, keeps repositories that show verifiable results and have 50+ stars, and trials the top two or three candidates in an isolated environment. It reads the source code of the one candidate worth following as a whole (the backbone), identifies which other repositories can fill its specific gaps, and writes a step-by-step brief for your coding agent.

Research never modifies your repository. Your project changes only when you ask your coding agent to adopt the brief, which applies the changes under your project's rules and records file and commit provenance in a local registry so you can track upstream updates.

## Quick start

### Install

Install the skills globally for your agent:

```bash
npx skills add JunJayDev/github-scout -g
```

Or tell your agent: *"Install the skills from https://github.com/JunJayDev/github-scout"*.

In Claude Code, you can also install via the plugin marketplace:

```text
/plugin marketplace add JunJayDev/github-scout
/plugin install github-scout@github-scout
```

The CLI requires Python 3.9+ and a logged-in `gh` CLI (or `GITHUB_TOKEN`). It has no external Python dependencies. Your first question automatically initializes the local registry in `~/.github-scout`.

### Use

Open your agent inside your project repository and state the outcome you want:

> Use github-scout: make the product videos our agent renders cut and move like an editor's.

1. **Confirm the plan.** The agent inspects your codebase, proposes what good looks like along with English and Chinese search directions, and stops for your confirmation.
2. **Get the brief.** Once confirmed, it runs the searches, keeps candidates with observable results and 50+ stars, trials the best two or three, maps the backbone's code, and writes a hand-off brief without changing your project.
3. **Adopt and track.** When you are ready to integrate, ask your coding agent to adopt the brief. It commits changes one source repository at a time and runs `github-scout adopt` to record which of your files came from which upstream files and commits. Run `github-scout updates` at any time to check whether upstream changed the files you took.

### Run without installing (Web chat)

In ChatGPT or Claude on the web, upload [`cloud/github-scout.md`](cloud/github-scout.md) and describe your goal (attach a zip of your project if possible). It runs on web search alone without pausing unless you ask, and finishes with a single Markdown report.

To bring that report into your local registry later, run:

```bash
github-scout import report.md --q <project>/<question>
```

`import` checks every GitHub link against the API and saves the candidates, notes, and verdicts.

## Six stages

Each stage is an independent skill that can run on its own. `github-scout` runs stages 1 through 5 in order without modifying your project; your coding agent runs stage 6 inside your repository when asked.

| Stage | Skill | What it does |
|---|---|---|
| 1. Plan | `github-scout-plan` | Reads your project, restates the goal as a result, defines what good looks like, sets the stage (`idea`, `prototype`, `working`, `polishing`), and writes search directions in English and Chinese. |
| 2. Search | `github-scout-search` | Searches each direction across names, term pairs, mechanisms, GitHub topics, `SKILL.md` files, skills.sh, the MCP registry, npm, and fast-rising new repos; excludes lures, farmed installs, and repos under 50 stars. |
| 3. Triage | `github-scout-triage` | Keeps candidates with observable results and 50+ stars, tags their kind (`skill`, `cli`, `mcp`, `library`, `app`, `list`), and assigns an inspection route to each. |
| 4. Dig | `github-scout-dig` | Trials the top two or three candidates in a throwaway directory or container, stops early on dead ends, and reads the source code of the chosen backbone. |
| 5. Brief | `github-scout-brief` | Compares findings against your code and writes the answer (one backbone, what fills its gaps, and a "Not adopted" appendix) plus the hand-off brief for your coding agent. |
| 6. Adopt | `github-scout-adopt` | Brings the backbone in as a whole (`depend`, `skill`, `tool`) and fills gaps by your project's rules (`port`, `vendor`, `data`), recording provenance with `github-scout adopt`. |

## CLI overview

Usage: `github-scout [--version] [--store DIR] <command> ...`

**Planning and search**
- `init` : Create a registry directory.
- `new-project` : Add a project profile.
- `find` : Search existing questions, repo cards, and the ledger to see if a topic was already evaluated.
- `ask` : Start a question with your goal, project stage, and search vocabulary.
- `scan` : Execute searches for a question and print merged, ranked candidates (`--plan` previews queries; `--add` adds external links; `--expand` adds the repos an awesome list links to).

**Triage, trials, and adoption**
- `pick` : Record verdicts on scan table rows or `owner/repo` (`--low-stars "<why>"` required under 50 stars).
- `look` : Inspect repository facts, activity, kind, file tree, and README result links (`--source` downloads and maps source code).
- `note` : Record findings on a repo card (`use`, `adapt`, `learn`, `later`, `skip`), including `--results`, `--trial`, and `--watch` paths.
- `brief` : Turn an answered question into a hand-off file for the coding agent without changing the project.
- `adopt` : Record a repository integrated into your project (mode, local paths, upstream paths, and commit hashes).

**Registry and maintenance**
- `import` : Import a Markdown report from a web chat or teammate and verify every GitHub link.
- `show` : Display a question with its coverage and answer, or a repo card with its history.
- `updates` : Check upstream repositories for commits touching the files your cards watch or adopted.
- `site` : Generate a static HTML page (`site/index.html`) to browse the registry.
- `check` : Validate the registry and regenerate `INDEX.md`.

The minimum star threshold defaults to `50` (override via `GITHUB_SCOUT_MIN_STARS`). The registry path resolves from `--store DIR`, `GITHUB_SCOUT_STORE`, the config file, the nearest parent directory containing `github-scout.json`, or `~/.github-scout`.

## Design principles

- **Goal and stage drive the search.** Searching for a generic tool category yields different candidates than stating the target result. Defining what good looks like (two or three finished outputs to match, or runnable checks) and setting your project's stage (`idea`, `prototype`, `working`, `polishing`) determines whether to borrow an entire approach or specific parameters and edge cases.
- **Bilingual search by entities and mechanisms.** Good projects describe what they touch and how they work rather than broad problem phrases. Every direction is searched in both English and Chinese using each community's native terms; Chinese projects supplied half of the repositories selected in real runs.
- **Observable results before code.** A repository qualifies as a reference only when you can inspect what it produced (sample outputs, videos, galleries, benchmarks, or downstream projects) and it has at least 50 stars, unless you record an explicit reason for an exception.
- **Trial before deep reading.** The top two or three candidates get a short run on their smallest example or a real task before anyone reads their codebase. Candidates that fail to run are dropped in minutes.
- **One backbone, then targeted gaps.** Combining ideas from many unrelated repositories does not add up to a working system. Every brief follows one proven repository as a whole (with at most one alternate) and takes from other repositories only what is needed to fill named gaps.
- **An actionable brief, not a link dump.** Handing over twenty repository links with star counts leaves the analysis to you. The output is a concrete implementation plan tailored to your existing files.
- **No license filter.** Research looks for technical references to follow. Licenses are omitted from search queries, ranking, and reports because filtering by license causes agents to discard projects before anyone has inspected what they built.
- **Recency and velocity help find, not pick.** Repositories with no push in 3 months rank much lower, 6 months are set aside, and 12 months are dropped. Fast-rising new repositories are searched to aid discovery, while selection depends on results, stars, trial outcomes, and fit. Lures (game cheats, cracks) and farmed skill install counts are excluded.
- **Persistent verdicts and provenance.** Every evaluated repository is logged in the registry with a verdict so no repository is read twice. Each adoption records your files, upstream files, and both commit hashes so upstream fixes to copied or ported code are surfaced by `github-scout updates`.

## The registry

The registry is a plain-text directory of Markdown and JSON files, designed to be tracked in git:

```text
projects/<project>/questions/<q>.md      the goal, its stage, the directions, the answer
projects/<project>/briefs/<q>.md         the hand-off for the coding agent
repos/<owner>__<repo>.md                 one card per repo read closely: idea, results, trial, adoptions
ledger.jsonl                             every verdict, append-only
scans/<project>/<q>/<stamp>.json         what each search ran and found
```

Run `github-scout site` to build a single static page (`site/index.html`) for browsing the registry. For file schemas, see [`store-format.md`](skills/github-scout/references/store-format.md).

## Costs and limits

- **API calls and token footprint:** Searches consume GitHub API calls rather than LLM tokens. A full search takes 5 to 15 minutes within GitHub's free rate limits. The ranked candidate table read by the agent is about 2,000 tokens, and one repository inspection (`look`) is about 1,300 tokens.
- **Source coverage:** Automated scans cover public GitHub, npm, skills.sh, the official MCP registry, and links added with `scan --add`. GitLab, Codeberg, and closed-source products require the web search pass described in `github-scout-search`.
- **Completeness:** A clean scan proves nothing was missed only across the sources and queries it checked, which are recorded in the scan log.

## Comparison with similar skills

Pre-build search skills such as ECC's `search-first` (the most installed on skills.sh), `reuse-before-build`, and `oss-scout` guide a single search toward a build-or-reuse decision. `github-scout` covers what comes before and after that decision:

- reading your local project first to map existing code and gaps;
- framing the question by project stage and defining verifiable target outputs;
- enforcing a quality gate: observable results, 50+ stars, and an isolated trial run before code review;
- storing every verdict in a persistent registry so repositories are not evaluated twice;
- writing a codebase-aware brief that your coding agent can execute directly;
- recording file-level and commit-level provenance with `github-scout adopt` and tracking upstream changes via `github-scout updates`.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

Tests run offline against a fake GitHub API fixture:

```bash
python -m unittest discover -s tests
```

## License

[MIT](LICENSE).
