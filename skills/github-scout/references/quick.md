# Quick lookup

`github-scout quick` answers "is there something that already does this?" in one to three minutes.
Use it before you build something, install a tool or skill, or pick a library. Skip it only when
the user says to. It does not replace the stages: when the answer shapes the project (several
candidates compete, the user wants a report, you will adopt one), run the full flow.

A cheap, fast model does this well: the steps are mechanical and the table carries the evidence.
Give it to your cheapest capable model and keep only its short answer in your own context.

## Steps

1. **The need, in one sentence:** the result you want, not the tool you imagine. "An agent skill
   that makes a repo quotable by AI search", not "a GEO plugin".
2. **The words, in every language the audience writes in** (at least English and Chinese). Use
   the words the projects use about themselves, not translations:
   - `-e` names of things (platforms, formats, products); synonyms after `|`:
     `-e "xiaohongshu|小红书|rednote"`. Repeat for each thing.
   - `-m` how a solution works, in README words: `-m "mcp server" -m "logged-in browser"`.
   - `-p` a short phrase a user of this would write, one per language: `-p "geo skill for claude code" -p "让项目被 ai 搜索推荐"`.
   - `--form skill|mcp|cli|library|app|extension` what you want it to be. `skill` also reads
     skills.sh, `mcp` the MCP registry, `cli` and `library` npm.
3. **Run it:** `github-scout quick "<need>" -e … -m … -p … --form …`. It prints how many searches
   and GitHub calls it made, and a table: score, stars, created, last push, repo, description, the
   lenses that found it, `fit` (how many of your word groups its own name, description and topics
   match). Under the table: how many repos it hid (under 50 stars, not pushed in 6 months, lures)
   and any search that failed. `installs` is the skills.sh install count; `?` after a repo's kind in `look`
   means a guess.
4. **Look at the two or three rows that fit the need,** not blindly the first three: skip a word that
   matches in another sense (`geo` is also geography; a README beautifier matches `readme`). Then `github-scout look <owner/repo> …` gives facts, activity, the
   verifiable effect and the start of the README. No registry is needed.
5. **Answer** with those two or three: stars, last push, one line on what each does for the need,
   and the one risk that matters. Say what the lookup did not cover.

## Reading the table

- `fit` counts word matches in the repo's own name, description and topics, not meaning. A high `fit` and a high
  score together is the signal, once the description fits the need. A big repo with `fit 1` is often only a
  famous neighbour.
- The `rising` rows are new repos growing fast without your words in them. Judge them by what
  they make, not by the words.
- If few rows come back, your words are too narrow or too generic: change them, or run the full
  flow, which searches more ways.
- `hidden: N under 50 stars` is the thin tail. Look at it only if nothing above fits.

## Cost and limits

- A quick lookup runs the lenses E, P, M, Q, T and H (names, pairs, mechanisms, problems, topics,
  and the rising list of new repos that grow fast) plus one for the form. That is 20 to 100 searches, and GitHub allows about 30 a minute, so a
  large vocabulary takes minutes: give 3 to 6 word groups, not 20. `--budget N` caps the GitHub API
  calls (default 80; the skills.sh, npm and MCP registry searches do not stop at it) and `--seconds N` the time it stops starting searches (default 150; the lookup can end 20 to 40 seconds
  later, when the last searches finish; a slow host skips its searches instead
  of stretching the lookup); `--lenses` picks the lenses yourself.
- It leaves out code search (SKILL.md files), which GitHub limits to 10 a minute. Add it with
  `--lenses EPMQTK` when you are looking for skills and a few minutes are fine.
- Several agents on one token share the budget through a cache file in `~/.cache/github-scout`,
  so parallel lookups slow down instead of failing.
- Recall is lower than a full scan: see CHANGELOG.md for what the recall eval found.
- It records nothing. `--keep DIR` saves the scan in a new registry when you want to continue
  with `scan`, `pick` and `brief`.

## Example

```bash
github-scout quick "an agent skill that makes a GitHub repo show up when people ask an AI for tools" \
  -e "geo|generative engine optimization|aeo|生成式引擎优化" -e "github repo|readme|仓库" \
  -m "ai search visibility|citability|ai 搜索可见度" -p "geo skill for claude code" -p "让项目被 ai 搜索推荐" \
  --form skill
```

Words in both languages go in `-e` and `-m` too, not only in `-p`.
