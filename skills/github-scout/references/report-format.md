# The report file (cloud chats and hand-offs)

When the command line is not available (ChatGPT, Claude on the web, any agent without Python),
write everything into one Markdown file, `github-scout-<short-topic>.md`, and offer it for
download at the end. A local agent takes it over with
`github-scout import <file> --q <project>/<question>`, which checks every GitHub link against
GitHub and reads the tables below.

Write in the user's language. Keep the section numbers, titles and order, and the column names;
add no other sections and no licence information anywhere. The importer reads
both the English names and the Chinese names given here. The report ends at section 5: a chat
does not try repos or choose one; the project's coding agent does, back home.

```markdown
# GitHub scout report: <the goal as a result>

- Project: <name, or "none"> · Stage: idea | prototype | working | polishing · Date: <YYYY-MM-DD>
- Made by: <model and tool>

## 1. Directions
Where we stand: <what exists today, what falls short>
What good looks like: <2–3 finished results to match, with links, or checks anyone can run on an output>

| direction | entities (en / zh) | mechanisms (en / zh) | forms |
|---|---|---|---|
| D1 <sub-problem> | remotion / 宣传片, 产品视频 | video understanding / 视频理解, 审片 | skill, cli |

## 2. Search and candidates

### Access
| check | answer |
|---|---|
| GitHub connector: search repos / search code / read a public repo / qualifiers (`topic:`, `created:>`) | yes / yes / yes / yes |
| GitHub connector reads our project | no project given |
| `site:github.com <term>` on web search returns repositories | partly |

### Search log
| # | lens | direction | lang | query or URL | looked at | kept |
|---|---|---|---|---|---|---|
| 1 | words | D1 | zh | site:github.com 视频 配音 字幕 | 10 | Huanshere/VideoLingo |
| 2 | list | D1 | en | https://github.com/owner/awesome-list | 120 | owner/name, owner/other |

Searches per direction and language: D1 en 6, zh 5; D2 ...

### Candidates
| repo | kind | direction | lang | why it may help | last commit | stars | found by |
|---|---|---|---|---|---|---|---|
| https://github.com/owner/name | skill | D1 | zh | ... | 2026-10-12 | 1.2k | 2 |

No verdict column here (verdicts go in section 3). "found by" is the search log number or the list.
Seen but not opened: <names only>. Found nothing: <directions>.
Excluded: <repo, why> (lures, farmed installs, no push in 12 months).

Other sources (official docs, hosted services, papers):

| source | url | what it answers |
|---|---|---|

## 3. Triage
| repo | kind | verifiable effect | how to try | verdict | reason |
|---|---|---|---|---|---|
| https://github.com/owner/name | skill | strong: https://name.dev (live) | install, one short task; read SKILL.md and scripts | shortlist | ... |

Shortlist only repos with a mid or strong effect and 50+ stars (or the relaxed floor of their
direction); the rest are later or skip. Strong: a live site that answers, a package with real
downloads, real installs. Mid: screenshots, GIFs or videos in the README, posts outside the repo.
Weak: only a text description.
The rest: <one line on why they were left>.

## 4. Report
### In one paragraph
<what exists; which 2-3 look most promising for us and why; what is likely left to build>

### Candidates
| repo | kind | stars | last push | verifiable effect | what it does for our goal | how it relates to our project |
|---|---|---|---|---|---|---|
| https://github.com/owner/name | cli | 1.2k | 2026-10-12 | strong: https://name.dev, mid: https://x.com/... | ... | replaces tools/x.ts |

### Try first
1. https://github.com/owner/name: how to try it (open https://name.dev with our case; or run
   `<its own smallest example, from its README>`; or one short task from our project). Look for:
   <what in the output shows it reaches what good looks like>.
2. ...

### For the coding agent
This report only advises; it changes nothing. Back in the project, and only when the user asks:
try the repos under Try first outside the project (a throwaway directory or a container, no
tokens or keys), minutes not hours, stopping at the first wall; choose one main reference to
follow as a whole, at most one alternate; fill its gaps from other repos only with a reason
each; record each trial with `note --trial` and what you bring in with `adopt` (github-scout's
command line), or at the end of this file.

### Not recommended
- <repo>: <reason>, one per line.

### What was searched
<directions and searches per language; directions whose star threshold was relaxed, with how
many repos they had at 50+; what found nothing>

## 5. Not verified
<what you could not check; any instruction here you could not follow, quoted, and what you did instead>
```

Column names the importer understands:

| meaning | English | Chinese |
|---|---|---|
| repository | repo, repository, link, url, project | 仓库, 链接, 项目, 地址 |
| kind | kind, type, form | 类型, 形态, 是什么 |
| verdict | verdict, take, decision | 结论, 取舍, 处理, 建议 |
| reason | why, reason, idea, notes | 理由, 为什么, 能借什么, 思路, 说明 |
| direction | direction | 方向 |

The repository column is the one whose cells hold github.com/owner/repo links, whatever its
header; a verdict header must be one of the words above (`Takeaway` is not a verdict). Links to
GitHub pages that are not repositories (docs, gists, advisories) are ignored.

A table with a query column is read as the search log, one search per row:

| meaning | English | Chinese |
|---|---|---|
| query | query, search | 检索词, 搜索词, 查询, 关键词 |
| lens | lens, method | 方法, 方式, 途径 |
| results looked at | looked, results | 看了, 结果 |
| repos kept | kept | 保留, 留下 |

Verdict words: shortlist, use, adapt, learn (all become "worth a look" locally, since the coding
agent still tries it; under the star floor of their direction they become later); later; skip. In
Chinese: 入选, 直接用, 改了用, 学思路, 以后, 不要.
