[English](./README.md) · **中文**

# github-scout

面向编码 Agent 的开源调研 Skill 与命令行工具：在写代码前检索 GitHub 上的现有方案，实测头部候选项目，并为编码 Agent 生成可直接落地的实现简报。

[![CI](https://github.com/JunJayDev/github-scout/actions/workflows/ci.yml/badge.svg)](https://github.com/JunJayDev/github-scout/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

## 工作方式

收到目标后，`github-scout` 会先读取你的当前项目，了解现有代码和不足之处。随后将目标转化为具体的结果描述，明确达标标准，确定项目所处阶段，并规划中英文检索方向，然后暂停等待你确认。

确认后，工具会使用中英文在 GitHub 和各大包目录中执行检索，筛掉未满 50 星或拿不出实际成品的仓库，并在隔离环境中试跑排名前两三的候选项目。接着，它会深入阅读最值得整体借鉴的主干仓库源码，找出可由其他仓库补齐的缺口，最终为编码 Agent 生成一份分步骤的落地简报。

调研过程不会修改你的项目代码。只有当你要求编码 Agent 采纳简报时，它才会按项目自己的规范改代码，并在本地登记库中记录文件与提交来源，方便后续跟踪上游更新。

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
2. **生成简报。** 确认后，Agent 执行检索，保留有实际成品且满 50 星的仓库，试跑最优的两三个候选，分析主干项目的源码结构，并在不改动你项目的前提下生成交接简报。
3. **落地与跟踪。** 准备接入时，让编码 Agent 按简报落地。它会按每个上游仓库一次提交的方式修改代码，并运行 `github-scout adopt` 记录本地文件对应的上游文件及双端 commit。后续随时运行 `github-scout updates`，即可查看上游是否修改了你所引用的文件。

### 免安装模式（网页端对话）

在 ChatGPT 或 Claude 网页版中，上传 [`cloud/github-scout.md`](cloud/github-scout.md) 并写明你的目标（建议同时附上项目压缩包）。它仅靠网页搜索即可运行，除非你要求，否则中途不会停顿，最终输出一份完整的 Markdown 报告。

回到本地后，可以运行以下命令将报告导入登记库：

```bash
github-scout import report.md --q <project>/<question>
```

`import` 会通过 GitHub API 核验报告中的每一个链接，并保存候选仓库、笔记与结论。

## 六个阶段

每个阶段都是独立的 Skill，可单独调用。`github-scout` 按顺序运行前五个阶段，绝不改动你的项目；第六阶段仅在你指示编码 Agent 落地时在项目仓库内执行。

| 阶段 | Skill | 职责 |
|---|---|---|
| 1. 规划 | `github-scout-plan` | 读取当前项目，将目标重写为预期结果，明确达标标准，设定项目阶段（`idea`、`prototype`、`working`、`polishing`），编写中英文检索方向。 |
| 2. 检索 | `github-scout-search` | 按每个方向从项目名、词对、实现机制、GitHub 话题、`SKILL.md`、skills.sh、MCP 目录、npm 及近期飙升仓库多路检索；剔除引流仓库、刷量安装与未满 50 星的仓库。 |
| 3. 筛选 | `github-scout-triage` | 只保留有实际成品可看且满 50 星的候选仓库，标记类型（`skill`、`cli`、`mcp`、`library`、`app`、`list`），并指定后续阅读与试跑方式。 |
| 4. 细读 | `github-scout-dig` | 在临时目录或容器中试跑最优的两三个候选项目，走不通立即止损；选定主干项目并深入阅读其源码。 |
| 5. 简报 | `github-scout-brief` | 对照你的现有代码写出最终方案（一个主干项目、缺口由何处补齐、以及「未采纳」附录），生成给编码 Agent 的交接简报。 |
| 6. 落地 | `github-scout-adopt` | 将主干项目整体引入（`depend`、`skill`、`tool`），按项目规范补齐缺口（`port`、`vendor`、`data`），并用 `github-scout adopt` 记录来源。 |

## CLI 命令一览

用法：`github-scout [--version] [--store DIR] <command> ...`

**规划与检索**
- `init` : 创建登记库目录。
- `new-project` : 添加项目档案。
- `find` : 检索已有的问题、仓库卡片与结论账本，确认此前是否调研过同类问题。
- `ask` : 创建新问题，记录目标、项目阶段与检索词表。
- `scan` : 执行检索并输出合并排序后的候选列表（`--plan` 预览查询语句；`--add` 补充外部链接；`--expand` 把 awesome 清单里链接的仓库加进来）。

**筛选、试跑与落地**
- `pick` : 为候选表格中的行或 `owner/repo` 记录筛选结论（未满 50 星需传 `--low-stars "<原因>"`）。
- `look` : 查看仓库基本信息、活跃度、类型、目录树及 README 中的成品链接（`--source` 会下载源码并生成代码结构映射）。
- `note` : 在仓库卡片上记录结论（`use`、`adapt`、`learn`、`later`、`skip`），以及 `--results`、`--trial` 和 `--watch` 监控路径。
- `brief` : 将已解答的问题生成供编码 Agent 使用的交接简报（不改动项目）。
- `adopt` : 登记已接入项目的开源仓库（接入方式、本地路径、上游路径及双端 commit）。

**登记库与日常维护**
- `import` : 导入网页端对话或同事生成的 Markdown 报告，并逐一核验 GitHub 链接。
- `show` : 查看问题的检索覆盖度与最终方案，或查看单个仓库卡片的历史记录。
- `updates` : 检查上游仓库是否有新提交修改了卡片所监控或已落地的那些文件。
- `site` : 生成用于浏览登记库的静态网页（`site/index.html`）。
- `check` : 校验登记库完整性并重新生成 `INDEX.md`。

星数门槛默认为 `50`（可通过环境变量 `GITHUB_SCOUT_MIN_STARS` 修改）。登记库路径按以下优先级解析：`--store DIR`、`GITHUB_SCOUT_STORE`、配置文件、最近一层包含 `github-scout.json` 的父目录，最后默认为 `~/.github-scout`。

## 设计原则

- **目标与阶段决定检索策略。** 搜「视频工具」和搜「把产品宣传片剪出专业剪辑师的节奏」会命中完全不同的仓库。检索前先明确达标标准（两三个参考成品或可执行的检查项）并设定当前项目阶段（`idea`、`prototype`、`working`、`polishing`），以此决定是借鉴整套架构，还是只取具体参数与边界处理。
- **按实体与实现机制做中英文双语检索。** 优秀项目通常用「操作什么对象」和「采用什么技术机制」来描述自己，而不是堆砌宽泛的需求套话。每个方向都使用中英文社区各自的常用词检索；在实际使用中，最终入选的仓库有一半是中文项目。
- **先看实际成品，再看代码。** 候选仓库必须能展示它做出的成果（样片、画廊、示例输出、基准测试或实际使用方），且至少达到 50 星，才具备参考资格；特殊破例必须写明理由。
- **先隔离试跑，再细读源码。** 排名前两三的候选项目，会先在项目外的临时目录或容器里跑通最小示例或真实短任务，再深入读代码。跑不通的项目在几分钟内直接放弃。
- **单一主干加定点补缺。** 从十几个互不相干的仓库各摘一点思路，拼不出可用的系统。每份简报只选定一个经过验证的主干仓库整体跟进（最多附一个备选），其余仓库仅用于填补明确列出的具体缺口。
- **交付可执行简报，而非链接清单。** 罗列二十个仓库链接和星数只是把工作转交给你。工具最终交付的是结合你现有代码结构的具体改造方案。
- **检索阶段不过滤开源许可证。** 调研的目标是寻找技术参考与实现范本。检索、排序和报告均不检查许可证，因为一旦前置过滤许可证，Agent 往往还没看过项目做出了什么，就先把重要参考排除了。
- **近期活跃度与增速用于发现，不直接决定选用。** 3 个月无提交大幅降权，6 个月搁置，12 个月直接排除。工具会专门检索近期快速飙升的新仓库以防漏掉新作，但最终选型只看成品质量、星数、试跑表现与契合度。游戏外挂、破解工具等引流仓库以及刷出来的安装量一律剔除。
- **结论持久化与文件级溯源。** 每个看过的仓库都在登记库中留下结论与理由，后续检索不再重复审阅。每次代码落地都会记录本地文件、上游文件及双端 commit，上游一旦修复了你所借鉴的代码，运行 `github-scout updates` 即可感知。

## 登记库结构

登记库是一个纯文本的 Markdown 与 JSON 文件夹，适合直接纳入 Git 版本控制：

```text
projects/<项目>/questions/<问题>.md      目标、所处阶段、检索方向、最终方案
projects/<项目>/briefs/<问题>.md         给编码 Agent 的交接简报
repos/<owner>__<repo>.md                 每个细看仓库一张卡片：核心思路、成品与试跑记录、落地位置
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
- 设立严格的质量门槛：有成品可看、50 星以上、读源码前先在隔离环境试跑；
- 用持久化登记库记住每一次筛选结论，看过的仓库绝不看第二遍；
- 结合本地代码结构写出编码 Agent 拿来就能执行的交接简报；
- 通过 `github-scout adopt` 记录文件级与提交级来源，并由 `github-scout updates` 持续跟踪上游对应文件的变更。

## 参与贡献

欢迎提交 Issue 和 Pull Request，详见 [CONTRIBUTING.md](CONTRIBUTING.md) 与 [AGENTS.md](AGENTS.md)。

测试使用内置的模拟 GitHub API 离线运行，无需联网：

```bash
python -m unittest discover -s tests
```

## 许可证

[MIT](LICENSE)。
