**English** · [中文](./README.zh-CN.md)

# github-scout

Agent skills and a CLI that find what GitHub already solved for a goal in your project, keep the projects whose effect you can verify, and report to your coding agent the two or three worth trying.

[![CI](https://github.com/JunJayDev/github-scout/actions/workflows/ci.yml/badge.svg)](https://github.com/JunJayDev/github-scout/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## How it works

When you give your agent a goal, `github-scout` reads your project first to see what you already have and where it falls short. It restates the goal as a concrete outcome, defines what good looks like, sets the project stage, and plans search directions in English and Chinese. Then it pauses for you to confirm the plan.

After you confirm, it searches GitHub and package directories in both languages and keeps repositories with a verifiable effect and 50+ stars. A verifiable effect is something you can check outside the README text: a live site that responds, a package with real downloads, screenshots or videos, or posts about the project. Where a search direction has fewer than five such repositories, its threshold drops to 20 stars, then 10. The run ends with a report for your coding agent: what exists, the two or three candidates to try first and how to try each, what is likely left to build, and what was searched.

`github-scout` never runs candidate code and never modifies your repository. When you ask, your coding agent takes the report from there: it tries the two or three in an isolated environment, chooses one to follow as a whole, fills its gaps from other repositories with a stated reason for each, and adopts it under your project's rules. Each adoption records file and commit provenance in a local registry so you can track upstream updates.

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
2. **Get the report.** Once confirmed, it runs the searches, keeps candidates with a verifiable effect and enough stars, and writes a report: the candidates, the two or three to try first with how to try each, and what was searched. Your project is not changed.
3. **Try, choose, adopt.** When you are ready, ask your coding agent to act on the report. It tries the two or three (minutes each, outside your project), records each trial, and chooses one to follow. It then commits changes one source repository at a time and runs `github-scout adopt` to record which of your files came from which upstream files and commits. Run `github-scout updates` at any time to check whether upstream changed the files you took.

### Run without installing (Web chat)

In ChatGPT or Claude on the web, upload [`cloud/github-scout.md`](cloud/github-scout.md) and describe your goal (attach a zip of your project if possible). It runs on web search alone without pausing unless you ask, and finishes with a single Markdown report.

To bring that report into your local registry later, run:

```bash
github-scout import report.md --q <project>/<question>
```

`import` checks every GitHub link against the API and saves the candidates, notes, and verdicts.

## Six stages

Each stage is an independent skill that can run on its own. `github-scout` runs stages 1 through 4 in order and ends with the report, without modifying your project. Your coding agent runs stages 5 and 6 inside your repository when asked.

| Stage | Skill | What it does |
|---|---|---|
| 1. Plan | `github-scout-plan` | Reads your project, restates the goal as a result, defines what good looks like, sets the stage (`idea`, `prototype`, `working`, `polishing`), and writes search directions in English and Chinese. |
| 2. Search | `github-scout-search` | Searches each direction across names, term pairs, mechanisms, GitHub topics, `SKILL.md` files, skills.sh, the MCP registry, npm, and fast-rising new repos; excludes lures, farmed installs, and repos under 50 stars. |
| 3. Triage | `github-scout-triage` | Keeps candidates with a verifiable effect (strong or mid) and enough stars, tags their kind (`skill`, `cli`, `mcp`, `library`, `app`, `list`), and notes how each would be tried. |
| 4. Brief | `github-scout-brief` | Compares the shortlist against your code and writes the report: what exists, a candidate table, the two or three to try first and how, what is not recommended, and what was searched. |
| 5. Dig | `github-scout-dig` | Run by your coding agent. Tries the two or three in a throwaway directory or container, stops early on dead ends, chooses one to follow as a whole, and names what fills its gaps. |
| 6. Adopt | `github-scout-adopt` | Run by your coding agent. Brings the chosen repository in as a whole (`depend`, `skill`, `tool`) and fills gaps by your project's rules (`port`, `vendor`, `data`), recording provenance with `github-scout adopt`. |

## CLI overview

Usage: `github-scout [--version] [--store DIR] <command> ...`

**Planning and search**
- `init` : Create a registry directory.
- `new-project` : Add a project profile.
- `find` : Search existing questions, repo cards, and the ledger to see if a topic was already evaluated.
- `ask` : Start a question with your goal, project stage, and search vocabulary.
- `scan` : Execute searches for a question and print merged, ranked candidates (`--plan` previews queries; `--add` adds external links; `--expand` adds the repos an awesome list links to).

**Triage, trials, and adoption**
- `pick` : Record verdicts on scan table rows or `owner/repo` (`--low-stars "<why>"` required under the star floor).
- `look` : Inspect repository facts, activity, kind, file tree, and the verifiable effect graded strong, mid or weak (`--source` downloads and maps source code).
- `note` : Record findings on a repo card (`use`, `adapt`, `learn`, `later`, `skip`), including `--results` (links to its verifiable effect), `--trial`, and `--watch` paths.
- `brief` : Turn an answered question into the report for the coding agent without changing the project.
- `adopt` : Record a repository integrated into your project (mode, local paths, upstream paths, and commit hashes).

**Registry and maintenance**
- `import` : Import a Markdown report from a web chat or teammate and verify every GitHub link.
- `show` : Display a question with its coverage and answer, or a repo card with its history.
- `updates` : Check upstream repositories for commits touching the files your cards watch or adopted.
- `site` : Generate a static HTML page (`site/index.html`) to browse the registry.
- `check` : Validate the registry and regenerate `INDEX.md`.

The minimum star threshold defaults to `50` (override via `GITHUB_SCOUT_MIN_STARS`); a search direction with fewer than five repositories at the threshold is relaxed to 20 stars, then 10. The registry path resolves from `--store DIR`, `GITHUB_SCOUT_STORE`, the config file, the nearest parent directory containing `github-scout.json`, or `~/.github-scout`.

## Design principles

- **Goal and stage drive the search.** Searching for a generic tool category yields different candidates than stating the target result. Defining what good looks like (two or three finished outputs to match, or runnable checks) and setting your project's stage (`idea`, `prototype`, `working`, `polishing`) determines whether to borrow an entire approach or specific parameters and edge cases.
- **Bilingual search by entities and mechanisms.** Good projects describe what they touch and how they work rather than broad problem phrases. Every direction is searched in both English and Chinese using each community's native terms; Chinese projects supplied half of the repositories selected in real runs.
- **Verifiable effect before code.** Most projects show their results outside the repository. A candidate's effect is graded: strong (a live site that responds, a package with real downloads, real installs), mid (screenshots, GIFs or videos in the README, posts on X, Bilibili, YouTube, blogs or Xiaohongshu), or weak (only a text description). Only strong and mid candidates qualify as references, unless you record an explicit reason for an exception.
- **Stars per direction.** A reference needs 50 stars. Niche directions rarely have five projects that size, so a direction (one group of search terms) with fewer than five is relaxed to 20 stars, then 10, never lower. The scan header and the report say which directions were relaxed and why.
- **The report stops before trials.** `github-scout` finds, filters and reports; it does not run candidate code or pick a winner. Your coding agent tries the two or three in minutes each, outside your project, and drops a candidate at the first failure.
- **One main reference, then targeted gaps.** Combining ideas from many unrelated repositories does not add up to a working system. After its trials, the coding agent follows one repository as a whole (with at most one alternate) and takes from other repositories only what fills a named gap, with a reason for each.
- **A report, not a link dump.** Handing over twenty repository links with star counts leaves the analysis to you. The report says what each candidate does for your goal, how it relates to your files, and how to try the two or three worth trying.
- **No license filter.** Research looks for technical references to follow. Licenses are omitted from search queries, ranking, and reports because filtering by license causes agents to discard projects before anyone has inspected what they built.
- **Recency and velocity help find, not pick.** Repositories with no push in 3 months rank much lower, 6 months are set aside, and 12 months are dropped. Fast-rising new repositories are searched to aid discovery, while selection depends on results, stars, trial outcomes, and fit. Lures (game cheats, cracks) and farmed skill install counts are excluded.
- **Persistent verdicts and provenance.** Every evaluated repository is logged in the registry with a verdict so no repository is read twice. Each adoption records your files, upstream files, and both commit hashes so upstream fixes to copied or ported code are surfaced by `github-scout updates`.

## The registry

The registry is a plain-text directory of Markdown and JSON files, designed to be tracked in git:

```text
projects/<project>/questions/<q>.md      the goal, its stage, the directions, the answer
projects/<project>/briefs/<q>.md         the report for the coding agent
repos/<owner>__<repo>.md                 one card per repo read closely: idea, verifiable effect, trials, adoptions
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
- enforcing a quality gate: a verifiable effect and 50+ stars (relaxed per thin search direction), with an isolated trial by the coding agent before anyone reads code;
- storing every verdict in a persistent registry so repositories are not evaluated twice;
- writing a codebase-aware report that tells your coding agent what to try first and how;
- recording file-level and commit-level provenance with `github-scout adopt` and tracking upstream changes via `github-scout updates`.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

Tests run offline against a fake GitHub API fixture:

```bash
python -m unittest discover -s tests
```

## License

[MIT](LICENSE).
