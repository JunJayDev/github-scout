"""Files that cross between agents.

`import`: a report written elsewhere (a cloud chat, a teammate, another agent) comes back into the
registry. Only GitHub links are trusted; every one is checked against GitHub, and the ones that
do not exist are listed, since a chat model may invent them. Table columns it recognises (kind,
verdict, reason) ride along as notes.

`brief`: an answered question becomes a hand-off for the agent that will change the code. It
copies the answer's own sections and adds the facts from the cards (take, reviewed commit),
so the coding agent gets what to change, why, and from where, without reading the registry.
"""

from __future__ import annotations

import re
from pathlib import Path

from .discover import slugs_in_text
from .store import Store, StoreError, as_list, today

# Column names a report may use, in English and Chinese.
COLUMNS = {
    "repo": ("repo", "repository", "link", "url", "project", "仓库", "链接", "项目", "地址"),
    "kind": ("kind", "type", "form", "category", "类型", "形态", "是什么", "种类"),
    "take": ("take", "verdict", "decision", "action", "结论", "取舍", "处理", "建议"),
    "reason": ("why", "reason", "idea", "what to take", "notes", "理由", "为什么", "能借什么", "思路", "说明", "备注"),
    "direction": ("direction", "lens", "方向"),
}
# A search log (one row per search) is told apart by its query column; its rows are searches, not repos.
LOG_COLUMNS = {
    "query": ("query", "search", "检索词", "搜索词", "查询", "关键词"),
    "lens": ("lens", "method", "方法", "方式", "途径"),
    "direction": ("direction", "方向"),
    "lang": ("lang", "language", "语言"),
    "looked": ("looked", "results", "看了", "结果"),
    "kept": ("kept", "保留", "留下"),
}
TAKE_WORDS = {
    "shortlist": ("shortlist", "short", "入选", "值得看", "深入看"),
    "use": ("use", "直接用", "用"), "adapt": ("adapt", "改了用", "改用", "改造"), "learn": ("learn", "学思路", "学", "借鉴"),
    "later": ("later", "以后", "以后再说", "待定"), "skip": ("skip", "不要", "跳过", "不用"),
}
VERDICT_OF_TAKE = {"shortlist": "short", "use": "short", "adapt": "short", "learn": "short", "later": "later", "skip": "skip"}


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _column(header: list[str], key: str, table: dict = COLUMNS) -> int | None:
    names = table[key]
    for i, h in enumerate(header):
        low = re.sub(r"[*_`]", "", h).strip().lower()
        if any(low == n or low.startswith(n) for n in names):
            return i
    return None


def _take(text: str) -> str | None:
    low = re.sub(r"[*_`]", "", text).strip().lower()
    for take, words in TAKE_WORDS.items():
        if any(low == w or low.startswith(w + " ") or low.startswith(w + "，") or low.startswith(w + ",") for w in words):
            return take
    return None


def report_goal(text: str) -> tuple[str | None, str | None]:
    """The goal (the report's title) and the stage written in its header, when present."""
    goal = None
    m = (re.search(r"^#{1,3}\s+(?:GitHub scout report|github-scout report|GitHub scout 报告|github-scout 报告)\s*[:：]\s*(.+)$", text, re.M | re.I)
         or re.search(r"^#\s+(.+)$", text, re.M))
    if m:
        goal = m.group(1).strip() or None
    st = re.search(r"\b(idea|prototype|working|polishing)\b", text[:2000])
    return goal, st.group(1) if st else None


def _tables(text: str):
    """(in the Candidates section?, header cells, row cells) for every Markdown table."""
    lines = text.splitlines()
    candidates = False
    i = 0
    while i < len(lines):
        h = re.match(r"^(#{1,2})\s+(.*)$", lines[i])
        if h:
            candidates = bool(re.search(r"candidates|候选", h.group(2), re.I))
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            header, body = _cells(lines[i]), []
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                body.append((_cells(lines[i]), lines[i]))
                i += 1
            yield candidates, header, body
            continue
        i += 1


def _cell(cells: list[str], j: int | None) -> str:
    return cells[j] if j is not None and j < len(cells) else ""


def parse_report(text: str) -> tuple[list[str], dict[str, dict]]:
    """Every GitHub repo linked in the text, in order, and per repo the fields found in table rows.

    A verdict counts only outside the Candidates section: a candidate list is not triaged yet, and
    a chat model fills such a column with one word for every row (84 rows of "learn" in one test).
    Search logs are skipped here; `parse_search_log` reads them.
    """
    rows: dict[str, dict] = {}
    for candidates, header, body in _tables(text):
        if _column(header, "query", LOG_COLUMNS) is not None:
            continue
        cols = {k: _column(header, k) for k in COLUMNS}
        for cells, line in body:
            found = slugs_in_text(_cell(cells, cols["repo"]) if cols["repo"] is not None else line)
            if not found:
                continue
            entry = rows.setdefault(found[0].lower(), {"repo": found[0]})
            for key in ("kind", "reason", "direction"):
                v = _cell(cells, cols[key])
                if v and key not in entry:
                    entry[key] = v[:300]
            take = _take(_cell(cells, cols["take"])) if cols["take"] is not None else None
            if not candidates and take:
                entry["take"] = take
    return slugs_in_text(text), rows


DIRECTION_COLUMNS = {
    "entities": ("entities", "entity", "实体", "对象"),
    "mechanisms": ("mechanisms", "mechanism", "机制", "做法"),
    "forms": ("forms", "form", "形态"),
}
FORM_WORDS = ("skill", "skills", "skill-pack", "plugin", "agent", "rules", "mcp", "cli", "library", "framework",
              "app", "extension", "service", "template", "model", "prompt", "list")


def parse_directions(text: str, cap: int = 24) -> dict[str, list[str]]:
    """Search words from the report's directions table, one group per term, for a local `scan`.

    Chat models write "remotion / 宣传片, 产品视频" or "Claude Code / Codex / 宣传片": synonyms
    cannot be paired reliably, so every term becomes its own group and the scan's language split
    sorts them. Capped so a scan stays within its budget."""
    out: dict[str, list[str]] = {"entities": [], "mechanisms": [], "forms": []}
    for _, header, body in _tables(text):
        cols = {k: _column(header, k, DIRECTION_COLUMNS) for k in DIRECTION_COLUMNS}
        if cols["entities"] is None and cols["mechanisms"] is None:
            continue
        for cells, _ in body:
            for key in out:
                for term in re.split(r"\s*[/,，、;；|]\s*", re.sub(r"[`*]", "", _cell(cells, cols[key]))):
                    term = term.strip().strip("()（）")
                    if key == "forms":
                        term = term.lower()
                        if term not in FORM_WORDS:
                            continue
                    if term and len(term) <= 40 and term.lower() not in {x.lower() for x in out[key]}:
                        out[key].append(term)
    return {k: v[:cap] for k, v in out.items()}


def words_from_log(searches: list[dict], cap: int = 24) -> list[str]:
    """Search phrases from a log, for a report that has no directions table: the words it used."""
    out: list[str] = []
    for s in searches:
        q = re.sub(r"\b(site|pushed|created|stars|topic|in|language):\S*", " ", s["query"])
        q = re.sub(r"https?://\S+|[\"'`]", " ", q)
        q = re.sub(r"\s+", " ", q).strip()
        if q and len(q.split()) <= 4 and q.lower() not in {x.lower() for x in out}:
            out.append(q)
    return out[:cap]


def parse_search_log(text: str) -> list[dict]:
    """The searches a report says it ran: lens, direction, language, query, results looked at, repos kept."""
    out = []
    for _, header, body in _tables(text):
        cols = {k: _column(header, k, LOG_COLUMNS) for k in LOG_COLUMNS}
        if cols["query"] is None:
            continue
        for cells, _ in body:
            query = re.sub(r"`", "", _cell(cells, cols["query"])).strip()
            if not query:
                continue
            looked = re.search(r"\d+", _cell(cells, cols["looked"]))
            out.append({"lens": _cell(cells, cols["lens"]), "direction": _cell(cells, cols["direction"]),
                        "lang": _cell(cells, cols["lang"]), "query": query[:200],
                        "looked": int(looked.group()) if looked else None,
                        "kept": re.findall(r"[\w.-]+/[\w.-]+", re.sub(r"https?://github\.com/", "", _cell(cells, cols["kept"])))})
    return out


# ---------------------------------------------------------------------------


def _section(body: str, titles: tuple[str, ...]) -> str:
    """The text under the first heading whose title starts with one of `titles`, up to the next heading
    of the same or a higher level."""
    lines = body.splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{2,4})\s+(.*)$", ln)
        if m and any(m.group(2).strip().lower().startswith(t.lower()) for t in titles):
            level = len(m.group(1))
            out = []
            for nxt in lines[i + 1:]:
                h = re.match(r"^(#{1,4})\s", nxt)
                if h and len(h.group(1)) <= level:
                    break
                out.append(nxt)
            text = "\n".join(out).strip()
            return "" if _placeholder(text) else text
    return ""


def _placeholder(text: str) -> bool:
    """Template hints are one parenthesised paragraph: "(Who to take what from ...)"."""
    t = text.strip()
    return not t or (t[0] in "(（" and t[-1] in ")）" and "\n\n" not in t)


SECTIONS = {
    "where": ("Where we are", "我们现在"),
    "summary": ("In one paragraph", "一段话结论"),
    "ideas": ("Ideas worth taking", "值得借的思路"),
    "practice": ("Practices and components", "做法和组件"),
    "compare": ("Against what we have", "和我们已有的对照"),
    "next": ("Next steps", "我们接下来改什么"),
}

T = {
    "en": {
        "title": "Brief for the coding agent: {ask}", "from": "From github-scout question `{ref}` ({path}), {date}.",
        "rule": "This brief only advises. Make the changes in the project yourself, check each one, and keep "
                "what the user decided before.",
        "goal": "## Goal and where we stand", "code": "Project code: {code}", "nocode": "No local project was given; "
                "map each step onto the code it would change before starting.",
        "steps": "## What to change, in order", "why": "## Why: the ideas behind it",
        "practice": "## Practices and components", "compare": "## Against what we have",
        "repos": "## Sources", "head": "| repo | take | reviewed at | what we take |",
        "empty": "(the answer has no such section yet)", "noanswer": "{ref} has no answer yet: write its answer section first",
    },
    "zh": {
        "title": "给开发 agent 的简报：{ask}", "from": "来自 github-scout 问题 `{ref}`（{path}），{date}。",
        "rule": "这份简报只给建议，改动由你在项目里做，每一步做完要验证，用户以前定过的规矩照旧。",
        "goal": "## 目标和现状", "code": "项目代码：{code}", "nocode": "没有给本地项目；动手前先把每一步对应到要改的代码。",
        "steps": "## 要改什么（按顺序）", "why": "## 依据：值得借的思路",
        "practice": "## 做法和组件", "compare": "## 和我们已有的对照",
        "repos": "## 参考仓库", "head": "| 仓库 | 取舍 | 审查时的版本 | 我们拿什么 |",
        "empty": "（答案里还没有这一节）", "noanswer": "{ref} 还没有答案：先写问题文件里的答案",
    },
}


def brief(store: Store, ref: str, out: Path | None = None) -> Path:
    doc = store.question(ref)
    q = doc.data
    t = T[store.lang]
    parts = {k: _section(doc.body, v) for k, v in SECTIONS.items()}
    if not (parts["summary"] or parts["ideas"] or parts["next"]):
        raise StoreError(t["noanswer"].format(ref=ref))
    project = store.project(q["project"])
    code = (project.data.get("code") if project else "") or ""
    lines = [f"# {t['title'].format(ask=q.get('ask', ''))}", "",
             t["from"].format(ref=f"{q['project']}/{q['id']}", path=doc.path, date=today()), "", t["rule"], "",
             t["goal"], "", t["code"].format(code=code) if code else t["nocode"], "", parts["where"] or t["empty"], ""]
    if parts["summary"]:
        lines += [parts["summary"], ""]
    lines += [t["steps"], "", parts["next"] or t["empty"], "", t["why"], "", parts["ideas"] or t["empty"], ""]
    if parts["practice"]:
        lines += [t["practice"], "", parts["practice"], ""]
    if parts["compare"]:
        lines += [t["compare"], "", parts["compare"], ""]
    picked = [str(x) for x in as_list(q.get("picked"))]
    if picked:
        lines += [t["repos"], "", t["head"], "|---|---|---|---|"]
        for slug in picked:
            card = store.card(slug)
            if not card:
                lines.append(f"| [{slug}](https://github.com/{slug}) | - | - | - |")
                continue
            d = card.data
            use = next((u for u in as_list(d.get("uses")) if isinstance(u, dict) and u.get("question") == q["id"]), {})
            note = str(use.get("note") or d.get("summary") or "").replace("|", "/").replace("\n", " ")[:220]
            lines.append(f"| [{card.id}](https://github.com/{card.id}) | {use.get('take', '-')} | "
                         f"{d.get('commit', '-')} | {note} |")
        lines.append("")
    path = out or store.root / "projects" / q["project"] / "briefs" / f"{q['id']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path


def read_source(src: str) -> str:
    p = Path(src).expanduser()
    if not p.is_file():
        raise StoreError(f"no such file: {src}")
    return p.read_text(encoding="utf-8", errors="replace")
