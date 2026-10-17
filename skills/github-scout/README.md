# github-scout skill: setup

`SKILL.md` is the procedure; the six stage skills (`github-scout-plan`, `-search`, `-triage`,
`-dig`, `-brief`, `-adopt`) sit next to this folder. This file covers setup. Project home and
design notes are in the repository's top-level README.

## Requirements

- Python 3.9+ (standard library only).
- A GitHub token: `GITHUB_TOKEN` or `GH_TOKEN`, or a logged-in `gh` CLI. Code search needs one.
- Network access to `api.github.com`, `codeload.github.com`, `skills.sh`, `registry.npmjs.org`
  and `registry.modelcontextprotocol.io`.

None of this is needed in a cloud chat: there the skills run on web search alone (see
`references/report-format.md`).

## Where the registry lives

Nothing to configure for a first run: the first `ask` creates `~/.github-scout`. The tool looks
in this order:

1. `--store DIR` on the command line.
2. `GITHUB_SCOUT_STORE`.
3. A config file, the first that exists: `$GITHUB_SCOUT_CONFIG`,
   `${XDG_CONFIG_HOME:-~/.config}/github-scout/config.env`,
   `${AGENT_SKILLS_CONFIG_DIR:-~/.config/agent-skills}/github-scout/config.env`. See
   `config.example.env`. Parsed as `KEY=value`, never executed; unknown keys are an error.
4. The nearest parent of the current directory holding `github-scout.json`, so a team can keep
   a registry inside a repository.
5. `~/.github-scout`.

Registries, variables and config files from before the rename (`reuse-first.json`,
`REUSE_FIRST_*`, `reuse-first/config.env`) are still read.

## Environment variables

| variable | purpose |
|---|---|
| `GITHUB_SCOUT_STORE` | registry directory |
| `GITHUB_SCOUT_PROJECT` | project used when a question is written without `<project>/` |
| `GITHUB_SCOUT_CONFIG` | alternative config file |
| `GITHUB_SCOUT_AGENT` | name recorded as `by` in the ledger (default `agent`) |
| `GITHUB_TOKEN`, `GH_TOKEN` | GitHub token |
| `GITHUB_SCOUT_GITHUB_API`, `GITHUB_SCOUT_NPM_API`, `GITHUB_SCOUT_SKILLS_API`, `GITHUB_SCOUT_MCP_API` | API base URLs (GitHub Enterprise, mirrors, tests) |
| `AGENT_SKILLS_STATE_DIR` | where `scripts/report-problem.sh` records known defects |

## CLI

```bash
python3 scripts/github-scout.py --help
python3 scripts/github-scout.py <command> --help
```

Installed as a package (`pipx install <repo>`), the same CLI is `github-scout`.

## Maintenance

- `updates` (with `--diff` and `--done`) keeps cards current, adopted repos first: `adopt`
  records which files came into a project, and `updates` reports the upstream commits on them.
  `check` validates the registry and regenerates `INDEX.md`. `site` writes `site/index.html`.
- Record a defect that stays unfixed with `scripts/report-problem.sh "<summary>" [observed] [tried]`.
  It writes to local state, never to the registry.
