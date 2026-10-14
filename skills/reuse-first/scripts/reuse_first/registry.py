"""Cards, needs and projects: creating them, relating repos to needs, finding, indexing."""

from __future__ import annotations

import re
from pathlib import Path

from .store import (
    FAMILY_TITLES, KINDS, NEED_ORDER, PROJECT_ORDER, RELATIONS, Doc, Store, StoreError, as_list, family,
    strongest, today, write_doc,
)

TEMPLATES = {
    "agent": """
# {id}

## What it teaches
(The method in two or three sentences: what an agent does differently with it.)

## What we take
(Concrete rules, steps, prompts or scripts, with file paths, and where they go in our setup.)

## What we leave, and why

## Safety
(Instructions or scripts that send data out, call the network, self-update or ask for broad
permissions. "None found in <files>" is an answer.)

## Read first
(Paths relative to the repository root.)
""",
    "software": """
# {id}

## What it is
(Who maintains it, what it does, how it is used: CLI, server, library, app.)

## What we use
(Commands, modules, adapters and versions; where it runs in our setup.)

## Fit and gaps
(Which parts of the need it covers, and what we would still have to build.)

## Risks
(Permissions, data it can reach, maintenance, license terms, lock-in.)

## Adoption
(How we install and pin it, the wrapper or plugin we write, and which of our own code it replaces.)

## Read first
(Paths relative to the repository root.)
""",
    "other": """
# {id}

## What it is

## What we take

## Read first
""",
}


def new_card(store: Store, meta: dict, kind: str, uses: list[dict], watch: list[str], level: str,
             summary: str | None = None) -> Doc:
    slug = meta["repo"]
    path = store.card_path(slug)
    if path.exists():
        raise StoreError(f"{slug} already has a card: {path} (use `relate` to add a use)")
    if kind not in KINDS:
        raise StoreError(f"kind must be one of {', '.join(KINDS)}")
    data = {
        "id": slug, "repo": f"https://github.com/{slug}", "kind": kind,
        "summary": summary or meta.get("desc") or "", "license": meta.get("license") or "none",
        "stars": meta.get("stars"), "pushed": meta.get("pushed") or None, "created": meta.get("created") or None,
        "branch": meta.get("branch"), "commit": meta.get("commit"), "reviewed": today(), "level": level,
        "watch": watch, "uses": uses,
    }
    data = {k: v for k, v in data.items() if v is not None}
    doc = Doc(path, data, TEMPLATES[family(kind)].format(id=slug))
    store.save_card(doc)
    return doc


def relate(store: Store, slug: str, use: dict) -> Doc:
    card = store.card(slug)
    if not card or card.error:
        raise StoreError(f"{slug}: no card (create one with `reuse-first card`)")
    if use.get("relation") not in RELATIONS:
        raise StoreError(f"relation must be one of {', '.join(RELATIONS)}")
    uses = [u for u in as_list(card.data.get("uses")) if isinstance(u, dict)]
    for u in uses:
        if u.get("project") == use.get("project") and (u.get("need") or None) == (use.get("need") or None):
            u.update({k: v for k, v in use.items() if v})
            break
    else:
        uses.append({k: v for k, v in use.items() if v})
    card.data["uses"] = uses
    store.save_card(card)
    return card


def new_project(store: Store, pid: str, name: str, summary: str) -> Path:
    path = store.root / "projects" / pid / "project.md"
    if path.exists():
        raise StoreError(f"project {pid} exists: {path}")
    data = {"id": pid, "name": name, "summary": summary, "where": "", "stack": [], "constraints": [],
            "languages": ["en"]}
    body = f"""
# {name}

(What this project is, who it serves, and what we would never adopt: licenses, platforms,
hosting, data handling. Agents read this before judging fit.)
"""
    write_doc(path, data, body, PROJECT_ORDER)
    return path


def new_need(store: Store, ref: str, want: str) -> Path:
    project, need = store.split_ref(ref)
    if not store.project(project):
        raise StoreError(f"no project {project} (reuse-first new-project {project} --name ...)")
    path = store.need_path(project, need)
    if path.exists():
        raise StoreError(f"need exists: {path}")
    data = {"id": need, "project": project, "want": want, "status": "open", "entities": [], "mechanisms": [],
            "forms": [], "problems": [], "topics": [], "chosen": [], "scanned": None}
    body = f"""
# {project}/{need}

{want}

## Landscape
(Compare the serious options side by side: what each covers, how mature, what it costs us.
`reuse-first show {project}/{need}` lists everything carded and triaged for this need.)

## Decision
(What we use for which part, what we adapt, and what we build because nothing covers it, with
the searches that prove it: `scans/{project}/{need}/`.)
"""
    write_doc(path, data, body, NEED_ORDER)
    return path


def card_line(c: Doc) -> str:
    d = c.data
    rels = [f"{u.get('project')}/{u.get('need') or '-'}:{u.get('relation')}" for u in as_list(d.get("uses")) if isinstance(u, dict)]
    return (f"{c.id} [{d.get('kind')}] {strongest([str(u.get('relation')) for u in as_list(d.get('uses')) if isinstance(u, dict)]) or 'unrelated'}"
            f" — {str(d.get('summary') or '')[:100]} ({', '.join(rels) or 'no uses'}; reviewed {d.get('reviewed')} @ {str(d.get('commit') or '')[:7]})")


def _text(doc: Doc) -> str:
    vals = []
    for v in doc.data.values():
        if isinstance(v, list):
            for x in v:
                vals.append(" ".join(map(str, x.values())) if isinstance(x, dict) else str(x))
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
    needs = sorted(((hits(_text(n)), n) for n in store.needs() if not n.error), key=lambda x: -x[0])
    seen: dict[str, dict] = {}
    for e in store.ledger():
        if "repo" not in e:
            continue
        text = " ".join(str(e.get(k, "")) for k in ("repo", "reason", "need", "project", "desc")).lower()
        h = hits(text)
        if h:
            prev = seen.get(e["repo"].lower())
            if not prev or (e.get("date") or "") >= (prev["entry"].get("date") or ""):
                seen[e["repo"].lower()] = {"hits": h, "entry": e}
    carded = {c.id.lower() for _, c in cards}
    ledger = sorted((v for k, v in seen.items() if k not in carded), key=lambda v: -v["hits"])
    top = max([h for h, _ in cards] + [h for h, _ in needs] + [v["hits"] for v in ledger] + [0])
    keep = lambda h: h > 0 and (h == top or h >= 2 or len(terms_l) == 1)  # noqa: E731
    return {
        "cards": [c for h, c in cards if keep(h)][:limit],
        "needs": [n for h, n in needs if keep(h)][:limit],
        "ledger": [v["entry"] for v in ledger if keep(v["hits"])][:limit],
    }


def render_find(res: dict) -> str:
    out = []
    if res["cards"]:
        out.append("cards:")
        out += [f"  {card_line(c)}" for c in res["cards"]]
    if res["needs"]:
        out.append("needs:")
        for n in res["needs"]:
            d = n.data
            out.append(f"  {d.get('project')}/{d.get('id')} [{d.get('status')}] {d.get('want')}"
                       f" (chosen: {', '.join(map(str, as_list(d.get('chosen')))) or '-'}; scanned {d.get('scanned') or 'never'})")
    if res["ledger"]:
        out.append("triaged, no card:")
        for e in res["ledger"]:
            out.append(f"  {e['repo']} {e.get('verdict')} for {e.get('project')}/{e.get('need')} on {e.get('date')}"
                       + (f": {e.get('reason')}" if e.get("reason") else ""))
    return "\n".join(out) or "nothing in the registry matches. Run a scan for the need (see the skill)."


def coverage(store: Store, project: str, need: str) -> dict:
    ref = f"{project}/{need}"
    cards = [c for c in store.cards() if not c.error and any(
        isinstance(u, dict) and u.get("project") == project and u.get("need") == need for u in as_list(c.data.get("uses")))]
    latest = {k: e for k, e in store.verdicts().items() if k[1] == ref}
    counts: dict[str, int] = {}
    for e in latest.values():
        counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1
    scans = store.scans(project, need)
    return {"cards": cards, "verdicts": counts, "open": [e for e in latest.values() if e["verdict"] in ("short", "peeked", "defer", "list")],
            "scans": [p.stem for p in scans]}


def show_need(store: Store, ref: str) -> str:
    doc = store.need(ref)
    d = doc.data
    project, need = d["project"], d["id"]
    cov = coverage(store, project, need)
    out = [f"{project}/{need} [{d.get('status')}] {d.get('want')}",
           f"file: {doc.path}",
           f"chosen: {', '.join(map(str, as_list(d.get('chosen')))) or '-'} · scanned {d.get('scanned') or 'never'}"
           f" · scans {len(cov['scans'])}" + (f" (latest {cov['scans'][-1]})" if cov["scans"] else ""),
           "vocabulary: " + " · ".join(f"{k}={as_list(d.get(k))}" for k in ("entities", "mechanisms", "forms", "problems", "topics") if as_list(d.get(k)))]
    out.append("triaged: " + (", ".join(f"{k} {v}" for k, v in sorted(cov["verdicts"].items())) or "nothing yet"))
    if cov["open"]:
        out.append("waiting for a decision: " + ", ".join(f"{e['repo']} ({e['verdict']})" for e in cov["open"]))
    if cov["cards"]:
        out.append("cards:")
        out += [f"  {card_line(c)}" for c in cov["cards"]]
    body = doc.body.strip()
    if body:
        out += ["", body]
    return "\n".join(out)


def show_card(store: Store, ref: str) -> str:
    card = store.card(ref)
    hist = store.history(card.id if card else ref)
    out = []
    if card:
        out.append(f"card: {card.path}")
        out.append(card.path.read_text(encoding="utf-8").strip())
        cached = store.cached(card.id)
        if cached:
            out.append("cached source: " + ", ".join(str(p) for p in cached))
    if hist:
        out.append("ledger:")
        out += [f"  {e.get('date')} {e.get('verdict')} ({e.get('level')}) {e.get('project')}/{e.get('need')}"
                + (f": {e.get('reason')}" if e.get("reason") else "") for e in hist]
    return "\n".join(out) or f"{ref}: never seen. Peek it: reuse-first peek {ref}"


def write_index(store: Store) -> Path:
    cards = [c for c in store.cards() if not c.error]
    lines = [f"# {store.settings.get('name') or 'Registry'} index", "",
             f"Generated by `reuse-first index` on {today()}. Do not edit; edit the cards and needs.", ""]
    lines += ["## Needs", "", "| need | status | chosen | cards | triaged | last scan | want |", "|---|---|---|---|---|---|---|"]
    for n in store.needs():
        if n.error:
            continue
        d = n.data
        cov = coverage(store, d["project"], d["id"])
        lines.append(f"| [{d['project']}/{d['id']}](projects/{d['project']}/needs/{d['id']}.md) | {d.get('status')} | "
                     f"{', '.join(map(str, as_list(d.get('chosen')))) or '-'} | {len(cov['cards'])} | "
                     f"{sum(cov['verdicts'].values())} | {cov['scans'][-1][:8] if cov['scans'] else '-'} | {_cell(d.get('want'))} |")
    for fam in ("agent", "software", "other"):
        group = [c for c in cards if family(c.data.get("kind")) == fam]
        if not group:
            continue
        lines += ["", f"## {FAMILY_TITLES[fam]}", "", "| repo | kind | status | uses | summary | stars | reviewed |",
                  "|---|---|---|---|---|---|---|"]
        for c in sorted(group, key=lambda c: (RELATIONS.index(strongest([str(u.get('relation')) for u in as_list(c.data.get('uses')) if isinstance(u, dict)]) or 'reject'), c.id.lower())):
            d = c.data
            uses = [u for u in as_list(d.get("uses")) if isinstance(u, dict)]
            lines.append(f"| [{c.id}](repos/{c.path.name}) | {d.get('kind')} | "
                         f"{strongest([str(u.get('relation')) for u in uses]) or '-'} | "
                         f"{', '.join(sorted({str(u.get('project')) + '/' + str(u.get('need') or '-') for u in uses}))} | "
                         f"{_cell(d.get('summary'))} | {d.get('stars', '')} | {d.get('reviewed')} |")
    led = store.ledger()
    repos = {str(e.get('repo', '')).lower() for e in led if e.get("repo")}
    lines += ["", "## Ledger", "", f"{len(led)} verdicts on {len(repos)} repositories in `ledger.jsonl`; "
              f"{len(cards)} have cards. `reuse-first find <words>` searches all of it.", ""]
    path = store.root / "INDEX.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _cell(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).replace("|", "/")[:120]
