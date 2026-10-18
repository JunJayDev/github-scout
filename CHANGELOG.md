# Changelog

## 0.2.0 (unreleased)

Renamed from reuse-first to github-scout, and split by stage.

- Windows (found by the first CI run): output is written as UTF-8, so a piped scan table with
  Chinese rows no longer crashes on the default codepage; `check` and `look --source` print
  registry and repo paths with forward slashes; `ask` stores the project's resolved path; tests
  read and write files as UTF-8.
- Recall. A test scan on 2026-10-18 (125 searches, 525 repos) missed the two closest
  competitors, skills with 131 and 139 stars that do what github-scout does. Broad words sorted
  by stars returned only giants, the vocabulary said each idea one way, and the star gate hid 16
  direct rivals.
  - A single-term search that matches over 1,000 repos is read again, 100 rows in GitHub's
    best-match order, after the planned searches: mechanisms first, then problems, entities and
    recent, the narrowest first within each, at most 12 a scan. In the test, `"existing
    solutions"` in READMEs (8,176 repos) put the 131-star competitor 72nd by best match and
    nowhere in the first 100 by stars. Generic words (github, open source, 开源, skill, tool ...) are not read again and take
    no slot in the capped lenses (K, S, D, N, R) or the derived topics. A term with Chinese in it
    no longer becomes a topic (`去 AI 味` made `topic:ai`). A topic search that returned every repo
    of its topic skips its 12-month repeat. skills.sh is read 100 rows deep instead of 30: the
    two competitors sat at 57 and 84.
  - The capped lenses (K, S, D, N) take the heads of six groups per language before any synonym:
    entity groups first (up to four), mechanism groups fill the rest. With two entity groups the
    slots used to go to synonyms (`gh search`) instead of the third mechanism (`prior art`).
    Questions with four or more entity groups plan as before.
  - A scan keeps, past its best 400 rows, up to 400 more whose own words match the vocabulary,
    and every list it found (lists are listed apart for `--expand`, not ranked against tools).
    Reading deeper found two must-find repos that the 400-row cut then dropped.
  - `scan --plan` warns about broad words (the generic ones, and terms an earlier scan found
    matching 10,000 repos or more) and about mechanism groups said one way only in a language.
    The scan header names the broad words with their counts. Every search in the log keeps
    `total`, the number of repos it matched.
  - The rising list keeps only rows that show one of the question's forms in their name,
    description or topics; `--all` shows the rest. In the test, 63 of 125 rising rows were
    other forms, among them a CarPlay receiver and a graphics driver.
  - The header names the first five rows under 50 stars that fit four or more vocabulary groups,
    for questions about who else does this. The threshold stays at 50.
  - `evals/run.py` scans each case in `evals/evals.json` for real, with a fixed vocabulary per
    case, and reports where each must-find repo sits (table row, rising row, list, or why it is
    hidden); cases with the same vocabulary share a scan. New case `search-first-skills`: the
    2026-10-18 draft vocabulary, revised by an agent that saw only the new `scan --plan`
    warnings. Real runs on 2026-10-19: all 10 must-find repos in 5 cases kept (OpenCLI row 3,
    anatomy rising h1, the writing trio rows 4, 63 and 306, the video trio rows 2, 5 and 14,
    search-before-build row 147, instructa/agent-skills as a list). The old code on the same
    vocabularies kept 2 of 3 writing repos (tramstop never returned) and 1 of 2 competitors
    (instructa never returned); on the 10-18 draft words it kept neither competitor, the new
    code keeps instructa. A scan costs 159 to 196 API calls and 7 to 12 minutes (the old code:
    156 to 175 calls on the same words).
- Trials run apart: dig tells the agent to try repos in a throwaway directory or container, outside
  the project, with no tokens or keys in the environment, after reading install scripts and hooks.
  SECURITY.md said downloaded code never runs; that holds for the command line only, and now says
  so. README: licences are left out on purpose (a belief, not a gap); the no-install cloud file
  moves up to Install; a full search takes five to ten minutes (a test run: 125 searches, 156 API
  calls, 7.6 minutes).
- Quality gate (user, 2026-10-18). A run that took one idea from each of 12 repos made an
  explainer film the user called completely wrong: nobody had looked at what those repos made,
  run one of them, or said what good looks like. Now a repo is a reference only with results to
  look at and 50+ stars (`GITHUB_SCOUT_MIN_STARS`); the best two or three are tried before one is
  chosen; the answer follows one backbone as a whole (at most one alternate) and fills only its
  named gaps; other repos' ideas go to a Not adopted appendix. New and fast-growing repos are
  still searched for, but no longer pick.
  - `pick` refuses a shortlist under the threshold without `--low-stars "<why>"`, recorded in the
    ledger; lists are exempt and unknown stars warn. Such rows leave the scan table and are
    counted in its header; `import` keeps a shortlist under the threshold as `later`.
  - `note --take use|adapt|learn` needs results on the card (`--results <links>`, or
    `--no-results "<why>"`) and the same `--low-stars`; both reasons go on the take and into the
    ledger. `note --trial` writes a dated line into the card's new Results and trial section and
    sets `level: trial`. `look` shows the homepage and the README links that look like results;
    `show` and the site show a card's results.
  - Questions: What good looks like; an answer of one paragraph, Backbone, Gaps to fill, Trial
    runs, Against what we have, Next steps, Not adopted; `backbone:` and `alternate:` in the
    frontmatter. `check` warns when a named backbone was not tried or a repo the answer relies
    on lacks results or stars without a reason. `brief` follows the new layout, lists each
    source's role, stars, results and level, and ends with the appendix. Questions and cards
    written before still read, brief and check as they did.
  - All eight recall cases in `evals/evals.json` have 50+ stars (the smallest,
    alchaincyf/tramstop-skill, has 53), so the threshold hides none of them.
- `note` on a card that another question already wrote: the idea goes at the end of the first section,
  marked with the question, instead of above what was there; `--watch` adds to the card's list and
  `--summary` replaces its summary. A repo with no description on GitHub gets the first sentence of the
  idea as its summary, so `check` does not stop on an empty one (found on the first real run of all six
  stages, 2026-10-18).
- Seven skills instead of one: `github-scout` runs the search; `github-scout-plan`, `-search`,
  `-triage`, `-dig` and `-brief` run alone, and `github-scout-adopt` carries a brief into the
  project. Every stage says what to do with the command line and without it, so the same skills
  run in a cloud chat on web search alone.
- `cloud/github-scout.md`: the skills as one file to upload to ChatGPT or Claude on the web,
  generated by `tools/build-cloud.py`. A local agent stops after the directions for the user to
  confirm; a cloud chat does not stop unless asked.
- `brief`: an answered question becomes a hand-off file for the coding agent, with each source's
  take and reviewed commit, ending with one ready-to-fill `github-scout adopt` line per picked
  repo. The brief itself never changes the project.
- Stage 6, adopt: `github-scout-adopt` is the only stage that changes the project. The project's
  coding agent runs it in the project's own repository when the user asks: a mode per repo
  (depend, vendor, port, skill, tool, data), provenance in copied and ported files, one commit per
  repo, each step checked before it is recorded. `adopt <repo> --q <p/q> --mode … --into …
  [--from …]` records it on the card (`adopted`: our paths, their paths, their commit, our commit)
  and in the ledger; the same paths again replace the entry, and `--drop` keeps it, marked dropped.
  `updates` lists adopted repos first and counts the upstream commits that touched each file we
  took since we took it; `show`, the site and the brief show adoptions. Until now no brief had
  reached a project, and the registry could not tell which upstream changes mattered. The cloud
  file says only that the local coding agent adopts.
- `updates`: a compare that fails (the reviewed commit is no longer on the branch) no longer
  reads as up to date.
- `import`: a report from a cloud chat comes back into the registry (the question is created from the report when missing); every GitHub link is checked
  and the ones that do not exist are listed; table columns (kind, verdict, reason) are kept.
  Verdicts count only outside the Candidates section: a ChatGPT Pro run wrote "learn" on all 84
  candidate rows, which would have shortlisted every one.
- Cloud search assumes what a web chat has: web search and maybe a GitHub connector, no browser.
  It checks those tools first, runs each lens of `scan` as search queries (`site:github.com`,
  topic pages, SKILL.md files, skills.sh, MCP and npm directories, trending sites, Chinese
  communities) in both languages, reads every awesome list it opens, follows the shortlist's
  authors and links, and logs every search. The first ChatGPT Pro run used long web queries only
  and missed the best three repos, which a short query and an awesome list it had opened both show.
- `import` reads the report's search log into the scan record, and its directions into the
  question when the question has no words yet, so `scan` can run GitHub's API on them; `scan --show`
  names the rows that came only from the API (the repos the report missed).
  Directions take turns (and languages within them) so the cap keeps every direction; generic
  words a chat lists as entities (Claude Code, Codex, skill, plugin, SKILL.md, 技能) and step
  chains are left out: a third test run put a 280k-star agent harness first because of them.
- Licences are out of scope: no licence checks, warnings, columns or ranking penalty.
- `ask` creates the registry (`~/.github-scout`) and the project on first use; inside a git
  repository the project is named after it and its code path recorded.
- Lures (game cheats, cracks, "Ultimate Trainer 2026") and skills.sh install counts far beyond a
  repo's stars are left out of the table and counted in its header.
- Only scan files are read from a question's scan folder; other files may sit beside them.
- Registries, variables and config files from before the rename are still read.
- `README.zh-CN.md`, `AGENTS.md`, `.codex-plugin/plugin.json`, `evals/evals.json` (recall cases).

## 0.1.0 (unreleased)

First release.

- Questions instead of searches: each has a stage (`idea`, `prototype`, `working`, `polishing`)
  that decides what is worth borrowing, and an answer section that is the deliverable
  (ideas first, then practices and components, compared with what the project already has).
- Ranking: relevance, then whether a repo is young and maintained, then stars. No push in 3
  months ranks far down, 6 months is hidden, 12 months is dropped; searches ask GitHub for
  maintained repos only.
- 14 search lenses, including skills.sh (install counts) and the official MCP registry;
  web/X links and awesome lists feed the same ranking.
- A rising lens that needs no vocabulary: repos created in the last two months in the form's
  topics (skills, MCP servers) and breakouts from anywhere. Those no vocabulary matches are
  listed apart, fastest-growing first, for the agent to judge (`pick h1`). It found a
  11k-star skill created a week earlier that no word list could reach, because its own
  description never names the use people found for it.
- Languages: a question lists `langs` (default `[en, zh]`, `ask --langs`), because in real runs
  Chinese projects supplied half of the repos picked while only a fifth of the searches were in
  Chinese. Terms are told apart by script. Pairs and combinations are built within one language
  from each group's first term in it (same totals: 15 pairs, 9 combinations). Combinations and the
  capped lenses (mechanisms in READMEs, SKILL.md code, skills.sh, npm) take turns between languages;
  pairs and recent give the first language its full share and the others what is left; the
  MCP registry lens keeps Latin-script terms, since it matches ASCII server names (seven Chinese
  searches there found nothing). Every mechanism synonym is now searched, not only the first ten.
  `check`, `ask --update` and `scan --plan` warn about a vocabulary group with no term in a listed
  language, and the scan header counts searches per language and rows with a Chinese description.
  The default call budget is 250, so the last lenses are no longer cut off on large vocabularies.
  Replayed on three answered questions, Chinese went from 10–33% of the searches with words to
  40–50%; the new Chinese searches found about fifteen relevant Chinese writing skills the earlier
  scans never saw (most through `活人感`, `像人写` and `AI 痕迹`), a handful for browser automation,
  and little of use for video. Chinese pair and recent searches brought mostly noise, which is why
  they only fill leftover slots.
- Cards (idea first) with five takes: use, adapt, learn, later, skip; a ledger of every verdict;
  upstream tracking limited to the paths a card watches.
- 12 commands: `init`, `new-project`, `ask`, `find`, `scan`, `pick`, `look`, `note`, `show`,
  `updates`, `site`, `check`. English and Chinese templates.
- Claude Code plugin manifest.
