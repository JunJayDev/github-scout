[English](./README.md) · **中文**

# github-scout

面向编码 Agent 的 GitHub 调研工具：在 Agent 从零开写之前，找到值得先试的成熟开源项目。提供 Claude Code 和 Codex 用的 skill 与命令行工具。

[![CI](https://github.com/JunJayDev/github-scout/actions/workflows/ci.yml/badge.svg)](https://github.com/JunJayDev/github-scout/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 工作方式

收到目标后，`github-scout` 会先读取你的当前项目，了解现有代码和不足之处。随后将目标转化为具体的结果描述，明确达标标准，确定项目所处阶段，并规划中英文检索方向，然后暂停等待你确认。

确认后，工具会使用中英文在 GitHub 和各大包目录中执行检索，保留相关且满 50 星的仓库。对 README、示例、截图或演示只做轻量检查，确认能力描述与需求有无明显不符。最终重点推荐的两三个项目，各做一次站外独立检索，查真实使用、评价、推荐、具体产出和问题；记录来源，没找到就明确写「未找到独立使用反馈」，不因此直接淘汰。某个检索方向满足条件的仓库不到 5 个时，该方向的门槛降到 20 星，仍不足再降到 10 星。整个流程以一份给编码 Agent 的报告结束：现有方案、最值得先试的两三个候选及各自的试法、大概还需自研的部分，以及检索覆盖范围。

`github-scout` 不运行候选项目的代码，也不修改你的项目。你提出要求后，由编码 Agent 接手报告：在隔离环境中试跑这两三个候选，选定一个整体跟进，其余仓库只用来补它的缺口且每处写明理由，再按项目规范落地。每次落地都会在本地登记库中记录文件与提交来源，方便后续跟踪上游更新。

## 快速开始

### 安装

为你的 Agent 全局安装 Skill：

```bash
npx skills add JunJayDev/github-scout -g
```

或者直接对你的 Agent 说：「帮我安装这个仓库里的 skill：https://github.com/JunJayDev/github-scout」。

在 Claude Code 中，也可以通过插件市场安装：

```text
/plugin marketplace add JunJayDev/github-scout
/plugin install github-scout@github-scout
```

命令行工具需要 Python 3.9+ 以及已登录的 `gh` CLI（或配置 `GITHUB_TOKEN`），无任何第三方 Python 依赖。首次提问时会自动在 `~/.github-scout` 创建本地登记库。

### 使用

在项目仓库目录下启动 Agent，直接描述你想要的结果：

> 用 github-scout：让我们 agent 渲染的产品宣传片，剪辑和动效像专业剪辑师做的。

1. **确认方案。** Agent 先读取项目代码，提出达标标准与中英文检索方向，并停下来等你确认。
2. **生成报告。** 确认后，Agent 执行检索，保留相关且星数达标的仓库，对重点推荐的两三个项目检索独立反馈，再写出报告：候选列表、最值得先试的两三个及各自的试法、检索覆盖范围。你的项目不会被改动。
3. **试跑、选定与落地。** 准备接入时，让编码 Agent 按报告继续。它在项目外试跑这两三个候选（每个几分钟），记录每次试跑，选定一个整体跟进；然后按每个上游仓库一次提交的方式修改代码，并运行 `github-scout adopt` 记录本地文件对应的上游文件及双端 commit。后续随时运行 `github-scout updates`，即可查看上游是否修改了你所引用的文件。

### 动手之前先查一下（交给子 Agent）

Agent 准备自己写一个工具、skill 或组件，或者要在几个工具之间选一个时，把查询交给一个子 Agent，自己继续做不依赖结论的部分。子 Agent 先列出自己已经知道的方案，再到网页和各个登记处（skills.sh、MCP registry、npm、PyPI、Hugging Face）查别人在用、在推荐什么，用 `github-scout quick` 扫一遍 GitHub 上的新仓库，核对少数几个对得上的，查它们的独立反馈，最后用十五行左右给出结论：直接用、改着用、借一个思路，或者没有合适的。整件事五到十五分钟，不占主会话。

```bash
github-scout quick "split unpunctuated speech transcripts into sentences, offline" \
  -e "transcript|asr|speech to text|语音转写" -m "sentence segmentation|punctuation restoration|断句|标点恢复" \
  -p "add punctuation to whisper output" -p "语音识别结果自动加标点" --form library
```

为什么不只搜 GitHub：它按字面匹配，不按意思。在大约二十次只跑这一步的真实查询里，Agent 从没采用过一个它本来不知道的仓库；好答案来自模型自己的知识、网页和其他登记处。交给子 Agent 的说明和步骤见 [`skills/github-scout/references/lookup.md`](skills/github-scout/references/lookup.md)。答案会影响整个项目时，走完整流程。

### 免安装模式（网页端对话）

在 ChatGPT 或 Claude 网页版中，上传 [`cloud/github-scout.md`](cloud/github-scout.md) 并写明你的目标（建议同时附上项目压缩包）。它仅靠网页搜索即可运行，除非你要求，否则中途不会停顿，最终输出一份完整的 Markdown 报告。

回到本地后，可以运行以下命令将报告导入登记库：

```bash
github-scout import report.md --q <project>/<question>
```

`import` 会通过 GitHub API 核验报告中的每一个链接，并保存候选仓库、笔记与结论。

## 六个阶段

每个阶段都是独立的 Skill，可单独调用。`github-scout` 按顺序运行前四个阶段，以报告结束，绝不改动你的项目；第五、六阶段由编码 Agent 在你提出要求后于项目仓库内执行。

| 阶段 | Skill | 职责 |
|---|---|---|
| 1. 规划 | `github-scout-plan` | 读取当前项目，将目标重写为预期结果，明确达标标准，设定项目阶段（`idea`、`prototype`、`working`、`polishing`），编写中英文检索方向。 |
| 2. 检索 | `github-scout-search` | 按每个方向从项目名、词对、实现机制、GitHub 话题、`SKILL.md`、skills.sh、MCP 目录、npm 及近期飙升仓库多路检索；剔除引流仓库、刷量安装与未满 50 星的仓库。 |
| 3. 筛选 | `github-scout-triage` | 轻量检查项目自述，保留相关且星数达标的候选仓库，标记类型（`skill`、`cli`、`mcp`、`library`、`app`、`list`），并写明各自的试法。 |
| 4. 报告 | `github-scout-brief` | 对重点推荐的两三个项目检索独立反馈，对照现有代码写出报告：现有方案、候选表、最值得先试的两三个及试法、不推荐的项目、检索覆盖范围。 |
| 5. 试跑 | `github-scout-dig` | 由编码 Agent 执行。在临时目录或容器中试跑这两三个候选，走不通立即止损；选定一个整体跟进，并写明缺口由何处补齐。 |
| 6. 落地 | `github-scout-adopt` | 由编码 Agent 执行。将选定的仓库整体引入（`depend`、`skill`、`tool`），按项目规范补齐缺口（`port`、`vendor`、`data`），并用 `github-scout adopt` 记录来源。 |

## CLI 命令一览

用法：`github-scout [--version] [--store DIR] <command> ...`

**规划与检索**
- `init` : 创建登记库目录。
- `new-project` : 添加项目档案。
- `find` : 检索已有的问题、仓库卡片与结论账本，确认此前是否调研过同类问题。
- `ask` : 创建新问题，记录目标、项目阶段与检索词表。
- `scan` : 执行检索并输出合并排序后的候选列表（`--plan` 预览查询语句；`--add` 补充外部链接；`--expand` 把 awesome 清单里链接的仓库加进来）。

**筛选、试跑与落地**
- `pick` : 为候选表格中的行或 `owner/repo` 记录筛选结论（低于星数下限需传 `--low-stars "<原因>"`）。
- `look` : 查看仓库基本信息、活跃度、类型、目录树，以及站点可访问性、下载量和 README 展示链接；不自动评级（`--source` 会下载源码并生成代码结构映射）。
- `note` : 在仓库卡片上记录结论（`use`、`adapt`、`learn`、`later`、`skip`），以及 `--results`（项目展示或独立反馈的可选链接）、`--trial` 和 `--watch` 监控路径。
- `brief` : 将已解答的问题生成供编码 Agent 使用的报告（不改动项目）。
- `adopt` : 登记已接入项目的开源仓库（接入方式、本地路径、上游路径及双端 commit）。

**登记库与日常维护**
- `import` : 导入网页端对话或同事生成的 Markdown 报告，并逐一核验 GitHub 链接。
- `show` : 查看问题的检索覆盖度与最终方案，或查看单个仓库卡片的历史记录。
- `updates` : 检查上游仓库是否有新提交修改了卡片所监控或已落地的那些文件。
- `site` : 生成用于浏览登记库的静态网页（`site/index.html`）。
- `check` : 校验登记库完整性并重新生成 `INDEX.md`。

星数门槛默认为 `50`（可通过环境变量 `GITHUB_SCOUT_MIN_STARS` 修改）；某个检索方向达标仓库不到 5 个时，门槛降到 20 星，再降到 10 星。登记库路径按以下优先级解析：`--store DIR`、`GITHUB_SCOUT_STORE`、配置文件、最近一层包含 `github-scout.json` 的父目录，最后默认为 `~/.github-scout`。

## 设计原则

- **目标与阶段决定检索策略。** 搜「视频工具」和搜「把产品宣传片剪出专业剪辑师的节奏」会命中完全不同的仓库。检索前先明确达标标准（两三个参考成品或可执行的检查项）并设定当前项目阶段（`idea`、`prototype`、`working`、`polishing`），以此决定是借鉴整套架构，还是只取具体参数与边界处理。
- **按实体与实现机制做中英文双语检索。** 优秀项目通常用「操作什么对象」和「采用什么技术机制」来描述自己，而不是堆砌宽泛的需求套话。每个方向都使用中英文社区各自的常用词检索；在实际使用中，最终入选的仓库有一半是中文项目。
- **自述轻查，重点推荐前独立检索。** README、示例、截图或演示用于确认能力与需求有无明显不符，不要求逐项复现。页面能打开只代表可访问，下载量也不等于产出质量。只对重点推荐的两三个项目，各做一次中英文站外检索，打开相关来源，查真实使用、第三方推荐、具体产出和负面反馈。作者宣传、同一篇介绍的转载、单纯目录收录不算独立使用。记录简短结论和来源；查不到写「未找到独立使用反馈」，工具不可用写「未核查」，两者都不直接导致淘汰。实际效果留给后续试跑。
- **星数按方向放宽。** 参考项目需满 50 星。小众方向很少有 5 个这种体量的项目，因此某个方向（一组检索词）不足 5 个时放宽到 20 星，再放宽到 10 星，不再更低。扫描表头和报告都会写明哪些方向放宽过、原因是什么。
- **报告止于试跑之前。** `github-scout` 负责检索、筛选和报告，不运行候选项目的代码，也不替你选定方案。由编码 Agent 在项目外试跑这两三个候选，每个几分钟，跑不通立即放弃。
- **单一主干加定点补缺。** 从十几个互不相干的仓库各摘一点思路，拼不出可用的系统。编码 Agent 试跑后只选定一个仓库整体跟进（最多附一个备选），其余仓库仅用于填补明确列出的缺口，每处写明理由。
- **交付报告，而非链接清单。** 罗列二十个仓库链接和星数只是把工作转交给你。报告会写明每个候选对目标有什么用、与你现有文件的关系，以及最值得先试的两三个该怎么试。
- **检索阶段不过滤开源许可证。** 调研的目标是寻找技术参考与实现范本。检索、排序和报告均不检查许可证，因为一旦前置过滤许可证，Agent 往往还没看过项目做出了什么，就先把重要参考排除了。
- **近期活跃度与增速用于发现，不直接决定选用。** 3 个月无提交大幅降权，6 个月搁置，12 个月直接排除。工具会专门检索近期快速飙升的新仓库以防漏掉新作，但最终选型只看成品质量、星数、试跑表现与契合度。游戏外挂、破解工具等引流仓库以及刷出来的安装量一律剔除。
- **结论持久化与文件级溯源。** 每个看过的仓库都在登记库中留下结论与理由，后续检索不再重复审阅。每次代码落地都会记录本地文件、上游文件及双端 commit，上游一旦修复了你所借鉴的代码，运行 `github-scout updates` 即可感知。

## 登记库结构

登记库是一个纯文本的 Markdown 与 JSON 文件夹，适合直接纳入 Git 版本控制：

```text
projects/<项目>/questions/<问题>.md      目标、所处阶段、检索方向、最终方案
projects/<项目>/briefs/<问题>.md         给编码 Agent 的报告
repos/<owner>__<repo>.md                 每个细看仓库一张卡片：核心思路、可验证效果与试跑记录、落地位置
ledger.jsonl                             所有结论账本，仅追加写入
scans/<项目>/<问题>/<时间戳>.json        每次检索执行的查询与命中结果
```

运行 `github-scout site` 可生成单页静态站点（`site/index.html`）以浏览登记库。文件格式规范见 [`store-format.md`](skills/github-scout/references/store-format.md)。

## 成本与局限

- **API 调用与 Token 开销：** 检索消耗的是 GitHub API 调用次数，而非大模型 Token。一次完整检索耗时 5 到 15 分钟，在 GitHub 免费限额之内。Agent 读取的排序汇总表约 2,000 Token，查看单个仓库详情（`look`）约 1,300 Token。
- **检索覆盖范围：** 自动扫描覆盖公开的 GitHub、npm、skills.sh、官方 MCP 目录以及通过 `scan --add` 手动添加的链接。GitLab、Codeberg 与闭源商业方案需配合 `github-scout-search` 中描述的网页搜索完成。
- **完备性边界：** 检索未命中仅代表在已查验的数据源和查询词下没有结果，具体查验范围会完整记录在扫描日志中。

## 与同类项目对比

许多「先搜再写」类 Skill（如 skills.sh 上安装量最高的 ECC `search-first`，以及 `reuse-before-build`、`oss-scout`）主要负责引导单次搜索并给出「造还是用」的建议。`github-scout` 补的是这个决定之前和之后的部分：

- 检索前先读取本地项目，摸清现有实现与差距；
- 按项目阶段提问，在搜索前先明确可核验的达标标准；
- 保留星数和维护状态筛选，轻查项目自述，对重点推荐独立检索反馈，再由编码 Agent 试跑；
- 用持久化登记库记住每一次筛选结论，看过的仓库绝不看第二遍；
- 结合本地代码结构写出报告，告诉编码 Agent 先试什么、怎么试；
- 通过 `github-scout adopt` 记录文件级与提交级来源，并由 `github-scout updates` 持续跟踪上游对应文件的变更。

## 同系列

属于「agent 媒介素养」系列。[x-scout](https://github.com/JunJayDev/x-scout) 用同样的思路处理 X：不登录读帖，搜索结果逐条回 X 核对，把价值和传播分开判断。

## 参与贡献

欢迎提交 Issue 和 Pull Request，详见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [AGENTS.md](AGENTS.md)。

测试使用内置的模拟 GitHub API 离线运行，无需联网：

```bash
python -m unittest discover -s tests
```

## 许可证

[MIT](LICENSE)。
