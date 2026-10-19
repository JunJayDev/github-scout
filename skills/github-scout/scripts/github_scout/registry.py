"""Questions, cards and projects: creating them, recording what we take, finding, indexing."""

from __future__ import annotations

import re
from pathlib import Path

from .store import (
    DEFAULT_LANGS, KINDS, MODES, PROJECT_ORDER, QUESTION_ORDER, STAGES, TAKES, Doc, Store, StoreError, adoptions, as_list,
    card_takes, min_stars, repo_ref, strongest, today, write_doc,
)

# What is worth borrowing depends on where our own work stands.
STAGE_HELP = {
    "en": {
        "idea": "nothing built yet: borrow how others frame the problem, their overall approach, the dead ends they hit",
        "prototype": "a first version exists: borrow key workflows, architecture and trade-offs",
        "working": "it works: borrow techniques, parameters, prompts, edge cases and how they evaluate",
        "polishing": "we are refining: borrow details, benchmarks and components we can drop in",
    },
    "zh": {
        "idea": "还没动手：借别人怎么理解这个问题、整体做法、走过的弯路",
        "prototype": "有了雏形：借关键流程、架构和取舍",
        "working": "已经能用：借技巧、参数、提示词、边角处理和评测方法",
        "polishing": "在打磨：借细节、对比基准和能直接搬的组件",
    },
}

T = {
    "en": {
        "question": """
# {ask}

## Where we are
Stage: {stage} ({stage_help})
- What we have: (paths in our code, docs, what already works)
- What is not good enough: (the reason we are asking)

## What good looks like
(2-3 finished results we want to match, as links, or checks anyone can run on an output. Every candidate is judged against these.)

## Answer
(The deliverable: one repo to follow as a whole, and what fills its gaps. A repo qualifies with results to look at, {stars}+ stars and a trial that ran.)

### In one paragraph
(Which repo to follow and why; what fills its gaps; what is left to build. Or "nothing qualifies, so we build it, because ...".)

### Backbone
(The repo we follow as a whole, and at most one alternate. Why it passed: its results (links), its stars, our trial.)

### Gaps to fill
| what the backbone lacks | filled from | why |
|---|---|---|

### Trial runs
(Each repo tried: what we ran, what came out, how long; where we stopped.)

### Against what we have
| we have | the backbone does | difference | take it? |
|---|---|---|---|

### Next steps in our project

### Not adopted
(Ideas from other repos we did not take, one line each, with the reason. The coding agent leaves them out.)

## Searched
(Scans are in scans/{project}/{id}/. Note the web and X pass here.
Vocabulary, in the frontmatter: every entity and mechanism group needs a term in each language of `langs`,
in the words those users actually write, not a translation: "xiaohongshu|小红书|xhs|红书",
"humanizer|去AI味|活人感|人味", "product video|宣传片|产品视频".)
""",
        "skill": """
# {id}

## The idea
(How it does the job, in a few lines. Where, by file.)

## Results and trial
(What it has made that we can look at: links under results:. Our trial: what we ran, what came out, how long.)

## Method quality
(Concrete steps or vague advice? What it costs to load?)

## What we take
(The whole of it as our backbone, or the gap in the backbone it fills, with file paths.)

## Safety
(Network calls, credential reads, self-update, broad permissions. "None found in <files>" is an answer.)

## Read first
""",
        "software": """
# {id}

## The idea
(The key design decision, and how it differs from what we would have built. Where, by file.)

## Results and trial
(What it has made that we can look at: links under results:. Our trial: what we ran, what came out, how long.)

## Quality
(New and moving? Who uses it? Do maintainers answer issues?)

## What we take
(The whole of it as our backbone, or the gap in the backbone it fills: how we run or adapt it, with file paths.)

## Risks
(Permissions, data it can reach, lock-in.)

## Read first
""",
        "other": """
# {id}

## The idea

## Results and trial

## What we take

## Read first
""",
    },
    "zh": {
        "question": """
# {ask}

## 我们现在
阶段：{stage}（{stage_help}）
- 已经有的：（我们的代码路径、文档、已经能用的部分）
- 不满意的：（为什么要问这个问题）

## 好的结果长什么样
（2–3 个想做到的成品（给链接），或者任何人都能拿产出去核对的标准。每个候选都拿这个比。）

## 答案
（交付物：整套照做的一个仓库，加上补它缺口的东西。有能看的结果、{stars} 星以上、试跑跑通的仓库才算数。）

### 一段话结论
（照哪个仓库做、为什么；缺口从哪补；还剩什么要自己做。或者「没有过关的，只能自己做，因为……」。）

### 主干
（整套照做的那个仓库，最多再加一个备选。为什么过关：它的结果（链接）、星数、我们的试跑。）

### 补什么
| 主干缺什么 | 从哪补 | 为什么 |
|---|---|---|

### 试跑记录
（每个试过的仓库：跑了什么、出来什么、花了多久；在哪一步停下。）

### 和我们已有的对照
| 我们已有 | 主干的做法 | 差在哪 | 拿不拿 |
|---|---|---|---|

### 我们接下来改什么

### 没采用
（别家的思路，一行一条，写清为什么没用。开发 agent 不把这些加进来。）

## 搜过哪些
（扫描记录在 scans/{project}/{id}/；网页和 X 那一轮写在这里。
词表写在开头的 frontmatter：每组实体和机制都要有 langs 里每种语言的词，写那种语言的用户真正在用的叫法，
不是翻译：「xiaohongshu|小红书|xhs|红书」「humanizer|去AI味|活人感|人味」「product video|宣传片|产品视频」。）
""",
        "skill": """
# {id}

## 思路
（它怎么把事做成，几行说清。写在哪个文件。）

## 结果和试跑
（它做出过什么、我们能看到的：链接写进 results:。我们的试跑：跑了什么、出来什么、花了多久。）

## 方法质量
（是具体步骤还是空泛建议？加载要多少 token？）

## 我们拿什么
（整套当主干，还是补主干的哪个缺口；写到文件。）

## 安全
（联网、读凭证、自动更新、要宽权限。没有就写「在哪些文件里没看到」。）

## 先读
""",
        "software": """
# {id}

## 思路
（关键的设计决定，和我们自己会怎么做有什么不同。写在哪个文件。）

## 结果和试跑
（它做出过什么、我们能看到的：链接写进 results:。我们的试跑：跑了什么、出来什么、花了多久。）

## 质量
（新不新、更新勤不勤、谁在用、维护者回不回 issue。）

## 我们拿什么
（整套当主干，还是补主干的哪个缺口：怎么直接用、怎么改了用，写到文件。）

## 风险
（权限、能碰到的数据、锁定。）

## 先读
""",
        "other": """
# {id}

## 思路

## 结果和试跑

## 我们拿什么

## 先读
""",
    },
}

# The card section a trial goes into; cards from before it get one after their first section.
TRIAL_TITLES = {"en": "Results and trial", "zh": "结果和试跑"}


def stage_help(store: Store, stage: str) -> str:
    return STAGE_HELP[store.lang].get(stage, "")


def first_sentence(text: str | None, limit: int = 160) -> str:
    """The first sentence of a note or idea, for a card whose repo has no description on GitHub."""
    t = " ".join(str(text or "").split())
    for stop in (". ", "。", "; ", "；"):
        if stop in t:
            t = t[:t.index(stop) + (1 if stop.strip() in ".。" else 0)]
            break
    return t[:limit].rstrip()


def new_card(store: Store, meta: dict, kind: str, form: str | None, uses: list[dict], watch: list[str], level: str,
             summary: str | None = None, idea: str | None = None, results: list[str] | None = None) -> Doc:
    slug = meta["repo"]
    path = store.card_path(slug)
    if path.exists():
        raise StoreError(f"{slug} already has a card: {path} (use `note` again to add or change a take)")
    if kind not in KINDS:
        raise StoreError(f"kind must be one of {', '.join(KINDS)}")
    data = {
        "id": slug, "repo": f"https://github.com/{slug}", "kind": kind, "form": form,
        # a repo without a description on GitHub would leave the card without one (check refuses that)
        "summary": summary or meta.get("desc") or first_sentence(idea) or f"{slug} (no description on GitHub)",
        "stars": meta.get("stars"), "created": meta.get("created") or None, "pushed": meta.get("pushed") or None,
        "branch": meta.get("branch"), "commit": meta.get("commit"), "reviewed": today(), "level": level,
        "results": list(dict.fromkeys(results or [])), "watch": watch, "uses": uses,
    }
    data = {k: v for k, v in data.items() if v is not None}
    doc = Doc(path, data, T[store.lang].get(kind, T[store.lang]["other"]).format(id=slug))
    store.save_card(doc)
    return doc


def set_use(store: Store, slug: str, use: dict, level: str | None = None) -> Doc:
    card = store.card(slug)
    if not card or card.error:
        raise StoreError(f"{slug}: no card")
    if use.get("take") not in TAKES:
        raise StoreError(f"take must be one of {', '.join(TAKES)}")
    uses = [u for u in as_list(card.data.get("uses")) if isinstance(u, dict)]
    for u in uses:
        if u.get("project") == use.get("project") and (u.get("question") or None) == (use.get("question") or None):
            u.update({k: v for k, v in use.items() if v})
            break
    else:
        uses.append({k: v for k, v in use.items() if v})
    card.data["uses"] = uses
    if level:
        card.data["level"] = level
    store.save_card(card)
    return card


def set_adoption(store: Store, slug: str, entry: dict, drop: bool = False) -> dict:
    """Record on the card that a repo came into one of our projects (stage 6). The same project, question and
    paths replace the earlier entry; with drop, that entry is marked dropped instead, so its history stays."""
    card = store.card(slug)
    if not card or card.error:
        raise StoreError(f"{slug}: no card")
    if not drop and entry.get("mode") not in MODES:
        raise StoreError(f"mode must be one of {', '.join(MODES)}")

    def key(a: dict) -> tuple:
        return a.get("project"), a.get("question") or None, sorted(map(str, as_list(a.get("into"))))

    items = [a for a in as_list(card.data.get("adopted")) if isinstance(a, dict)]
    i = next((n for n, a in enumerate(items) if key(a) == key(entry)), None)
    if drop:
        if i is None:
            same = [", ".join(map(str, as_list(a.get("into")))) for a in items if key(a)[:2] == key(entry)[:2]]
            raise StoreError(f"{card.id} has no adoption into {', '.join(entry['into'])} under "
                             f"{entry['project']}/{entry['question']}" + (f" (recorded: {'; '.join(same)})" if same else ""))
        items[i]["dropped"] = today()
        if entry.get("note"):
            items[i]["note"] = entry["note"]
    elif i is None:
        items.append({k: v for k, v in entry.items() if v})
        i = len(items) - 1
    else:
        items[i] = {k: v for k, v in entry.items() if v}
    card.data["adopted"] = items
    store.save_card(card)
    return items[i]


def adoption_text(a: dict, short: bool = False) -> str:
    """One adoption as a line: where, how, from what, at which commits; short leaves out the question and date."""
    into = ", ".join(map(str, as_list(a.get("into"))))
    src = ", ".join(map(str, as_list(a.get("from"))))
    return ("" if short else f"{a.get('project')}/{a.get('question') or '-'} ") + f"{a.get('mode')}: {into}" \
        + (f" <- {src}" if src else "") + (f" @{str(a['at'])[:12]}" if a.get("at") else "") \
        + (f", ours {a['ours']}" if a.get("ours") else "") + (f", {a['date']}" if a.get("date") and not short else "") \
        + (f" (dropped {a['dropped']})" if a.get("dropped") else "") + (f": {a['note']}" if a.get("note") else "")


def put_idea(store: Store, slug: str, idea: str, ref: str | None = None) -> None:
    """Write the idea into the card's first section: in place of the template hint while it is still there, otherwise
    at the end of that section, marked with the question it came from, so what other questions wrote stays first."""
    card = store.card(slug)
    lines = card.body.split("\n")
    first = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), None)
    if first is None:
        card.body = card.body.rstrip() + "\n\n" + idea + "\n"
    else:
        j = first + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j < len(lines) and lines[j].startswith(("(", "（")):
            lines[j] = idea
        elif j >= len(lines) or lines[j].startswith("## "):        # an empty first section: the idea goes first
            lines.insert(first + 1, idea)
        else:
            end = next((i for i in range(first + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
            while end > first + 1 and not lines[end - 1].strip():
                end -= 1
            lines[end:end] = ["", (f"**{ref}:** " if ref else "") + idea]
        card.body = "\n".join(lines)
    store.save_card(card)


def put_trial(store: Store, slug: str, text: str, ref: str) -> None:
    """Add a dated trial line to the card's Results and trial section, in place of its template hint. A card from
    before that section existed gets it after its first section."""
    card = store.card(slug)
    lines = card.body.split("\n")
    entry = f"- {today()}, {ref}: {' '.join(text.split())}"
    heads = [i for i, ln in enumerate(lines) if ln.startswith("## ")]
    at = next((i for i in heads if lines[i][3:].strip().lower() in {t.lower() for t in TRIAL_TITLES.values()}), None)
    if at is None:
        pos = heads[1] if len(heads) > 1 else len(lines)
        lines[pos:pos] = ([""] if pos and lines[pos - 1].strip() else []) + [f"## {TRIAL_TITLES[store.lang]}", "", entry, ""]
    else:
        end = next((i for i in heads if i > at), len(lines))
        kept = [ln for ln in lines[at + 1:end] if not re.fullmatch(r"\s*[(（].*[)）]\s*", ln)]   # the hint goes
        while kept and not kept[-1].strip():
            kept.pop()
        while kept and not kept[0].strip():
            kept.pop(0)
        lines[at + 1:end] = [""] + kept + ([""] if kept and not kept[-1].startswith("- ") else []) + [entry, ""]
    card.body = "\n".join(lines)
    store.save_card(card)


def add_results(store: Store, slug: str, links: list[str]) -> list[str]:
    """Add links to what a repo made to its card's results (no duplicates)."""
    card = store.card(slug)
    results = [str(x) for x in as_list(card.data.get("results"))]
    results += [x for x in links if x not in results]
    card.data["results"] = results
    store.save_card(card)
    return results


def add_watch(store: Store, slug: str, paths: list[str]) -> list[str]:
    """Add upstream paths we depend on to an existing card's watch list (no duplicates)."""
    card = store.card(slug)
    watch = [str(w) for w in as_list(card.data.get("watch"))]
    for p in paths:
        if p not in watch:
            watch.append(p)
    card.data["watch"] = watch
    store.save_card(card)
    return watch


def new_project(store: Store, pid: str, name: str, summary: str, code: str = "") -> Path:
    path = store.root / "projects" / pid / "project.md"
    if path.exists():
        raise StoreError(f"project {pid} exists: {path}")
    data = {"id": pid, "name": name, "summary": summary, "code": code, "stack": [], "constraints": [],
            "languages": ["en"]}
    body = ("\n# {name}\n\n(What this project is, who it serves, where its code is, and what we would never adopt: "
            "platforms, hosting, data handling. Agents read this before judging fit.)\n" if store.lang == "en" else
            "\n# {name}\n\n（这个项目是什么、给谁用、代码在哪；哪些东西绝不采用：平台、托管、数据处理。"
            "agent 判断合不合适之前先读这里。）\n").format(name=name)
    write_doc(path, data, body, PROJECT_ORDER)
    return path


def new_question(store: Store, ref: str, ask: str, stage: str, langs: list[str] | None = None) -> Path:
    project, qid = store.split_ref(ref)
    if not store.project(project):
        raise StoreError(f"no project {project} (github-scout new-project {project} --name ...)")
    if stage not in STAGES:
        raise StoreError(f"stage must be one of {', '.join(STAGES)}")
    path = store.question_path(project, qid)
    if path.exists():
        raise StoreError(f"question exists: {path}")
    data = {"id": qid, "project": project, "ask": ask, "stage": stage, "status": "open",
            "langs": list(langs or DEFAULT_LANGS), "entities": [], "mechanisms": [], "forms": [], "problems": [],
            "topics": [], "backbone": None, "alternate": None, "picked": [], "scanned": None}
    body = T[store.lang]["question"].format(ask=ask, stage=stage, stage_help=stage_help(store, stage),
                                            project=project, id=qid, stars=min_stars())
    write_doc(path, data, body, QUESTION_ORDER)
    return path


def card_line(c: Doc) -> str:
    d = c.data
    uses = [u for u in as_list(d.get("uses")) if isinstance(u, dict)]
    takes = [f"{u.get('project')}/{u.get('question') or '-'}:{u.get('take')}" for u in uses]
    facts = [", ".join(takes) or "no uses", f"{d['stars']} stars" if d.get("stars") is not None else "stars unknown",
             f"{len(as_list(d.get('results')))} results" if as_list(d.get("results")) else "no results",
             f"level {d.get('level') or '-'}", f"reviewed {d.get('reviewed')} @ {str(d.get('commit') or '')[:7]}"]
    return (f"{c.id} [{d.get('kind')}{'/' + str(d['form']) if d.get('form') else ''}] {strongest(card_takes(d)) or 'unrelated'}"
            f" — {str(d.get('summary') or '')[:100]} ({'; '.join(facts)})")


def _text(doc: Doc) -> str:
    vals = []
    for v in doc.data.values():
        if isinstance(v, list):
            vals += [" ".join(map(str, x.values())) if isinstance(x, dict) else str(x) for x in v]
        else:
            vals.append(str(v))
    return (" ".join(vals) + " " + doc.body).lower()


def find(store: Store, terms: list[str], limit: int = 20) -> dict:
    terms_l = [t.lower() for t in terms if t.strip()]
    if not terms_l:
        raise StoreError("give at least one word")

    def hits(text: str) -> int:
        return sum(1 for t in terms_l if t in text)

    cards = sorted(((hits(_text(c)), c) for c in store.cards() if not c.error), key=lambda x: (-x[0], x[1].id))
    questions = sorted(((hits(_text(q)), q) for q in store.questions() if not q.error), key=lambda x: -x[0])
    seen: dict[str, dict] = {}
    for e in store.ledger():
        if "repo" not in e:
            continue
        h = hits(" ".join(str(e.get(k, "")) for k in ("repo", "reason", "question", "project", "desc")).lower())
        if h:
            key = str(e["repo"]).lower()
            prev = seen.get(key)
            if not prev or (e.get("date") or "") >= (prev["entry"].get("date") or ""):
                seen[key] = {"hits": h, "entry": e}
    carded = {c.id.lower() for _, c in cards}
    ledger = sorted((v for k, v in seen.items() if k not in carded), key=lambda v: -v["hits"])
    top = max([h for h, _ in cards] + [h for h, _ in questions] + [v["hits"] for v in ledger] + [0])

    def keep(h: int) -> bool:
        return h > 0 and (h == top or h >= 2 or len(terms_l) == 1)

    return {"cards": [c for h, c in cards if keep(h)][:limit],
            "questions": [q for h, q in questions if keep(h)][:limit],
            "ledger": [v["entry"] for v in ledger if keep(v["hits"])][:limit]}


def render_find(res: dict) -> str:
    out = []
    if res["questions"]:
        out.append("questions:")
        for q in res["questions"]:
            d = q.data
            out.append(f"  {d.get('project')}/{d.get('id')} [{d.get('stage')}, {d.get('status')}] {d.get('ask')}"
                       f" (picked: {', '.join(map(str, as_list(d.get('picked')))) or '-'}; scanned {d.get('scanned') or 'never'})")
    if res["cards"]:
        out.append("cards:")
        out += [f"  {card_line(c)}" for c in res["cards"]]
    if res["ledger"]:
        out.append("looked at, no card:")
        out += [f"  {e['repo']} {e.get('verdict')} for {e.get('project')}/{e.get('question')} on {e.get('date')}"
                + (f": {e.get('reason')}" if e.get("reason") else "") for e in res["ledger"]]
    return "\n".join(out) or "nothing in the registry matches. Ask the question: github-scout ask <project>/<id> \"...\""


def coverage(store: Store, project: str, qid: str) -> dict:
    ref = f"{project}/{qid}"
    cards = [c for c in store.cards() if not c.error and any(
        isinstance(u, dict) and u.get("project") == project and u.get("question") == qid for u in as_list(c.data.get("uses")))]
    latest = {k: e for k, e in store.verdicts().items() if k[1] == ref}
    counts: dict[str, int] = {}
    for e in latest.values():
        counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1
    return {"cards": cards, "verdicts": counts,
            "open": [e for e in latest.values() if e["verdict"] in ("short", "peeked", "list")],
            "scans": [p.stem for p in store.scans(project, qid)]}


def show_question(store: Store, ref: str) -> str:
    doc = store.question(ref)
    d = doc.data
    cov = coverage(store, d["project"], d["id"])
    out = [f"{d['project']}/{d['id']} [{d.get('stage')}, {d.get('status')}] {d.get('ask')}",
           f"stage: {stage_help(store, str(d.get('stage')))}",
           f"file: {doc.path}",
           f"picked: {', '.join(map(str, as_list(d.get('picked')))) or '-'} · scanned {d.get('scanned') or 'never'}"
           f" · scans {len(cov['scans'])}"]
    if d.get("backbone"):
        out.append(f"backbone: {d['backbone']}" + (f" · alternate: {d['alternate']}" if d.get("alternate") else ""))
    adopted = [(c.id, a) for c in store.cards() if not c.error for a in adoptions(c.data, d["project"], dropped=True)
               if a.get("question") == d["id"]]
    if adopted:
        out.append("adopted: " + ", ".join(f"{slug} ({a.get('mode')} {', '.join(map(str, as_list(a.get('into'))))}"
                                           + (f"; dropped {a['dropped']}" if a.get("dropped") else "") + ")"
                                           for slug, a in adopted))
    out += ["vocabulary: " + " · ".join(f"{k}={as_list(d.get(k))}" for k in ("langs", "entities", "mechanisms", "forms", "problems", "topics")
                                        if as_list(d.get(k))),
            "looked at: " + (", ".join(f"{k} {v}" for k, v in sorted(cov["verdicts"].items())) or "nothing yet")]
    if cov["open"]:
        out.append("waiting for a decision: " + ", ".join(f"{e['repo']} ({e['verdict']})" for e in cov["open"]))
    if cov["cards"]:
        out.append("cards:")
        out += [f"  {card_line(c)}" for c in cov["cards"]]
    if doc.body.strip():
        out += ["", doc.body.strip()]
    return "\n".join(out)


def show_card(store: Store, ref: str) -> str:
    ref = repo_ref(ref)
    card = store.card(ref)
    hist = store.history(card.id if card else ref)
    out = []
    if card:
        out += [f"card: {card.path}", card.path.read_text(encoding="utf-8").strip()]
        results = [str(x) for x in as_list(card.data.get("results"))]
        out += ["results:"] + [f"  {x}" for x in results] if results else \
            ["results: none recorded (note --results <links to what it made>)"]
        adopted = adoptions(card.data, dropped=True)
        if adopted:
            out.append("adopted:")
            out += [f"  {adoption_text(a)}" for a in adopted]
        cached = store.cached(card.id)
        if cached:
            out.append("cached source: " + ", ".join(str(p) for p in cached))
    if hist:
        out.append("ledger:")
        out += [f"  {e.get('date')} {e.get('verdict')} ({e.get('level')}) {e.get('project')}/{e.get('question')}"
                + (f": {e.get('reason')}" if e.get("reason") else "")
                + (f" · low stars: {e['low_stars']}" if e.get("low_stars") else "")
                + (f" · no results: {e['no_results']}" if e.get("no_results") else "") for e in hist]
    return "\n".join(out) or f"{ref}: never seen. Look at it: github-scout look {ref}"


def write_index(store: Store) -> Path:
    cards = [c for c in store.cards() if not c.error]
    lines = [f"# {store.settings.get('name') or 'Registry'}", "",
             f"Generated by `github-scout check` on {today()}. Do not edit; edit the questions and cards.", "",
             "## Questions", "", "| question | stage | status | picked | cards | looked at | asks |", "|---|---|---|---|---|---|---|"]
    for q in store.questions():
        if q.error:
            continue
        d = q.data
        cov = coverage(store, d["project"], d["id"])
        lines.append(f"| [{d['project']}/{d['id']}](projects/{d['project']}/questions/{d['id']}.md) | {d.get('stage')} | "
                     f"{d.get('status')} | {', '.join(map(str, as_list(d.get('picked')))) or '-'} | {len(cov['cards'])} | "
                     f"{sum(cov['verdicts'].values())} | {_cell(d.get('ask'))} |")
    titles = {"skill": "Skills", "software": "Software", "list": "Lists", "other": "Other"}
    for kind in KINDS:
        group = [c for c in cards if c.data.get("kind") == kind]
        if not group:
            continue
        lines += ["", f"## {titles[kind]}", "", "| repo | take | used by | summary | pushed | reviewed |",
                  "|---|---|---|---|---|---|"]
        for c in sorted(group, key=lambda c: (TAKES.index(strongest(card_takes(c.data)) or "skip"), c.id.lower())):
            d = c.data
            uses = [u for u in as_list(d.get("uses")) if isinstance(u, dict)]
            lines.append(f"| [{c.id}](repos/{c.path.name}) | {strongest(card_takes(d)) or '-'} | "
                         f"{', '.join(sorted({str(u.get('project')) + '/' + str(u.get('question') or '-') for u in uses}))} | "
                         f"{_cell(d.get('summary'))} | {d.get('pushed', '')} | {d.get('reviewed')} |")
    led = store.ledger()
    repos = {str(e.get("repo", "")).lower() for e in led if e.get("repo")}
    lines += ["", "## Ledger", "", f"{len(led)} verdicts on {len(repos)} repositories; {len(cards)} have cards.", ""]
    path = store.root / "INDEX.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _cell(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).replace("|", "/")[:120]
