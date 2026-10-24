# Changelog

## 0.2.0 (unreleased)

Renamed from reuse-first to github-scout, and split by stage.

- The lookup before building runs in a subagent and asks people first (owner, 2026-10-25). The main agent
  sends a short brief (need, Musts, project, form, known names) and keeps only a verdict of about fifteen lines;
  it never runs the commands or reads the steps. The subagent lists what it already knows, searches the web,
  awesome lists and the registries (skills.sh, MCP registry, npm, PyPI, Hugging Face) for what people use, runs
  `github-scout quick` as the GitHub sweep for new repos, reads its table as leads by meaning, checks the
  candidates with `look`, searches independent feedback on the two or three it names, and answers use, adapt,
  borrow an idea, or nothing fits. The subagent runs on Sonnet by default (the trial below ran on it).
  `references/quick.md` is now `references/lookup.md`.
  Why: in about twenty lookups across projects (2026-10-22 to 24) that ran `quick` in the main session, agents
  never adopted a repo they or the user did not already know, and at least six built their own. Keyword rows
  were mostly neighbours (a 76.8k-star job-search agent for "Bilibili covers"), the rising rows were the same
  five repos whatever the need, nearly every run hit the 150 s limit, and the table, `look` and the doc put
  13 to 16 KB into the main context. The good answers came from the model's own knowledge (wtpsplit, Konsta
  UI, missed by the table), web research, Hugging Face datasets and an awesome list read by hand.
  - Trial (2026-10-25): a subagent given only the brief and `lookup.md`, on a need where the table had missed
    (split unpunctuated speech transcripts into sentences, Chinese and English, on a Mac), answered in 7.7
    minutes with three candidates that pass the Musts: SaT (wtpsplit), which the project was already wiring in,
    from step 1; sherpa-onnx's CT-Transformer punctuation and FireRedPunc from the web, X and Hugging Face. Its
    two GitHub sweeps gave none of them. Its notes on the doc (a project already using a candidate, a Hugging
    Face command, an answer shape that fits 15 lines, runtime words in `-m`) are in `lookup.md`.
  - `quick`: defaults 150 GitHub calls, 300 s and 20 rows (were 80, 150 s, 10): a subagent can wait, and the
    topic searches that ran last were the ones cut. Lenses and ranking unchanged. Its last line says the rows
    are leads and points to the lookup. Recall (`evals/run.py --lenses quick --budget 150 --seconds 300`,
    2026-10-25): 10 of 10 repos in 5 cases, 4.6 to 6.1 minutes a scan (was 9 of 10 at 80 calls and 150 s;
    `user-w-ui/search-before-build` now comes back). Kept is not seen: that repo sits at row 254 and
    `alchaincyf/tramstop-skill` at row 276, past the 20 rows shown, which is why the lookup leans on the web.
  - `tools/build-cloud.py`: a heading that names a local-only command drops its whole section, code blocks
    included.

- `quick` (owner, 2026-10-22). A one-off lookup for the moment before you build, install or pick something: no
  registry, no plan to confirm, one ranked table in one to three minutes, run by a cheap model if you like. It
  runs the lenses E, P, M, Q, T, H and one per `--form` (skill: skills.sh; mcp: the MCP registry; cli and library: npm),
  never code search unless `--lenses` says so (10 a minute), with the scan's filters. Several agents share one
  GitHub budget through `~/.cache/github-scout`. `look` now works without a registry when it records nothing.
  Why: a hand search of seven queries missed the first-ranked candidate (a 19.6k-star skill) that `quick` put on top;
  the full flow took too long for small questions, so agents did not use it. `evals/run.py --lenses` measures a
  lens set against the recall cases.
  - Recall: on the five recall cases, with their large vocabularies (97 to 123 searches) and the default limits
    (80 GitHub calls, 150 s), `quick` keeps 9 of 10 repos in about three minutes a case; the last recorded full
    scan kept all 10. The one it missed, `user-w-ui/search-before-build`, needs more searches than the limits
    allow. A typical lookup has far fewer words and finishes sooner. Each limit trades recall for time: five
    passes with other lens orders each kept 8 of 10, a different two missing.
  - Limits that keep it quick: `--budget` counts GitHub calls only (skills.sh, npm and the MCP registry searches
    do not stop at it); `--seconds` (default 150) stops starting searches; a registry that does not answer is asked
    once, and non-GitHub hosts wait 20 s, not 60 (the MCP registry did not answer from the test machine).
  - Scan: `run(order=, seconds=)`; `Client.github_calls`.
- Skills: `description` values with a colon are quoted (adopt, brief, dig were not valid YAML); each skill has
  `metadata.improve-repo` and an "Improve this skill" section: with write access, branch, test and pull request;
  without it, report and offer a patch. The cloud file leaves the section out.

- Report first (owner, 2026-10-19). github-scout finds, filters and reports; trying the
  candidates and choosing the one to follow are the project's coding agent's work, after the
  report and only when the user asks.
  - Stages: 1 plan, 2 search, 3 triage, 4 brief (the report), then the coding agent's 5 dig (try
    the two or three, choose one main reference, fill its gaps with a reason each) and 6 adopt.
    The skill names stay, so installs keep working; their descriptions, stage numbers and text
    changed. The cloud file leaves out dig as it leaves out adopt: a chat ends with the report.
  - The report (`brief`, and section 4 of the cloud report): the goal and what good looks like;
    one paragraph on what exists, the two or three most promising and why, what is likely left to
    build; a candidate table (repo, kind, stars, last push, verifiable effect, what it does for our
    goal, how it relates to our project); Try first, with how to try each and what to look for;
    what the coding agent does next, with one `note --trial` line and one `adopt` line per repo;
    Not recommended; what was searched, with the scans' coverage and every relaxed threshold.
  - The question template's answer has those sections and Trials and choice, for the coding
    agent. `picked:` is the try-first list; `backbone:` and `alternate:` are optional, set by the
    coding agent. Answers written on 2026-10-18 (Backbone, Gaps to fill) and before still brief
    as they did. `check` no longer asks a report for a backbone or trials; it holds the repos to
    try to the effect and star gates, and asks a backbone the coding agent set to have been tried.
- Stars per direction (owner, 2026-10-19). For each entity or mechanism group, the maintained
  repos at 50+ stars whose own words name it are counted; under 5, that group's rows are shown
  down to 20 stars, and under 5 again down to 10, never lower. The scan header says which
  (`relaxed (...): stroke order to 20 stars (only 3 at 50+)`), rows carry `relaxed: <group>`, and
  the saved scan records `relaxed` and each row's `floor`. `pick`, `note` and `import` take such
  rows without `--low-stars` and record the relaxation as the reason; under the floor still needs
  one. Only floors under the threshold apply (`GITHUB_SCOUT_MIN_STARS=5` relaxes nothing).
- Verifiable effect instead of results (owner, 2026-10-19). Most projects show their results
  outside the repo, and `look` counted only video links and words like demo, and skipped README
  screenshots. Now it grades: strong (the homepage or a README demo link answers one short
  request, an npm package has 100+ downloads last month, the scan recorded 100+ skills.sh
  installs), mid (images, GIFs and videos in the README, badges, logos and icons left out), weak
  (only text). The requests carry no token. `note --results` takes any link; `use`, `adapt` and
  `learn` need a mid or strong one (posts on X, Bilibili, YouTube, blogs, Xiaohongshu count as
  mid; the repo's own text pages are weak) or `--no-results "why"`. `show`, `brief` and the site
  say "verifiable effect"; the flags keep their names. Cards get a "Verifiable effect and trial"
  section; trials still go into "Results and trial" on older cards. `look --json` gives `effect`
  in place of `result_links`.

- Fixes from a review on 2026-10-19, each reproduced first.
  - `updates` compares against the repo's current default branch, and says when it moved
    (`default branch master -> main`); before, a renamed branch broke the compare for good and
    `--done` wrote `commit: None`, which `check` refused. `--done` never writes an empty commit,
    and `--to` takes a tag or branch.
  - `adopt` again with the same `--q` and `--into` updates the entry: `--from`, `--at` and `--note`
    left out keep what was recorded. Following the hint after `updates` used to erase them.
  - `adopt --from` paths must exist upstream at `--at` (GitHub lists no commits for a path that is
    not there, so a typo read as unchanged for ever); `updates` says when a path we took is gone
    from the default branch.
  - `pick` reads row numbers against the table printed last: after `scan --show --all`, `pick 2`
    is row 2 of that table, not of the default one. Numbers outside it are refused. The table's
    rows are kept in `cache/tables/`.
  - `import` finds the repository column by its github.com links, so `| Project | Link | Verdict |`
    and `| 项目 | 地址 | 结论 |` give rows; a verdict header must be one of the verdict words
    (`Takeaway` was read as the verdict); GitHub links that are not repositories (docs.github.com,
    gists, advisories) are no longer taken for repos and reported as invented.
  - `brief` shows the take recorded for the question's own project, not another project's
    question of the same name.
  - A repo given as a github.com URL finds its card in `note`, `show`, `adopt`, `look` and
    `updates`.
  - `ask` without a project names it after the git folder as a valid id (`My App` -> `my-app`).
  - Two scans of a question in the same second keep both (the second id gets `-2`).
  - A reply that is not JSON (a challenge page from skills.sh) or is cut short fails only its own
    search; before, it ended the whole scan with a traceback and nothing saved.
  - A scan prints a progress line to stderr every 20 API calls: searches done of planned, time so
    far, a rough guess of the time left. stdout is unchanged; `--quiet` turns it off.
  - The ledger: a reason with U+2028 (text pasted from web pages) no longer splits its entry in
    two, entries appended to a file without a final newline stay separate, and a line that is JSON
    but not an object is reported by `check` instead of crashing it and `show`.
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
