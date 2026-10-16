# Contributing

Thanks for helping. github-scout stays small on purpose: one skill, one standard-library
Python package, and a plain-text registry format.

## Ground rules

- **No runtime dependencies.** The skill folder must work when it is copied on its own, with
  only Python 3.9+.
- **The registry format is a contract.** If you change what is written to disk, update
  `skills/github-scout/references/store-format.md`, keep old registries readable, and say so
  in CHANGELOG.md.
- **Agents read the output.** Keep command output short and dense, and say what to run next.
  Every token in a table row is paid for by every user.
- **Downloaded code is never executed.** `fetch` only extracts files, and must keep it that way.

## Development

```bash
python -m unittest discover -s tests -v       # offline; uses a fake GitHub API
python skills/github-scout/scripts/github-scout.py --help
```

Tests must not use the network. Add a fixture to `tests/fake.py` instead.

To try a change against real GitHub, create a scratch registry (`github-scout init /tmp/r`)
and run a scan. Include before/after rankings in the pull request when you change search
lenses or scoring. Ranking changes are judged on real needs, not on taste.

## Ideas that fit

- New lenses with a measurable recall gain: other package registries, other forges.
- Better kind detection in `peek`.
- Harness-specific install notes.
