# Lookup before building

A lookup answers one question before you build a tool, skill, workflow or component, or pick
between tools: does something good enough already exist to use or adapt? It runs in a subagent,
takes five to fifteen minutes, and hands back a verdict in about fifteen lines. When the answer
shapes the project (several candidates compete, the user wants a report, you will adopt one), run
the full flow instead.

Why it works this way. GitHub's search matches words, not meaning, and most of what it returns
for a need is noise: famous repos that share one word, tutorials, demos, new repos with farmed
stars. In about twenty real lookups that ran only `github-scout quick`, agents never adopted a repo
they did not already know. The good answers came from elsewhere: tools the model knew and the
table missed (wtpsplit for splitting unpunctuated speech, Konsta UI for an iOS-style kit), web
research, Hugging Face datasets, an awesome list read by hand. So a lookup asks people first and
checks the names on GitHub; GitHub's own search covers the new repos nobody has written about yet.

## Who runs it

The main agent does not run the commands or read this file. It hands the need to a subagent with
web search (Claude Code's Agent tool, a Codex subagent, or a background session) and keeps only
the answer. The work is searching and reading; any model that judges a repo by what it does, not
by the words it matches, is enough.

While the lookup runs, the main agent goes on with work that does not depend on it, but does not
build the thing in question: a lookup that comes back after the build is wasted.

The brief (its template is in `SKILL.md`) gives the need in one sentence, two to four Musts a fit
passes, the project and what it has, the form, any names the user gave, and the notes file.

## Steps

1. **What the project has, and names you already know.** Read what the project does today for
   this need; if it already uses or is wiring in a candidate, start from that one. Then, before
   any search, list the established tools, libraries, models and datasets you know for the need.
   Mark them "from memory" until step 5 checks them. Keyword searches miss many of these.
2. **Start the GitHub sweep.** It takes two to six minutes; run it in the background if your
   tools allow, and do step 3 meanwhile:
   `github-scout quick "<need>" -e … -m … -p … --form …`
   - `-e` names of things (platforms, formats, products), synonyms after `|`:
     `-e "xiaohongshu|小红书|rednote"`. Repeat for each thing.
   - `-m` how a solution works, in README words: `-m "mcp server" -m "logged-in browser"`. Name
     the method, not the runtime: `onnx`, `coreml` or `ggml` pull in every inference repo.
   - `-p` a short phrase a user of this would write, one per language.
   - `--form skill|mcp|cli|library|app|extension`. `skill` also reads skills.sh, `mcp` the MCP
     registry, `cli` and `library` npm.
   - Three to six word groups, each in English and Chinese, in the words projects use about
     themselves, not translations.
3. **Ask people, not GitHub.** Search the web in English and Chinese for what people use and
   recommend: `best <thing> for <need>`, `<need> open source`, `<known name> alternative`, and
   the same in Chinese; Reddit, Hacker News, X (x-scout when available), V2EX, 知乎, 掘金, 少数派.
   Read one awesome list for the field. Search the registry the form lives in: skills.sh, the MCP
   registry, npm, PyPI, and for models and datasets Hugging Face
   (`https://huggingface.co/api/models?search=<words>&sort=downloads&limit=20`, the same with
   `/api/datasets`). Note every repo or package that two independent places name, or that a post
   shows working.
4. **Read the sweep's table as leads, not a ranking.** Keep only rows whose description does the
   need. Skip a word that matched in another sense (`geo` is also geography), a famous repo with
   `fit 1` (a neighbour, not a fit), and a repo a few days old with thousands of stars until
   feedback backs it. The `rising` rows are new repos growing fast in the form and are much the
   same for every question: take one only if what it makes does the need.
5. **Check the candidates** from steps 1, 3 and 4: `github-scout look <owner/repo> …` gives facts,
   activity, project evidence and the start of the README; `--source` reads the code when the
   README does not say how it works. Drop dead repos, lures, and any that fail a Must.
6. **Search independent feedback on the two or three you will name.** One focused search per repo
   outside its repository, in English and Chinese, with its exact name or `owner/repo` and usage,
   review, output or problem terms. Open relevant hits and confirm the identity. Real use,
   third-party recommendations, concrete outputs and problems count; author promotion, reposts
   and directory listings alone do not. Say "no independent usage feedback found" or "not
   checked" when tools were missing. Neither alone disqualifies a repo.
7. **Answer** in this shape, which fits in 15 lines; the full notes go in the file the brief named:

   ```
   Verdict: use X | adapt X | borrow <idea> from X and build | nothing fits, build
   1. <link> · <stars> · pushed <date> · what it does for the need; Musts: all | fails <which>
      feedback: <one line, with a link> | none found | not checked · risk: <the one that matters>
   2. …
   Left out: <name (why)>, …
   Searched: <sources>; not covered: <a registry that did not answer, a time limit, …>
   ```

   Up to three candidates. "Nothing fits" is a good answer: name what came closest and why it
   fails.

## Reading the table

- Each row: score, stars, created, last push, repo, description, the lenses that found it, and
  `fit` (how many of your word groups its own name, description and topics match). `installs` is
  the skills.sh install count; `?` after a repo's kind means a guess.
- `fit` counts words, not meaning. A high `fit` and a high score together is the signal, once the
  description fits the need.
- Under the table: how many repos it hid (under 50 stars, not pushed in 6 months, lures) and any
  search that failed or was skipped. `hidden: N under 50 stars` is the thin tail; look at it only
  if nothing above fits.
- Few rows means the words are too narrow or too generic: change them once, then rely on step 3.

## Cost and limits

- The sweep runs the lenses E, P, M, Q, T and H (names, pairs, mechanisms, problems, topics, and
  the rising list) plus one for the form: 20 to 100 searches. GitHub allows about 30 a minute.
  `--budget N` caps the GitHub API calls (default 150; the skills.sh, npm and MCP registry
  searches do not stop at it), `--seconds N` the time it stops starting searches (default 300;
  it can end 20 to 40 seconds later; a slow host skips its searches instead of stretching the
  sweep), `--lenses` picks the lenses yourself.
- It leaves out code search (SKILL.md files), which GitHub limits to 10 a minute. Add it with
  `--lenses EPMQTHK` when you are looking for skills.
- Several agents on one token share the budget through a cache file in `~/.cache/github-scout`,
  so parallel lookups slow down instead of failing.
- It records nothing. `--keep DIR` saves the scan in a new registry when you want to continue
  with `scan`, `pick` and `brief`.

## Example

The brief:

```
Look for what already exists before we build this. Follow references/lookup.md in the
github-scout skill; do not change the project.
Need: split long unpunctuated speech transcripts into sentences, offline, in Chinese and English
Must: runs on a Mac without a server; handles text with no punctuation; under 1 GB of model
Project: ~/code/transcriber; it already has Whisper output as plain text
Form: library
Known names: none
Answer in at most 15 lines. Write your notes to notes/lookup-sentence-split.md.
```

The sweep the subagent starts in step 2:

```bash
github-scout quick "split unpunctuated speech transcripts into sentences, offline" \
  -e "transcript|asr|speech to text|语音转写" -m "sentence segmentation|punctuation restoration|断句|标点恢复" \
  -p "add punctuation to whisper output" -p "语音识别结果自动加标点" --form library
```
