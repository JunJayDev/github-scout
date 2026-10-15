# Changelog

## 0.1.0 (unreleased)

First release.

- Questions instead of searches: each has a stage (`idea`, `prototype`, `working`, `polishing`)
  that decides what is worth borrowing, and an answer section that is the deliverable
  (ideas first, then practices and components, compared with what the project already has).
- Ranking: relevance, then whether a repo is young and maintained, then stars. No push in 3
  months ranks far down, 6 months is hidden, 12 months is dropped; searches ask GitHub for
  maintained repos only.
- 13 search lenses, including skills.sh (install counts) and the official MCP registry;
  web/X links and awesome lists feed the same ranking.
- Cards (idea first) with five takes: use, adapt, learn, later, skip; a ledger of every verdict;
  upstream tracking limited to the paths a card watches.
- 12 commands: `init`, `new-project`, `ask`, `find`, `scan`, `pick`, `look`, `note`, `show`,
  `updates`, `site`, `check`. English and Chinese templates.
- Claude Code plugin manifest.
