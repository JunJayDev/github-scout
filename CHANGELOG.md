# Changelog

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
