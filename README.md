**English** · [中文](./README.zh-CN.md)

# github-scout

GitHub research for coding agents: find proven open-source projects to try before your agent builds from scratch. Agent skills and a CLI for Claude Code and Codex.

[![CI](https://github.com/JunJayDev/github-scout/actions/workflows/ci.yml/badge.svg)](https://github.com/JunJayDev/github-scout/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

Coding agents start writing before they check whether someone already built the thing. `github-scout` makes yours look first. It reads your project, searches GitHub in English and Chinese, and hands your agent a short report: what already exists, the two or three projects worth trying first, and how to try each. It never changes your project.

It is for people who build with Claude Code, Codex or another agent that runs skills. You can also run it by hand from the command line, or in ChatGPT or Claude on the web with one uploaded file.

## What you get

The question from the [worked example](skills/github-scout/references/workflow.md): read and post on Reddit, X and Xiaohongshu from scripts through a logged-in Chrome, with no model clicking pages. Agents that searched for "social media automation" missed the 30k-star tool that does it. This scan ran on 2026-11-07 (141 searches, about 7 minutes) and puts it on row 4 of the table your agent reads:

```text
scan demo/browser-ops 20261107-121044: 141 searches, 1250 repos
…
  #  score  stars created   pushed  repo  description  [lenses] fit = vocabulary groups in its own name/description/topics
  1.  15.0 109.7k  26-02 26-11-06  Panniantong/Agent-Reach  Give your AI agent eyes to see the entire internet. Read & search Twitter, Reddit, YouTube  [EPMTR] fit 5
  2.  14.8   3.7k  26-03 26-11-06  whiteguo233/OpenBiliClaw  本地私有、开源的自进化跨平台 AI 内容发现 Agent：先理解你，再主动从 B站、小红书、抖音、YouTube、X、知乎、Reddit、微博等平台与开放 Web 寻找内容。（支持  [EPMCTRK] fit 5
  3.  14.6   4.5k  26-08 26-11-02  ZJU-REAL/Easel  An open-source AI agent for social media — discover trends, create content, publish everyw  [EPR] fit 4
  4.  14.4  30.9k  26-03 26-11-05  jackwener/OpenCLI  Make Any Website into CLI & Use your logged-in browser by AI agent.   [PMCRS] fit 3 installs 20.5k
  5.  13.3  18.9k  26-04 26-11-07  browser-use/browser-harness  Let Claude Code, Codex or Cursor use your real Chrome, logged in as you. One prompt to set  [MTRS] fit 3 installs 864
  6.  13.2    114  26-08 26-08-23  woniu9524/open-web-bridge  Drive your real Chrome from any AI agent — logged-in sessions, real fingerprint, live tabs  [TS] fit 4 installs 9
…
```

Your agent then opens the promising rows with `look`:

```text
$ github-scout look jackwener/OpenCLI
## jackwener/OpenCLI  (software: cli?)  https://github.com/jackwener/OpenCLI
Make Any Website into CLI & Use your logged-in browser by AI agent.
stars 30941 · forks 3033 · issues 288 · created 2026-03-14 · pushed 2026-11-05 · JavaScript
head main@36bbbd7f60bd · release v2.0.2 2026-10-20
maintenance: active · 94 commits in 30 days · 5 releases in 90 days · 10+ contributors, top one 77% of commits
…
verifiable effect: strong · live site (homepage) https://opencli.info/ · npm @jackwener/opencli: 165.2k downloads last month https://www.npmjs.com/package/@jackwener/opencli
…
```

and writes the report: what exists, the two or three to try first and how to try each, and what is likely left to build. Section 5 of the [worked example](skills/github-scout/references/workflow.md) shows a report for this question. To get this table yourself, see [Try it by hand](#try-it-by-hand).

## How it works

When you give your agent a goal, `github-scout` reads your project first to see what you already have and where it falls short. It restates the goal as a concrete outcome, defines what good looks like, sets the project stage, and plans search directions in English and Chinese. Then it pauses for you to confirm the plan.

After you confirm, it searches GitHub and package directories in both languages and keeps repositories with a verifiable effect and 50+ stars. A verifiable effect is something you can check outside the README text: a live site that responds, a package with real downloads, screenshots or videos, or posts about the project. Where a search direction has fewer than five such repositories, its threshold drops to 20 stars, then 10. The run ends with a report for your coding agent: what exists, the two or three candidates to try first and how to try each, what is likely left to build, and what was searched.

`github-scout` never runs candidate code and never modifies your repository. When you ask, your coding agent takes the report from there: it tries the two or three in an isolated environment, chooses one to follow as a whole, fills its gaps from other repositories with a stated reason for each, and adopts it under your project's rules. Each adoption records file and commit provenance in a local registry so you can track upstream updates.

## Quick start

You need Python 3.9+ and GitHub access: run `gh auth login` once, or set `GITHUB_TOKEN`.

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

The skills bring their own copy of the CLI (standard library only), so your agent needs nothing else. Your first question creates the local registry in `~/.github-scout`.

To run the commands yourself (the walkthrough below, `import`, `updates`), put `github-scout` on your PATH:

```bash
pipx install git+https://github.com/JunJayDev/github-scout   # or: uv tool install git+https://github.com/JunJayDev/github-scout
```

### Use

Open your agent inside your project repository and state the outcome you want:

> Use github-scout: make the product videos our agent renders cut and move like an editor's.

A run has three parts: a plan you confirm, a search of 5 to 15 minutes, and a report saved in `~/.github-scout/projects/<project>/briefs/`.

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

### Try it by hand

To see what your agent sees, run one search yourself. With `github-scout` on your PATH (see Install), start a question:

```bash
github-scout ask demo/browser-ops "Read and post on Reddit, X and Xiaohongshu from scripts through my logged-in Chrome, with no model clicking pages" --stage working
```

`ask` prints the path of a question file. Open it and replace the four empty lists at the top with the search words (your agent writes these when it runs the skill):

```yaml
entities: ["reddit", "xiaohongshu|小红书|rednote|xhs", "twitter|x.com|推特", "bilibili|B站|哔哩哔哩", "zhihu|知乎"]
mechanisms: ["logged-in browser|登录态", "chrome extension|浏览器插件|Chrome 插件", "browser cookies", "CDP", "browser automation|浏览器自动化"]
forms: [cli, mcp, skill]
problems: ["social media automation", "自媒体 自动化", "website to cli"]
```

Then run the search and look at a row up close:

```bash
github-scout scan demo/browser-ops --plan   # list the searches; no network
github-scout scan demo/browser-ops          # about 7 minutes; prints a table like the one above (rows shift as repos change)
github-scout look jackwener/OpenCLI         # activity, kind, verifiable effect, README start
```

From here the skill goes on as your agent would: `pick` records verdicts on rows, `note` keeps what each repo would do for you, and `brief` writes the report. The steps are in [`workflow.md`](skills/github-scout/references/workflow.md).

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

## Related

Part of a series on media literacy for agents. [x-scout](https://github.com/JunJayDev/x-scout) does the same for X: it reads posts without login, checks every search hit against X, and judges value apart from reach.

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [AGENTS.md](AGENTS.md).

Tests run offline against a fake GitHub API fixture:

```bash
python -m unittest discover -s tests
```

## License

[MIT](LICENSE).
