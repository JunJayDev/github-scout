# The report file (cloud chats and hand-offs)

When the command line is not available (ChatGPT, Claude on the web, any agent without Python),
write everything into one Markdown file, `github-scout-<short-topic>.md`, and offer it for
download at the end. A local agent takes it over with
`github-scout import <file> --q <project>/<question>`, which checks every GitHub link against
GitHub and reads the tables below.

Write in the user's language. Keep the section numbers, titles and order, and the column names;
add no other sections and no licence information anywhere. The importer reads
both the English names and the Chinese names given here.

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
| repo | kind | results | route | verdict | reason |
|---|---|---|---|---|---|
| https://github.com/owner/name | skill | https://owner.github.io/name/showcase | try one task; read SKILL.md and scripts in full | shortlist | ... |

Shortlist only repos with results to look at and 50+ stars; the rest are later or skip.
The rest: <one line on why they were left>.

## 4. Findings
### owner/name
- Results: <links to what it made>
- Stars: <n>
- Trial: <the command a local trial runs, from its README; not run in this chat>
- How it works: <the design decision that makes it work, with file paths>
- Gaps: <what it does not do for us>
- Risks: <maintenance, network, credentials>
- Take: use | adapt | learn | later | skip

## 5. Answer
<one paragraph: the repo to follow as a whole, what fills its gaps, what is left to build>

Backbone: <repo URL> · results: <links> · stars: <n> · trial to run first: <command>
Alternate: <repo URL, or none>

| gap in the backbone | filled from | why |
|---|---|---|

| ours | the backbone's | the difference | take it or not |
|---|---|---|---|

Not adopted: <repo: its idea, why not>, one per line.

## 6. Brief for the coding agent
This brief only advises; the coding agent makes the changes and checks each one.

1. Run the backbone's own smallest example in our project: <command>. Stop and report if it fails.
2. <files to change, what to change> because <the backbone's way, or the gap it fills, with repo and file>. Check: <how>.
3. ...

## 7. Not verified
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

A table with a query column is read as the search log, one search per row:

| meaning | English | Chinese |
|---|---|---|
| query | query, search | 检索词, 搜索词, 查询, 关键词 |
| lens | lens, method | 方法, 方式, 途径 |
| results looked at | looked, results | 看了, 结果 |
| repos kept | kept | 保留, 留下 |

Verdict words: shortlist, use, adapt, learn (all become "worth a look" locally, since the local
agent still tries and reads it; under 50 stars they become later); later; skip. In Chinese: 入选,
直接用, 改了用, 学思路, 以后, 不要.
