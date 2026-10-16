"""`github-scout site`: one self-contained HTML page for people browsing the registry.

Everything is inline: CSS, JS, and the registry as JSON in a <script type="application/json"> tag.
Markdown is rendered here by a small renderer that escapes all registry text; the page script inserts
only that rendered Markdown as HTML and builds everything else from text nodes.
"""

from __future__ import annotations

import datetime as _dt
import html
import json
import os
import re
from pathlib import Path
from urllib.parse import quote

from .registry import STAGE_HELP, T
from .store import KINDS, SHA, SLUG, TAKES, Doc, Store, as_list, card_takes, strongest

# ---------------------------------------------------------------------------
# Markdown: the subset agents write. Blocks are parsed into tuples first so unfilled template
# scaffolding can be pruned before rendering:
#   ("h", level, text) ("p", text) ("code", lang, text) ("quote", blocks) ("hr",)
#   ("list", ordered, start, [(checked | None, blocks)], tight) ("table", aligns, head, rows)

_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*([^`\s]*)")
_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:[ \t]+(.*?))?(?:[ \t]+#+)?[ \t]*$")
_HR = re.compile(r"^ {0,3}([-*_])(?:[ \t]*\1){2,}[ \t]*$")
_QUOTE = re.compile(r"^ {0,3}> ?(.*)$")
_ITEM = re.compile(r"^( *)([-*+]|\d{1,9}[.)])(?:[ \t]+(.*)|[ \t]*$)")
_TASK = re.compile(r"^\[([ xX])\][ \t]+")


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _cjk(ch: str) -> bool:
    return bool(ch) and ("⺀" <= ch <= "鿿" or "가" <= ch <= "힯" or "＀" <= ch <= "￯")


def _cells(row: str) -> list[str]:
    """Split a table row on pipes outside code spans; `\\|` is a literal pipe."""
    row = row.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|") and not row.endswith("\\|"):
        row = row[:-1]
    out, cur, code, i = [], "", False, 0
    while i < len(row):
        ch = row[i]
        if ch == "\\" and row[i + 1:i + 2] == "|":
            cur, i = cur + "|", i + 2
            continue
        if ch == "`":
            code = not code
        if ch == "|" and not code:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
        i += 1
    return out + [cur.strip()]


def _table_at(lines: list[str], i: int) -> bool:
    if "|" not in lines[i] or i + 1 >= len(lines) or "|" not in lines[i + 1]:
        return False
    sep = _cells(lines[i + 1])
    return all(re.fullmatch(r":?-+:?", c) for c in sep) and len(sep) == len(_cells(lines[i]))


def _starts_block(lines: list[str], i: int) -> bool:
    line = lines[i]
    return bool(_HEADING.match(line) or _FENCE.match(line) or _HR.match(line) or _QUOTE.match(line)
                or _ITEM.match(line) or _table_at(lines, i))


def _join(lines: list[str]) -> str:
    """Join paragraph lines: a space between words, nothing between CJK characters, \\x01 for hard breaks."""
    text = ""
    for k, raw in enumerate(lines):
        s = raw.strip()
        hard = raw.endswith("  ") or s.endswith("\\")
        s = s[:-1] if s.endswith("\\") else s
        if k and not text.endswith("\x01"):
            text += "" if _cjk(text[-1:]) and _cjk(s[:1]) else " "
        text += s + ("\x01" if hard and k < len(lines) - 1 else "")
    return text


def parse(text: str) -> list:
    for ch in ("\x00", "\x01"):
        text = text.replace(ch, "")
    return _blocks(text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ").split("\n"))


def _blocks(lines: list[str]) -> list:
    out, i, n = [], 0, len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        m = _FENCE.match(line)
        if m:
            close = re.compile(r"^ {0,3}" + re.escape(m.group(1)[0]) + f"{{{len(m.group(1))},}}[ \t]*$")
            body, i = [], i + 1
            while i < n and not close.match(lines[i]):
                body.append(lines[i])
                i += 1
            out.append(("code", m.group(2), "\n".join(body)))
            i += 1
            continue
        m = _HEADING.match(line)
        if m:
            out.append(("h", len(m.group(1)), (m.group(2) or "").strip()))
            i += 1
            continue
        if _HR.match(line):
            out.append(("hr",))
            i += 1
            continue
        if _QUOTE.match(line):
            body = []
            while i < n and lines[i].strip():
                q = _QUOTE.match(lines[i])
                if q:
                    body.append(q.group(1))
                elif not _starts_block(lines, i):
                    body.append(lines[i])  # lazy continuation
                else:
                    break
                i += 1
            out.append(("quote", _blocks(body)))
            continue
        if _table_at(lines, i):
            head = _cells(line)
            aligns = [("center" if c.startswith(":") and c.endswith(":") else "right" if c.endswith(":")
                       else "left" if c.startswith(":") else None) for c in _cells(lines[i + 1])]
            rows, i = [], i + 2
            while i < n and lines[i].strip() and "|" in lines[i]:
                rows.append((_cells(lines[i]) + [""] * len(head))[:len(head)])
                i += 1
            out.append(("table", aligns, head, rows))
            continue
        if _ITEM.match(line):
            block, i = _list(lines, i)
            out.append(block)
            continue
        para, i = [line], i + 1
        while i < n and lines[i].strip() and not _starts_block(lines, i):
            para.append(lines[i])
            i += 1
        out.append(("p", _join(para)))
    return out


def _list(lines: list[str], i: int) -> tuple:
    first = _ITEM.match(lines[i])
    indent, ordered = len(first.group(1)), first.group(2)[0].isdigit()
    start = int(first.group(2)[:-1]) if ordered else None
    items, tight, n = [], True, len(lines)

    def sibling(line: str) -> bool:
        m = _ITEM.match(line)
        return bool(m) and not _HR.match(line) and len(m.group(1)) < indent + 2 and m.group(2)[0].isdigit() == ordered

    while i < n and sibling(lines[i]):
        m = _ITEM.match(lines[i])
        content = m.group(3) or ""
        col = len(lines[i]) - len(content) if content else len(m.group(1)) + len(m.group(2)) + 1
        body, i = [content], i + 1
        while i < n:
            line = lines[i]
            if not line.strip():
                j = i
                while j < n and not lines[j].strip():
                    j += 1
                if j < n and _indent(lines[j]) >= indent + 2:
                    body += [""] * (j - i)
                    i, tight = j, False
                    continue
                break
            if _indent(line) >= indent + 2:
                body.append(line[min(_indent(line), col):])
            elif _starts_block(lines, i):
                break
            else:
                body.append(line.strip())  # lazy continuation
            i += 1
        task = _TASK.match(body[0])
        if task:
            body[0] = body[0][task.end():]
        items.append((task.group(1) != " " if task else None, _blocks(body)))
        j = i
        while j < n and not lines[j].strip():
            j += 1
        if j > i:
            if j < n and sibling(lines[j]):
                i, tight = j, False
                continue
            break
    return ("list", ordered, start, items, tight), i


def _hint_patterns() -> list:
    """The parenthesised hints in the question and card templates, as patterns ({id} and the like match anything).
    Lines whose own text carries a placeholder ("Stage: {stage} (...)") are content, not hints."""
    hints = set()
    for templates in T.values():
        for text in templates.values():
            for line in text.splitlines():
                s = re.sub(r"^(?:[-*+]|\d+\.)\s+", "", line.strip())
                m = re.match(r"^(.*?)[(（].*[)）]$", s)
                if m and not s.startswith(("#", "|")) and "{" not in m.group(1):
                    hints.add(s)
    return [re.compile(re.sub(r"\\\{\w+\\\}", ".*?", re.escape(s))) for s in sorted(hints)]


_HINTS = _hint_patterns()


def _is_hint(text: str) -> bool:
    return any(p.fullmatch(text.strip()) for p in _HINTS)


def prune(blocks: list) -> list:
    """Drop unfilled template scaffolding: template hints, header-only tables, headings left empty."""
    kept = []
    for b in blocks:
        if (b[0] == "p" and _is_hint(b[1])) or (b[0] == "table" and not b[3]):
            continue
        if b[0] == "list":
            items = [it for it in b[3] if not (len(it[1]) == 1 and it[1][0][0] == "p" and _is_hint(it[1][0][1]))]
            if not items:
                continue
            b = b[:3] + (items,) + b[4:]
        kept.append(b)
    out = []
    for i, b in enumerate(kept):
        if b[0] == "h":
            filled = False
            for nb in kept[i + 1:]:
                if nb[0] == "h" and nb[1] <= b[1]:
                    break
                if nb[0] != "h":
                    filled = True
                    break
            if not filled:
                continue
        out.append(b)
    return out


def _untitled(blocks: list) -> list:
    """Drop the document title: the first level-1 heading, when no level-2 heading comes before it."""
    for i, b in enumerate(blocks):
        if b[0] == "h":
            return blocks[:i] + blocks[i + 1:] if b[1] == 1 else blocks
    return blocks


def _sections(blocks: list) -> tuple[list, list]:
    """(preamble, [(title, blocks)]) split at the top heading level."""
    level = min((b[1] for b in blocks if b[0] == "h"), default=2)
    pre, secs = [], []
    for b in blocks:
        if b[0] == "h" and b[1] == level:
            secs.append((b[2], []))
        else:
            (secs[-1][1] if secs else pre).append(b)
    return pre, secs


def _plain(blocks: list) -> str:
    parts = []
    for b in blocks:
        if b[0] == "p":
            parts.append(b[1])
        elif b[0] == "quote":
            parts.append(_plain(b[1]))
        elif b[0] == "list":
            parts += [_plain(inner) for _, inner in b[3]]
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", " ".join(parts))
    text = re.sub(r"`|\*\*|~~|\*(?=\S)|(?<=\S)\*", "", text.replace("\x01", " "))
    return re.sub(r"\s+", " ", text).strip()


# -- inline ------------------------------------------------------------------

_CODE_SPAN = re.compile(r"(`+)(.+?)(?<!`)\1(?!`)", re.S)
_BACKSLASH = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|<>~])")
_AUTOLINK = re.compile(r"<((?:https?://|mailto:)[^\s<>]+)>")
_IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*<?([^\s()<>]*)>?(?:\s+\"[^\"]*\")?\s*\)")
_LINK = re.compile(r"\[((?:[^\[\]]|\[[^\[\]]*\])+)\]\(\s*<?([^\s()<>]*(?:\([^\s()<>]*\)[^\s()<>]*)*)>?"
                   r"(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")
_BARE_URL = re.compile(r"https?://[^\s<>\"'`　-〿぀-鿿＀-￯]+")
_EMPHASIS = [
    (re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\w)__(?=\S)(.+?)(?<=\S)__(?!\w)"), r"<strong>\1</strong>"),
    (re.compile(r"(?<!\*)\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?!\*)"), r"<em>\1</em>"),
    (re.compile(r"(?<!\w)_(?=[^\s_])(.+?)(?<=[^\s_])_(?!\w)"), r"<em>\1</em>"),
    (re.compile(r"~~(?=\S)(.+?)(?<=\S)~~"), r"<del>\1</del>"),
]


def _emphasis(escaped: str) -> str:
    for pattern, repl in _EMPHASIS:
        escaped = pattern.sub(repl, escaped)
    return escaped


def _inline(text: str, link) -> str:
    """Escape everything; turn back only the constructs we know into tags we write."""
    slots: list[str] = []

    def keep(fragment: str) -> str:
        slots.append(fragment)
        return f"\x00{len(slots) - 1}\x00"

    def code(m) -> str:
        body = m.group(2)
        if len(body) > 2 and body[0] == body[-1] == " ":
            body = body[1:-1]
        return keep(f"<code>{_esc(body)}</code>")

    def bare(m) -> str:
        url, tail = m.group(0), ""
        while url and url[-1] in ".,;:!?)]}'\"" and not (url[-1] == ")" and url.count("(") >= url.count(")")):
            url, tail = url[:-1], url[-1] + tail
        return keep(_anchor(url, _esc(url), link)) + tail

    text = _CODE_SPAN.sub(code, text.replace("\x00", ""))
    text = _BACKSLASH.sub(lambda m: keep(_esc(m.group(1))), text)
    text = _AUTOLINK.sub(lambda m: keep(_anchor(m.group(1), _esc(m.group(1)), link)), text)
    text = _IMAGE.sub(lambda m: keep(_anchor(m.group(2), _esc(m.group(1) or m.group(2)), link)), text)
    text = _LINK.sub(lambda m: keep(_anchor(m.group(2), _emphasis(_esc(m.group(1))), link)), text)
    text = _BARE_URL.sub(bare, text)
    text = _emphasis(re.sub(r"&lt;br\s*/?&gt;", "<br>", _esc(text), flags=re.I)).replace("\x01", "<br>")
    for _ in range(4):  # link text can hold code spans: restore until nothing is left
        if "\x00" not in text:
            break
        text = re.sub(r"\x00(\d+)\x00", lambda m: slots[int(m.group(1))], text)
    return text


def _anchor(url: str, inner: str, link) -> str:
    href = link(url) if link else _web(url)
    if not href:
        return inner
    external = ' target="_blank" rel="noopener noreferrer"' if href.startswith(("http://", "https://")) else ""
    return f'<a href="{_esc(href)}"{external}>{inner}</a>'


def _web(url: str) -> str | None:
    url = url.strip()
    return url if re.match(r"(?i)^(?:https?://|mailto:)[^\s\x00-\x1f\x7f]+$", url) else None


def _linker(doc_dir: Path, out_dir: Path, root: Path):
    """Web links pass; relative paths point at the registry file from wherever the page is written;
    anything else (other schemes, control characters, bare anchors) becomes plain text."""

    def link(url: str) -> str | None:
        if _web(url):
            return _web(url)
        url = url.strip()
        if (not url or url.startswith(("#", "//")) or re.search(r"[\x00-\x1f\x7f\\]", url)
                or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", url)):
            return None
        path, _, frag = url.partition("#")
        base = root if path.startswith("/") else doc_dir
        try:
            rel = os.path.relpath(os.path.normpath(os.path.join(base, path.lstrip("/"))), out_dir)
        except ValueError:
            return None
        rel = Path(rel).as_posix()
        rel = rel if rel.startswith(".") else "./" + rel  # never let a path read as a scheme
        return quote(rel, safe="/.-_~%") + ("#" + quote(frag, safe="-_.~%") if frag else "")

    return link


# -- blocks to HTML ----------------------------------------------------------


def render(blocks: list, link=None, top: int = 3) -> str:
    """HTML for blocks; the highest heading becomes <h{top}>."""
    shift = top - min((b[1] for b in blocks if b[0] == "h"), default=top)
    return _render(blocks, link, shift, False)


def _render(blocks: list, link, shift: int, tight: bool) -> str:
    out = []
    for b in blocks:
        kind = b[0]
        if kind == "h":
            level = max(1, min(6, b[1] + shift))
            out.append(f"<h{level}>{_inline(b[2], link)}</h{level}>")
        elif kind == "p":
            out.append(_inline(b[1], link) if tight else f"<p>{_inline(b[1], link)}</p>")
        elif kind == "code":
            lang = f' class="lang-{_esc(b[1])}"' if b[1] else ""
            out.append(f"<pre><code{lang}>{_esc(b[2])}</code></pre>")
        elif kind == "quote":
            out.append(f"<blockquote>{_render(b[1], link, shift, False)}</blockquote>")
        elif kind == "hr":
            out.append("<hr>")
        elif kind == "list":
            _, ordered, start, items, is_tight = b
            tag = "ol" if ordered else "ul"
            attrs = f' start="{start}"' if ordered and start != 1 else ""
            lis = []
            for checked, inner in items:
                box = "" if checked is None else f'<input type="checkbox" disabled{" checked" if checked else ""}> '
                cls = "" if checked is None else ' class="task"'
                lis.append(f"<li{cls}>{box}{_render(inner, link, shift, is_tight)}</li>")
            out.append(f"<{tag}{attrs}>{''.join(lis)}</{tag}>")
        elif kind == "table":
            _, aligns, head, rows = b

            def cell(tag: str, text: str, align) -> str:
                style = f' style="text-align:{align}"' if align else ""
                return f"<{tag}{style}>{_inline(text, link)}</{tag}>"

            thead = "".join(cell("th", c, a) for c, a in zip(head, aligns))
            tbody = "".join("<tr>" + "".join(cell("td", c, a) for c, a in zip(r, aligns)) + "</tr>" for r in rows)
            out.append(f'<div class="tw"><table><thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table></div>')
    return "\n".join(out)


def markdown(text: str, link=None) -> str:
    """Markdown to safe HTML, as written (no pruning)."""
    return render(parse(text), link)


# ---------------------------------------------------------------------------
# The data the page shows

_ANSWER_TITLES = {"answer", "the answer", "答案", "回答"}
_VERDICT_ORDER = ["short", "list", "peeked", "later", "card", "skip"]


def _date(v) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(str(v or "")[:10])
    except ValueError:
        return None


def _months(since: _dt.date, until: _dt.date) -> int:
    return (until.year - since.year) * 12 + until.month - since.month - (until.day < since.day)


def _s(v) -> str:
    return "" if v is None else str(v)


def _int(v) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _uses(doc: Doc) -> list[dict]:
    return [{k: _s(u.get(k)) for k in ("project", "question", "take", "where", "note")}
            for u in as_list(doc.data.get("uses")) if isinstance(u, dict)]


def _card(c: Doc, link, day: _dt.date, root: Path) -> dict:
    d = c.data
    blocks = prune(_untitled(parse(c.body)))
    pre, secs = _sections(blocks)
    idea = _plain(secs[0][1] if secs else pre)
    pushed = _date(d.get("pushed"))
    age = _months(pushed, day) if pushed else None
    url = _s(d.get("repo"))
    if not re.match(r"^https?://[^\s\"'<>\\]+$", url):
        url = f"https://github.com/{c.id}" if SLUG.match(c.id) else ""
    return {
        "id": c.id, "url": url, "kind": _s(d.get("kind")), "form": _s(d.get("form")), "summary": _s(d.get("summary")),
        "stars": _int(d.get("stars")), "created": _s(d.get("created")),
        "pushed": _s(d.get("pushed")), "age": age, "stale": age is not None and age >= 3,
        "reviewed": _s(d.get("reviewed")), "level": _s(d.get("level")),
        "commit": _s(d.get("commit")) if SHA.match(_s(d.get("commit"))) else "", "branch": _s(d.get("branch")),
        "uses": _uses(c), "take": strongest(card_takes(d)) or "",
        "idea": idea if len(idea) <= 300 else idea[:299].rstrip() + "…",
        "body": render(blocks, link), "file": c.path.relative_to(root).as_posix(),
    }


def _question(store: Store, q: Doc, link, cards: list[Doc], latest: dict, root: Path) -> dict:
    d = q.data
    pid, qid = q.path.parent.parent.name, q.path.stem
    ref = f"{pid}/{qid}"
    pre, secs = _sections(_untitled(parse(q.body)))
    answer = [b for title, blocks in secs if title.strip().lower().rstrip(":：") in _ANSWER_TITLES for b in blocks]
    context = pre + [b for title, blocks in secs if title.strip().lower().rstrip(":：") not in _ANSWER_TITLES
                     for b in [("h", 2, title)] + blocks]

    looked: dict[str, dict] = {}
    for (repo, r), e in latest.items():
        if r == ref:
            looked[repo] = {"repo": _s(e.get("repo")), "card": False, "group": "verdict", "mark": _s(e.get("verdict")),
                            "note": _s(e.get("reason")), "date": _s(e.get("date"))}
    for c in cards:
        for u in _uses(c):
            if u["project"] == pid and u["question"] == qid:
                looked[c.id.lower()] = {"repo": c.id, "card": True, "group": "take", "mark": u["take"],
                                        "note": u["note"], "date": _s(c.data.get("reviewed"))}
    rank = {**{("take", t): i for i, t in enumerate(TAKES)},
            **{("verdict", v): 10 + i for i, v in enumerate(_VERDICT_ORDER)}}
    rows = sorted(looked.values(), key=lambda r: (rank.get((r["group"], r["mark"]), 99), r["repo"].lower()))

    scans = store.scans(pid, qid)
    last_scan = f"{scans[-1].stem[:4]}-{scans[-1].stem[4:6]}-{scans[-1].stem[6:8]}" if scans else ""
    picked = []
    for slug in as_list(d.get("picked")):
        card = store.card(str(slug))
        picked.append(card.id if card and not card.error else str(slug))
    stage = _s(d.get("stage"))
    return {
        "ref": ref, "project": pid, "id": qid, "ask": _s(d.get("ask")), "stage": stage,
        "stageHelp": STAGE_HELP[store.lang].get(stage, ""), "status": _s(d.get("status")), "picked": picked,
        "looked": rows, "scanned": max(_s(d.get("scanned")), last_scan), "scans": len(scans),
        "answer": render(prune(answer), link), "context": render(prune(context), link),
        "file": q.path.relative_to(root).as_posix(),
    }


def site_data(store: Store, out_dir: Path) -> dict:
    root = store.root
    day = _dt.date.today()
    projects = {p.path.parent.name: _s(p.data.get("name")) or p.path.parent.name
                for p in store.projects() if not p.error}
    cards = [c for c in store.cards() if not c.error]
    latest = store.verdicts()

    def link_for(doc: Doc):
        return _linker(doc.path.parent.resolve(), out_dir.resolve(), root.resolve())

    questions = [_question(store, q, link_for(q), cards, latest, root) for q in store.questions() if not q.error]
    order = {pid: i for i, pid in enumerate(projects)}
    questions.sort(key=lambda q: q["id"])
    questions.sort(key=lambda q: (q["scanned"], len(q["looked"])), reverse=True)
    questions.sort(key=lambda q: (order.get(q["project"], len(order)), q["status"] != "answered"))

    card_rows = [_card(c, link_for(c), day, root) for c in cards]
    card_rows.sort(key=lambda c: (-(c["stars"] or 0), c["id"].lower()))
    card_rows.sort(key=lambda c: TAKES.index(c["take"]) if c["take"] in TAKES else len(TAKES))

    # A repo counts as skipped when every current verdict on it, or its card's take, is skip.
    marks: dict[str, dict[str, str]] = {}
    for (repo, ref), e in latest.items():
        marks.setdefault(repo, {})[ref] = _s(e.get("verdict"))
    for c in cards:
        for u in _uses(c):
            marks.setdefault(c.id.lower(), {})[f"{u['project']}/{u['question']}"] = u["take"]
    skipped = sum(1 for m in marks.values() if m and all(v == "skip" for v in m.values()))

    return {
        "name": _s(store.settings.get("name")) or root.name, "lang": store.lang, "built": day.isoformat(),
        "counts": {"questions": len(questions), "cards": len(card_rows),
                   "verdicts": sum(1 for e in store.ledger() if e.get("repo")), "skipped": skipped},
        "projects": projects, "kinds": KINDS, "takes": TAKES,
        "questions": questions, "cards": card_rows, "ui": UI[store.lang],
    }


# ---------------------------------------------------------------------------
# The page

UI = {
    "en": {
        "questions": "Questions", "repos": "Repos",
        "overview": "{questions} questions · {cards} cards · {verdicts} verdicts in the ledger · {skipped} repos skipped",
        "built": "Generated on {date} by github-scout.", "noscript": "This page needs JavaScript to show the registry.",
        "noQuestions": "No questions yet.", "back": "All questions",
        "stage": "Stage", "status": "Status", "picked": "Picked", "looked": "Looked at", "lastScan": "Last scan",
        "lookedN": "{n} repos", "scansN": "{n} scans", "never": "never", "none": "none",
        "answer": "Answer", "noAnswer": "No answer written yet.", "context": "Where we are and what was searched",
        "lookedList": "Repos looked at ({n})",
        "search": "Search repos", "allKinds": "All kinds", "allTakes": "All takes", "allProjects": "All projects",
        "allQuestions": "All questions", "count": "{n} of {total}", "clear": "Clear",
        "noRepos": "No repos match these filters.",
        "created": "created", "pushed": "pushed", "reviewed": "reviewed", "stale": "no push for {n} months",
        "level": "Review depth", "commit": "Reviewed commit", "file": "File",
        "uses": "Taken by", "github": "GitHub", "stars": "stars",
        "labels": {
            "stage": {}, "status": {}, "take": {}, "verdict": {},
            "kind": {}, "level": {"meta": "metadata only", "look": "looked", "read": "read the code", "trial": "tried it"},
        },
    },
    "zh": {
        "questions": "问题", "repos": "仓库",
        "overview": "{questions} 个问题 · {cards} 张卡片 · 账本 {verdicts} 条 · 跳过 {skipped} 个仓库",
        "built": "{date} 由 github-scout 生成。", "noscript": "这个页面要开 JavaScript 才能显示。",
        "noQuestions": "还没有问题。", "back": "全部问题",
        "stage": "阶段", "status": "状态", "picked": "选用", "looked": "看过", "lastScan": "最近扫描",
        "lookedN": "{n} 个仓库", "scansN": "{n} 次扫描", "never": "没扫过", "none": "无",
        "answer": "答案", "noAnswer": "还没写答案。", "context": "现状和搜索记录",
        "lookedList": "看过的仓库（{n}）",
        "search": "搜索仓库", "allKinds": "全部类型", "allTakes": "全部取舍", "allProjects": "全部项目",
        "allQuestions": "全部问题", "count": "{n} / {total}", "clear": "清除",
        "noRepos": "没有符合筛选的仓库。",
        "created": "创建", "pushed": "推送", "reviewed": "审阅", "stale": "{n} 个月没有推送",
        "level": "看到哪一步", "commit": "审阅的提交", "file": "文件",
        "uses": "用在哪", "github": "GitHub", "stars": "星",
        "labels": {
            "stage": {"idea": "想法", "prototype": "雏形", "working": "能用", "polishing": "打磨"},
            "status": {"open": "待答", "answered": "已答"},
            "take": {"use": "采用", "adapt": "改用", "learn": "借鉴", "later": "观望", "skip": "不用"},
            "verdict": {"peeked": "瞄过", "short": "短名单", "list": "清单", "later": "观望", "skip": "跳过",
                        "card": "建卡"},
            "kind": {"skill": "技能", "software": "软件", "list": "清单", "other": "其他"},
            "level": {"meta": "只看了元数据", "look": "看过", "read": "读过代码", "trial": "试用过"},
        },
    },
}

CSS = """
:root{color-scheme:light dark;--bg:#fff;--bg2:#f6f8fa;--fg:#1f2328;--mut:#59636e;--bd:#d1d9e0;--bd2:#e8ecf0;
--ac:#0969da;--sel:#eaf3fd;--ok:#1a7f37;--ok-bg:#dafbe1;--info-bg:#ddf4ff;--warn:#9a6700;--warn-bg:#fff8c5;--neu-bg:#eff2f5}
@media (prefers-color-scheme:dark){:root{--bg:#0d1117;--bg2:#151b23;--fg:#e6edf3;--mut:#9198a1;--bd:#3d444d;--bd2:#262c36;
--ac:#4493f8;--sel:#16233a;--ok:#3fb950;--ok-bg:#12261e;--info-bg:#121d2f;--warn:#d29922;--warn-bg:#272115;--neu-bg:#212830}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans",
Helvetica,Arial,"PingFang SC","Hiragino Sans GB","Microsoft YaHei",sans-serif}
a{color:var(--ac);text-decoration:none}a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--ac);outline-offset:2px}
.wrap{max-width:1280px;margin:0 auto;padding:0 16px}
.top{border-bottom:1px solid var(--bd);background:var(--bg2)}
.brand{padding:14px 0 6px;display:flex;flex-wrap:wrap;align-items:baseline;gap:4px 14px}
.brand h1{margin:0;font-size:16px;font-weight:600}
.overview{color:var(--mut);font-size:13px}
.tabs{display:flex;gap:4px}
.tabs a{padding:8px 10px 7px;color:var(--fg);border-bottom:2px solid transparent;font-weight:500}
.tabs a:hover{text-decoration:none;border-color:var(--bd)}
.tabs a[aria-current=page]{border-color:var(--ac);font-weight:600}
main.wrap{padding-top:20px;padding-bottom:32px}
footer{color:var(--mut);font-size:12px;padding-bottom:24px}
.muted{color:var(--mut)}.empty{color:var(--mut)}
.badge{display:inline-block;font-size:12px;line-height:18px;padding:0 7px;border-radius:999px;background:var(--neu-bg);
color:var(--mut);white-space:nowrap;font-weight:500;vertical-align:1px}
.take-use,.status-answered{background:var(--ok-bg);color:var(--ok)}
.take-adapt{background:var(--info-bg);color:var(--ac)}
.take-learn{background:var(--warn-bg);color:var(--warn)}
.take-skip,.verdict-skip{background:none;box-shadow:inset 0 0 0 1px var(--bd2)}
.verdict-short,.verdict-card{background:var(--info-bg);color:var(--ac)}
.kind{background:none;box-shadow:inset 0 0 0 1px var(--bd)}
.qgrid{display:grid;grid-template-columns:minmax(240px,320px) minmax(0,1fr);gap:32px;align-items:start}
.qlist{position:sticky;top:12px;max-height:calc(100vh - 24px);overflow:auto;margin:0 -8px;padding:0 8px}
.group{font-size:12px;font-weight:600;color:var(--mut);margin:0 0 6px;padding:0 10px}
.qitem{display:block;padding:8px 10px;border-radius:6px;color:var(--fg)}
.qitem:hover{background:var(--bg2);text-decoration:none}
.qitem[aria-current=page]{background:var(--sel)}
.qask{display:block;font-weight:500;line-height:1.4}
.qmeta{display:block;margin-top:3px;font-size:12px;color:var(--mut)}
.qdetail{min-width:0}
.back{display:none;margin-bottom:12px;font-size:13px}
.crumbs{color:var(--mut);font-size:13px}
.qtitle{font-size:21px;line-height:1.35;font-weight:600;margin:4px 0 14px;overflow-wrap:anywhere}
.facts{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:5px 16px;margin:0 0 24px;font-size:13px}
.facts dt{color:var(--mut)}.facts dd{margin:0}
.answer{border-top:1px solid var(--bd);padding-top:4px}
.label{font-size:12px;font-weight:600;color:var(--mut);margin:12px 0 4px;letter-spacing:.02em}
.more{border-top:1px solid var(--bd2);padding:10px 0}
.more summary{cursor:pointer;font-weight:600;color:var(--fg)}
.more[open] summary{margin-bottom:10px}
.looked{list-style:none;margin:0;padding:0}
.looked li{padding:7px 0;border-top:1px solid var(--bd2)}.looked li:first-child{border-top:0}
.lnote{color:var(--mut);font-size:13px;margin-top:2px;overflow-wrap:anywhere}
.md{font-size:15px;line-height:1.7;max-width:48em;overflow-wrap:anywhere}
.md>:first-child{margin-top:0}
.md h1,.md h2,.md h3{font-size:17px;line-height:1.4;margin:26px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--bd2)}
.md h4{font-size:15px;margin:20px 0 6px}.md h5,.md h6{font-size:14px;margin:16px 0 4px;color:var(--mut)}
.md p,.md ul,.md ol,.md pre,.md blockquote,.md .tw{margin:0 0 12px}
.md ul,.md ol{padding-left:1.6em}.md ul{list-style:disc}.md ul ul{list-style:circle}.md ul ul ul{list-style:square}.md li+li{margin-top:3px}.md li>ul,.md li>ol{margin:3px 0 0}
.md li.task{list-style:none}.md li.task input{margin:0 .4em 0 -1.3em;vertical-align:-1px}
.md code{font:12.5px/1.5 ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,monospace;background:var(--bg2);
padding:.15em .35em;border-radius:4px}
.md pre{background:var(--bg2);border:1px solid var(--bd2);border-radius:6px;padding:10px 12px;overflow:auto}
.md pre code{background:none;padding:0;font-size:12.5px}
.md blockquote{padding:0 0 0 12px;border-left:3px solid var(--bd);color:var(--mut);margin-left:0}
.md hr{border:0;border-top:1px solid var(--bd);margin:20px 0}
.tw{overflow-x:auto}
.md table{border-collapse:collapse;font-size:14px;line-height:1.5}
.md th,.md td{border:1px solid var(--bd);padding:6px 10px;text-align:left;vertical-align:top;min-width:5em;overflow-wrap:normal}
.md th{background:var(--bg2);font-weight:600}
.filters{display:grid;grid-template-columns:minmax(0,2fr) repeat(4,minmax(0,1fr)) auto;gap:8px;margin-bottom:10px}
input,select,button{font:inherit;font-size:13px;color:var(--fg)}
.filters input,.filters select,.filters button{background:var(--bg);border:1px solid var(--bd);border-radius:6px;
padding:5px 8px;min-width:0;width:100%}
.filters button{cursor:pointer;background:var(--bg2)}
.rcount{font-size:12px;color:var(--mut);margin:0 0 8px}
.rlist{list-style:none;margin:0;padding:0;border:1px solid var(--bd);border-radius:6px}
.repo{padding:12px 16px;border-top:1px solid var(--bd2)}.repo:first-child{border-top:0}
.rhead{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 10px}
.rname{background:none;border:0;padding:0;cursor:pointer;text-align:left;font-size:15px;font-weight:600;color:var(--ac);
overflow-wrap:anywhere}
.rname .owner{font-weight:400}.rname:hover{text-decoration:underline}
.rname::before{content:"";display:inline-block;width:0;height:0;margin:0 7px 2px 1px;border:4px solid transparent;
border-left:5px solid var(--mut);border-right:0;transition:transform .12s}
.rname[aria-expanded=true]::before{transform:rotate(90deg)}
.gh{font-size:12px;color:var(--mut)}
.stars{margin-left:auto;color:var(--mut);font-size:12px;white-space:nowrap}
.stars svg{vertical-align:-1px;margin-right:3px}
.tags{display:flex;flex-wrap:wrap;gap:4px 6px;margin-top:6px;align-items:center;font-size:12px}
.use{color:var(--mut)}
.summary{margin:6px 0 0;overflow-wrap:anywhere}
.idea{margin:3px 0 0;color:var(--mut);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;overflow-wrap:anywhere}
.repo.open .idea{display:none}
.rmeta{margin-top:6px;font-size:12px;color:var(--mut)}
.stale{color:var(--warn);font-weight:500}
.rbody{margin-top:12px;padding-top:12px;border-top:1px dashed var(--bd)}
.rbody .facts{margin-bottom:14px}
.uselist{list-style:none;margin:0;padding:0}.uselist li+li{margin-top:6px}
.uselist .note{color:var(--fg);overflow-wrap:anywhere}
@media (max-width:899px){
.qgrid{grid-template-columns:minmax(0,1fr)}
.qlist{position:static;max-height:none;overflow:visible}
body.qopen .qlist{display:none}body:not(.qopen) .qdetail{display:none}
.back{display:inline-block}
.filters{grid-template-columns:1fr 1fr}.filters input{grid-column:1/-1}
.filters input,.filters select,.filters button{font-size:16px}
.repo{padding:12px}
.md{font-size:15px}
}
"""

JS = r"""
(() => {
"use strict";
const D = JSON.parse(document.getElementById("data").textContent), U = D.ui, L = U.labels;
const $ = (s) => document.querySelector(s);
const STAR = '<svg width="12" height="12" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 1.6l1.95 3.95 4.36.63-3.15 3.08.74 4.34L8 11.55l-3.9 2.05.74-4.34L1.69 6.18l4.36-.63z" fill="none" stroke="currentColor" stroke-width="1.3" stroke-linejoin="round"/></svg>';

// Build DOM from text nodes. Only `html` (Markdown rendered and escaped by site.py, or STAR) is parsed.
function h(tag, attrs, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k === "html") n.innerHTML = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat(Infinity)) if (c != null && c !== false && c !== "") n.append(c instanceof Node ? c : String(c));
  return n;
}
const fmt = (s, o) => s.replace(/\{(\w+)\}/g, (m, k) => (k in o ? o[k] : m));
const lab = (g, v) => (L[g] && L[g][v]) || v || "";
const badge = (g, v) => (v ? h("span", {class: `badge ${g}-${v}`}, lab(g, v)) : null);
const web = (u) => (/^https?:\/\//i.test(u || "") ? u : null);
const kilo = (n) => (n >= 1000 ? (n / 1000).toFixed(n >= 10000 ? 0 : 1).replace(/\.0$/, "") + "k" : String(n));
const sep = (items, s) => items.flatMap((x, i) => (i ? [s, x] : [x]));
const fact = (dt, ...dd) => h("div", {style: "display:contents"}, h("dt", null, dt), h("dd", null, dd));
const questions = new Map(D.questions.map((q) => [q.ref, q]));
const cards = new Map(D.cards.map((c) => [c.id.toLowerCase(), c]));
const projects = [...new Set(D.cards.flatMap((c) => c.uses.map((u) => u.project)))];
const multi = new Set([...Object.keys(D.projects), ...projects]).size > 1;
const qname = (p, q) => (q ? (multi ? p + "/" + q : q) : p);

function repoLink(slug) {
  const c = cards.get(String(slug).toLowerCase());
  if (c) return h("a", {href: "#r=" + encodeURIComponent(c.id)}, c.id);
  return /^[\w.-]+\/[\w.-]+$/.test(slug)
    ? h("a", {href: "https://github.com/" + slug, target: "_blank", rel: "noopener noreferrer"}, slug) : String(slug);
}
function questionLink(p, q) {
  const ref = p + "/" + q;
  return questions.has(ref) ? h("a", {href: "#q=" + encodeURIComponent(ref)}, qname(p, q)) : qname(p, q);
}

// -- questions -------------------------------------------------------------
function questionList() {
  const nav = $("#qlist");
  if (!D.questions.length) return nav.append(h("p", {class: "empty"}, U.noQuestions));
  let group;
  for (const q of D.questions) {
    if (q.project !== group) nav.append(h("h2", {class: "group"}, D.projects[(group = q.project)] || group));
    nav.append(h("a", {class: "qitem", href: "#q=" + encodeURIComponent(q.ref), "data-ref": q.ref},
      h("span", {class: "qask"}, q.ask || q.id),
      h("span", {class: "qmeta"}, badge("status", q.status), " ", lab("stage", q.stage), " · ",
        fmt(U.lookedN, {n: q.looked.length}), q.scanned ? " · " + q.scanned : "")));
  }
}

function showQuestion(ref) {
  const q = questions.get(ref) || D.questions[0];
  document.body.classList.toggle("qopen", !!ref);
  const shown = ref || !matchMedia("(max-width: 899px)").matches ? q : null;  // narrow screens show the list alone
  for (const a of document.querySelectorAll(".qitem")) {
    if (shown && a.dataset.ref === shown.ref) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  const box = $("#qdetail");
  box.replaceChildren();
  if (!q) return;
  box.append(
    h("a", {class: "back", href: "#questions"}, "← " + U.back),
    h("div", {class: "crumbs"}, (D.projects[q.project] || q.project) + " / " + q.id),
    h("h2", {class: "qtitle"}, q.ask || q.ref),
    h("dl", {class: "facts"},
      fact(U.stage, badge("stage", q.stage), q.stageHelp ? " " + q.stageHelp : ""),
      fact(U.status, badge("status", q.status)),
      fact(U.picked, q.picked.length ? sep(q.picked.map(repoLink), ", ") : U.none),
      fact(U.looked, fmt(U.lookedN, {n: q.looked.length})),
      fact(U.lastScan, q.scanned || U.never, q.scans ? " · " + fmt(U.scansN, {n: q.scans}) : "")),
    h("section", {class: "answer"}, h("h3", {class: "label"}, U.answer),
      q.answer ? h("div", {class: "md", html: q.answer}) : h("p", {class: "empty"}, U.noAnswer)),
    q.context ? h("details", {class: "more"}, h("summary", null, U.context), h("div", {class: "md", html: q.context})) : null,
    q.looked.length ? h("details", {class: "more", open: !q.answer},
      h("summary", null, fmt(U.lookedList, {n: q.looked.length})),
      h("ul", {class: "looked"}, q.looked.map((r) => h("li", null,
        h("div", null, repoLink(r.repo), " ", badge(r.group, r.mark), r.date ? h("span", {class: "muted"}, " " + r.date) : null),
        r.note ? h("div", {class: "lnote"}, r.note) : null)))) : null);
  if (box.getBoundingClientRect().top < 0) window.scrollTo(0, 0);
}

// -- repos -----------------------------------------------------------------
const st = {text: "", kind: "", take: "", project: "", question: ""};
const rows = [];

function repoRow(c) {
  const [owner, name] = c.id.includes("/") ? c.id.split("/", 2) : ["", c.id];
  const btn = h("button", {type: "button", class: "rname", "aria-expanded": "false"},
    owner ? h("span", {class: "owner"}, owner + "/") : null, name);
  const body = h("div", {class: "rbody", hidden: true});
  const pushed = c.pushed ? [U.pushed + " ", h("span", {class: c.stale ? "stale" : null}, c.pushed,
    c.stale ? " (" + fmt(U.stale, {n: c.age}) + ")" : "")] : null;
  const li = h("li", {class: "repo"},
    h("div", {class: "rhead"}, btn,
      web(c.url) ? h("a", {class: "gh", href: c.url, target: "_blank", rel: "noopener noreferrer"}, U.github) : null,
      c.stars != null ? h("span", {class: "stars", title: c.stars + " " + U.stars, html: STAR}, kilo(c.stars)) : null),
    h("div", {class: "tags"}, c.kind ? h("span", {class: "badge kind"}, lab("kind", c.kind) + (c.form ? " · " + c.form : "")) : null,
      c.uses.map((u) => h("span", {class: "use"}, qname(u.project, u.question), " ", badge("take", u.take)))),
    c.summary ? h("p", {class: "summary"}, c.summary) : null,
    c.idea ? h("p", {class: "idea"}, c.idea) : null,
    h("div", {class: "rmeta"}, sep([c.created ? U.created + " " + c.created : null, pushed,
      c.reviewed ? U.reviewed + " " + c.reviewed : null].filter(Boolean), " · ")),
    body);
  const row = {c, li, btn, body, open: false, filled: false,
    text: [c.id, c.summary, c.idea, c.kind, lab("kind", c.kind), c.form,
      ...c.uses.flatMap((u) => [u.project, u.question, u.take, lab("take", u.take), u.where, u.note]),
      new DOMParser().parseFromString(c.body, "text/html").body.textContent].join(" ").toLowerCase()};
  btn.addEventListener("click", () => toggle(row, !row.open, true));
  return row;
}

function fill(row) {
  const c = row.c, link = web(c.url);
  row.body.append(
    h("dl", {class: "facts"},
      c.level ? fact(U.level, lab("level", c.level)) : null,
      c.commit ? fact(U.commit, link ? h("a", {href: link.replace(/\/+$/, "") + "/tree/" + c.commit, target: "_blank",
        rel: "noopener noreferrer"}, h("code", null, c.commit.slice(0, 7))) : c.commit.slice(0, 7), c.branch ? " (" + c.branch + ")" : "") : null,
      c.uses.length ? fact(U.uses, h("ul", {class: "uselist"}, c.uses.map((u) => h("li", null,
        questionLink(u.project, u.question), " ", badge("take", u.take), u.where ? h("span", {class: "muted"}, " · " + u.where) : null,
        u.note ? h("div", {class: "note"}, u.note) : null)))) : null,
      fact(U.file, h("code", null, c.file))),
    h("div", {class: "md", html: c.body}));
  row.filled = true;
}

function toggle(row, open, fromClick) {
  row.open = open;
  row.btn.setAttribute("aria-expanded", String(open));
  row.body.hidden = !open;
  row.li.classList.toggle("open", open);
  if (open && !row.filled) fill(row);
  if (fromClick) try { history.replaceState(null, "", open ? "#r=" + encodeURIComponent(row.c.id) : "#repos"); } catch (e) {}
}

function select(key, all, options) {
  const s = h("select", {"aria-label": all}, h("option", {value: ""}, all),
    options.map(([v, t]) => h("option", {value: v}, t)));
  s.addEventListener("change", () => { st[key] = s.value; if (key === "project") questionOptions(); applyFilters(); });
  return s;
}
let qSelect;
function questionOptions() {
  const refs = [...new Set(D.cards.flatMap((c) => c.uses.filter((u) => u.question && (!st.project || u.project === st.project))
    .map((u) => u.project + "/" + u.question)))].sort();
  if (!refs.includes(st.question)) st.question = "";
  qSelect.replaceChildren(h("option", {value: ""}, U.allQuestions),
    ...refs.map((r) => h("option", {value: r, selected: r === st.question}, multi ? r : r.split("/").slice(1).join("/"))));
}

function repoList() {
  const kinds = D.kinds.filter((k) => D.cards.some((c) => c.kind === k));
  const search = h("input", {type: "search", placeholder: U.search, "aria-label": U.search});
  search.addEventListener("input", () => { st.text = search.value.trim().toLowerCase(); applyFilters(); });
  qSelect = select("question", U.allQuestions, []);
  const controls = [search, select("kind", U.allKinds, kinds.map((k) => [k, lab("kind", k)])),
    select("take", U.allTakes, D.takes.map((t) => [t, lab("take", t)])),
    select("project", U.allProjects, projects.map((p) => [p, D.projects[p] || p])), qSelect];
  const clear = h("button", {type: "button"}, U.clear);
  clear.addEventListener("click", () => resetFilters(controls));
  $("#filters").append(...controls, clear);
  questionOptions();
  for (const c of D.cards) rows.push(repoRow(c));
  $("#rlist").append(...rows.map((r) => r.li));
  applyFilters();
}
function resetFilters(controls) {
  Object.keys(st).forEach((k) => (st[k] = ""));
  for (const el of controls || document.querySelectorAll("#filters input, #filters select")) el.value = "";
  questionOptions();
  applyFilters();
}

function applyFilters() {
  const words = st.text.split(/\s+/).filter(Boolean);
  let shown = 0;
  for (const r of rows) {
    const c = r.c;
    const ok = (!st.kind || c.kind === st.kind)
      && (!(st.take || st.project || st.question) || c.uses.some((u) => (!st.take || u.take === st.take)
        && (!st.project || u.project === st.project) && (!st.question || u.project + "/" + u.question === st.question)))
      && words.every((w) => r.text.includes(w));
    r.li.hidden = !ok;
    shown += ok;
  }
  $("#rcount").textContent = fmt(U.count, {n: shown, total: rows.length});
  $("#rlist").hidden = !shown;
  $("#rempty").hidden = !!shown;
}

function openRepo(id) {
  const row = rows.find((r) => r.c.id.toLowerCase() === id.toLowerCase());
  if (!row) return;
  if (row.li.hidden) resetFilters();
  toggle(row, true, false);
  row.li.scrollIntoView({block: "start"});
}

// -- routing: #questions, #q=<project/question>, #repos, #r=<owner/repo> ----
function route() {
  let hash = location.hash.slice(1);
  try { hash = decodeURIComponent(hash); } catch (e) {}
  const view = hash === "repos" || hash.startsWith("r=") ? "repos" : "questions";
  $("#v-questions").hidden = view !== "questions";
  $("#v-repos").hidden = view !== "repos";
  for (const a of document.querySelectorAll(".tabs a")) {
    if (a.dataset.view === view) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
  }
  if (view === "questions") showQuestion(hash.startsWith("q=") ? hash.slice(2) : null);
  else if (hash.startsWith("r=")) openRepo(hash.slice(2));
}

questionList();
repoList();
window.addEventListener("hashchange", route);
route();
})();
"""


def _json_for_html(data: dict) -> str:
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")


def page(data: dict) -> str:
    ui = data["ui"]
    overview = ui["overview"].format(**data["counts"])
    lang = "zh-CN" if data["lang"] == "zh" else "en"
    return "\n".join([
        "<!doctype html>",
        f'<html lang="{lang}">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta name="color-scheme" content="light dark">',
        f"<title>{_esc(data['name'])}</title>",
        f"<style>{CSS}</style>",
        "</head>",
        "<body>",
        '<header class="top"><div class="wrap">',
        f'<div class="brand"><h1>{_esc(data["name"])}</h1><span class="overview">{_esc(overview)}</span></div>',
        f'<nav class="tabs"><a href="#questions" data-view="questions">{_esc(ui["questions"])}</a>'
        f'<a href="#repos" data-view="repos">{_esc(ui["repos"])}</a></nav>',
        "</div></header>",
        '<main class="wrap">',
        f'<noscript><p>{_esc(ui["noscript"])}</p></noscript>',
        '<section id="v-questions"><div class="qgrid">',
        f'<nav id="qlist" class="qlist" aria-label="{_esc(ui["questions"])}"></nav>',
        '<article id="qdetail" class="qdetail"></article>',
        "</div></section>",
        '<section id="v-repos" hidden>',
        '<div id="filters" class="filters"></div>',
        '<p id="rcount" class="rcount"></p>',
        '<ul id="rlist" class="rlist"></ul>',
        f'<p id="rempty" class="empty" hidden>{_esc(ui["noRepos"])}</p>',
        "</section>",
        "</main>",
        f'<footer class="wrap">{_esc(ui["built"].format(date=data["built"]))}</footer>',
        f'<script type="application/json" id="data">{_json_for_html(data)}</script>',
        f"<script>{JS}</script>",
        "</body>",
        "</html>",
        "",
    ])


def build_site(store: Store, out: Path | None = None) -> Path:
    """Write the viewer (default <store>/site/index.html) and return its path."""
    out = Path(out).expanduser() if out else store.root / "site" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out = out.resolve()
    out.write_text(page(site_data(store, out.parent)), encoding="utf-8")
    return out
