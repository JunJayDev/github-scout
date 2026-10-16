[English](./README.md) · **中文**

# github-scout

**你的 agent 动手之前，先去 GitHub 找别人已经做过的，读懂最要紧的几个项目，再给写代码的 agent 一份简报：从谁那里拿什么思路，用到你代码的哪里。**

agent 爱重复造轮子，因为它像新手一样搜。有个项目要用登录好的浏览器读写 Reddit、X 和小红书。该用的工具有 3 万星，它介绍自己是 "Make any website into CLI & use your logged-in browser by AI agent"。按星数排序的 GitHub 搜索里，它排在这里：

| 搜法 | 那个工具排第几 |
|---|---|
| `social media automation` | 前 8 名没有 |
| `自媒体 运营` | 前 8 名没有 |
| `"reddit" "xiaohongshu" in:readme`（两个具体的站） | **第 1** |
| `"logged-in browser"`（它怎么做到的） | **第 1** |

好项目用「碰什么」和「怎么做」介绍自己。github-scout 替你把这些搜法写出来，中英文各搜一遍，一次跑 140 次左右，再把结果读完。

## 安装

```bash
npx skills add <owner>/github-scout -g
```

或者直接对你的 agent 说：「帮我安装这个仓库里的 skill：https://github.com/<owner>/github-scout」。

Claude Code 也能用插件装：先 `/plugin marketplace add <owner>/github-scout`，再 `/plugin install github-scout@github-scout`。

命令行部分要 Python 3.9+ 和登录过的 `gh`（或者 `GITHUB_TOKEN`）。别的不用配：第一次提问会在 `~/.github-scout` 建好登记库。

## 怎么用

在你的项目里打开 agent，说你要什么：

> 用 github-scout：让我们 agent 渲染的产品宣传片，剪辑和动效像专业剪辑师做的。

它先读你的项目，列出检索方向，**停下来等你确认**。确认后它去搜、去挑，读最要紧的几个项目的代码，最后写一份给开发 agent 的简报。它不改你的项目。

**不想在本地装？** 在 ChatGPT 或 Claude 网页版里上传 [`cloud/github-scout.md`](cloud/github-scout.md)，写上你的目标，能附上项目的压缩包更好。它只靠网页搜索就能跑；除非你要求，中途不停；最后给你一个报告文件。回到本地，运行 `github-scout import 报告.md --q <项目>/<问题>` 就能接手，每个链接都会去 GitHub 核实。

## 五个阶段

每个阶段是一个 skill，能单独用；`github-scout` 按顺序全跑。

| skill | 做什么 |
|---|---|
| `github-scout-plan` | 读你的项目，把目标写成想要的结果，定阶段，写中英文的检索方向 |
| `github-scout-search` | 每个方向多种搜法：名字、两两组合、实现方式、话题、SKILL.md、skills.sh、MCP 目录、npm、新冒出来的仓库 |
| `github-scout-triage` | 给每个仓库登记、打标，定怎么读（skill、命令行工具、清单读法不同） |
| `github-scout-dig` | 读代码，带着文件路径把思路挖出来 |
| `github-scout-brief` | 和你的代码对照，写答案和给开发 agent 的简报 |

## 核心理念

- **目标决定能找到什么。**「找个视频工具」和「让我们的片子剪得像剪辑师」，找到的项目完全不同。你做到哪一步决定借什么：刚开始借思路，做到能用了借参数和边角处理。
- **思路比代码值钱。** agent 写代码很快，可它没想到的做法永远写不出来。每张卡先写思路、在哪个文件、为什么不容易想到。
- **交简报，不交清单。** 二十个仓库配星数，活全留给了你。
- **新的、常更新的，比星多的老项目值钱。** 3 个月没更新大幅降权，半年放一边，一年直接丢掉。游戏外挂、破解一类的引流仓库和刷出来的安装量，一律排除。
- **中英文都搜。** 实测选中的仓库一半是中文项目，它们用中文介绍自己。
- **看过的不再看第二遍。** 每个结论和理由都记进登记库，下次搜从这里开始；`updates` 只告诉你依赖的那几个文件变了什么。

## 登记库

一个装着 Markdown 和 JSON 的文件夹，最好放进 git：

```
projects/<项目>/questions/<问题>.md      目标、阶段、检索方向、答案
projects/<项目>/briefs/<问题>.md         给开发 agent 的简报
repos/<owner>__<repo>.md                 每个细看过的仓库一张卡，思路在最前
ledger.jsonl                             每个结论，只追加
scans/<项目>/<问题>/<时间>.json          每次搜了什么、找到什么
```

`github-scout site` 生成一个网页来浏览。格式见 [`store-format.md`](skills/github-scout/references/store-format.md)。

## 成本和局限

- 搜索花的是 API 调用，不是 token。一次完整搜索大约 5 分钟，在 GitHub 免费额度内。agent 读的表格约 2,000 token，看一个仓库约 1,300。
- 它看得到公开的 GitHub、npm、skills.sh、MCP 目录和你加进来的链接。GitLab、Codeberg 和闭源方案要靠搜索阶段里写的网页搜索。
- 搜不到，只说明在它查过的来源里没有，它会列出查过哪些。

## 同类项目

很多「先搜再造」的 skill 只管一次搜索、一次决定，比如 ECC 的 `search-first`（skills.sh 上装得最多的一个）、`reuse-before-build`、`oss-scout`。github-scout 补上这个决定的前后：
- 先读你的项目；
- 按阶段提问；
- 记住每个结论的登记库；
- 跟踪你依赖的仓库；
- 一份开发 agent 拿来就能做的简报。

## 参与

欢迎提 issue 和 PR，见 [CONTRIBUTING.md](CONTRIBUTING.md) 和 [AGENTS.md](AGENTS.md)。测试离线跑：`python -m unittest discover -s tests`。

## 许可证

MIT。
