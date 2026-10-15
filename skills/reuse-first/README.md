# reuse-first skill

Makes an agent ask the right question, find what open source already solved, take the ideas
and parts that fit where the project stands, and record every verdict in a shared registry. `SKILL.md` is the procedure. This file covers setup.
Project home, design notes and issues are in the repository's top-level README.

## Requirements

- Python 3.9+ (standard library only).
- A GitHub token: `GITHUB_TOKEN` or `GH_TOKEN`, or a logged-in `gh` CLI. Code search needs one.
- Network access to `api.github.com`, `codeload.github.com` and `registry.npmjs.org`.

## Configuration

The registry is a directory created by `python3 scripts/reuse-first.py init <dir>`. The tool
finds it in this order:

1. `--store DIR` on the command line (before or after the command).
2. `REUSE_FIRST_STORE`.
3. A config file, the first one that exists:
   `$REUSE_FIRST_CONFIG`, `${XDG_CONFIG_HOME:-~/.config}/reuse-first/config.env`,
   `${AGENT_SKILLS_CONFIG_DIR:-~/.config/agent-skills}/reuse-first/config.env`.
   See `config.example.env`. The file is parsed as `KEY=value`, never executed, and unknown
   keys are an error.
4. The nearest parent of the current directory that contains `reuse-first.json`. This lets a
   team keep a registry inside a project repository.

## Environment variables

| variable | purpose |
|---|---|
| `REUSE_FIRST_STORE` | registry directory |
| `REUSE_FIRST_PROJECT` | default project when a need is written without `<project>/` |
| `REUSE_FIRST_CONFIG` | alternative config file |
| `REUSE_FIRST_AGENT` | name recorded as `by` in the ledger (default `agent`) |
| `GITHUB_TOKEN`, `GH_TOKEN` | GitHub token |
| `REUSE_FIRST_GITHUB_API`, `REUSE_FIRST_NPM_API` | API base URLs (GitHub Enterprise, mirrors, tests) |
| `AGENT_SKILLS_STATE_DIR` | where `scripts/report-problem.sh` records known defects |

## CLI

```bash
python3 scripts/reuse-first.py --help
python3 scripts/reuse-first.py <command> --help
```

When installed as a package (`pipx install <repo>`), the same CLI is `reuse-first`.

## Maintenance

- `updates` (with `--diff` and `--done`) keeps cards current; `check` validates the registry and
  regenerates `INDEX.md`; `site` writes `site/index.html`.
- Known defects that remain unfixed: `scripts/report-problem.sh "<summary>" [observed] [tried]`
  (writes to local state, never to the registry).
