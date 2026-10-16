# The report file (cloud chats and hand-offs)

When the command line is not available (ChatGPT, Claude on the web, any agent without Python),
write everything into one Markdown file, `github-scout-<short-topic>.md`, and offer it for
download at the end. A local agent takes it over with
`github-scout import <file> --q <project>/<question>`, which checks every GitHub link against
GitHub and reads the tables below.

Write in the user's language. Keep the section titles and the column names. The importer reads
both the English names and the Chinese names given here.

```markdown
# GitHub scout report: <the goal as a result>

- Project: <name, or "none"> · Stage: idea | prototype | working | polishing · Date: <YYYY-MM-DD>
- Made by: <model and tool>

## 1. Directions
Where we stand: <what exists today, what falls short>

| direction | entities (en / zh) | mechanisms (en / zh) | forms |
|---|---|---|---|
| D1 <sub-problem> | remotion / 宣传片, 产品视频 | video understanding / 视频理解, 审片 | skill, cli |

## 2. Candidates
| repo | kind | direction | lang | why it may help | last commit | stars | found by |
|---|---|---|---|---|---|---|---|
| https://github.com/owner/name | skill | D1 | zh | ... | 2026-10-12 | 1.2k | site:github.com 审片 skill |

Searches per direction and language: D1 en 4, zh 3; D2 ...
Found nothing: <directions>. Excluded: <repo, why> (lures, farmed installs, no push in 12 months).

## 3. Triage
| repo | kind | route | verdict | reason |
|---|---|---|---|---|
| https://github.com/owner/name | skill | read SKILL.md and scripts in full | shortlist | ... |

The rest: <one line on why they were left>.

## 4. Findings
### owner/name
- Idea: <the design decision that makes it work>
- Where: <file paths>
- Why it is not obvious: ...
- Evidence: ...
- What to take at our stage: ...
- Risks: <licence, maintenance, network, credentials>
- Take: use | adapt | learn | later | skip

## 5. Answer
<one paragraph: what to take from whom; the part nobody covers>

| ours | theirs | the difference | take it or not |
|---|---|---|---|

## 6. Brief for the coding agent
This brief only advises; the coding agent makes the changes and checks each one.

1. <files to change, what to change> because <idea, repo and file>. Check: <how>. Do not copy: <licence notes>.
2. ...
```

Column names the importer understands:

| meaning | English | Chinese |
|---|---|---|
| repository | repo, repository, link, url, project | 仓库, 链接, 项目, 地址 |
| kind | kind, type, form | 类型, 形态, 是什么 |
| verdict | verdict, take, decision | 结论, 取舍, 处理, 建议 |
| reason | why, reason, idea, notes | 理由, 为什么, 能借什么, 思路, 说明 |
| direction | direction | 方向 |

Verdict words: shortlist, use, adapt, learn (all become "worth a look" locally, since the local
agent still reads the code); later; skip. In Chinese: 入选, 直接用, 改了用, 学思路, 以后, 不要.
