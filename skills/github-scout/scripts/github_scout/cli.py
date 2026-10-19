"""Command line for github-scout. `github-scout <command> --help` for details."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

from . import __version__
from .discover import (
    DEFAULT_LENSES, LENS_NAMES, LENSES, RISE_SHOW, Scan, floor_of, is_farmed, is_open, is_stale, merged, plan, plan_warnings,
    relaxed_reason, render, rising, row, scan_row, slugs_in_text, visible, why_hidden,
)
from .examine import bump, diff, digest, fetch, outdated, peek, render_outdated, render_peek
from .github import Client, GitHubError, github_slug
from .handoff import VERDICT_OF_TAKE, brief, parse_directions, parse_report, parse_search_log, read_source, report_goal, words_from_log
from .registry import (
    add_results, add_watch, adoption_text, find, live_adoption, new_card, new_project, new_question, put_idea, put_trial,
    render_find, set_adoption, set_use, show_card, show_question, stage_help, write_index,
)
from .store import (
    KINDS, LEVELS, MODES, REFERENCE_TAKES, SHA, STAGES, TAKES, URL, Store, StoreError, as_list, best_tier, env, lang_gaps,
    locate, min_stars, parse_langs, question_langs, read_config, stars_of, today,
)

EPILOG = """stages (one skill each; github-scout runs 1 to 5, which never change the project):
  plan    find, ask, scan --plan       the goal, what good looks like, search directions
  search  scan, scan --add/--expand     every lens, merged and ranked; lures, farmed installs and repos under 50 stars left out
  triage  pick, look                    keep repos with results to look at and 50+ stars; decide how to read each
  dig     note --trial, look --source   try the top 2-3, then read the code of the one to follow
  brief   write the answer, brief       one backbone and what fills its gaps; the project is not changed
  adopt   adopt                         the coding agent brings it into the project; updates then watches it
  also: import (a report from a cloud chat), updates, show, site, check
star threshold: 50, or $GITHUB_SCOUT_MIN_STARS

store: --store DIR, else $GITHUB_SCOUT_STORE, else the config file, else the nearest
parent directory that contains github-scout.json, else ~/.github-scout (created by the first `ask`)."""


def _store(args, create_lang: str | None = None) -> Store:
    return Store(locate(args.store, create_lang))


def make_client(args, store: Store | None = None) -> Client:
    return Client(verbose=not args.quiet, stamp_dir=(store.root / "cache") if store else None)


def _slug(text: str) -> str:
    s = github_slug(text)
    if not s:
        raise StoreError(f"not a GitHub repository: {text} (owner/repo or a github.com URL)")
    return s


def _out(args, text: str, data=None):
    if getattr(args, "json", False) and data is not None:
        print(json.dumps(data, ensure_ascii=False, indent=1, default=str))
    else:
        print(text)


def _entry(args, repo: str, project: str, qid: str, verdict: str, level: str, reason: str | None = None,
           meta: dict | None = None, scan: str | None = None) -> dict:
    meta = meta or {}
    e = {"date": today(), "repo": repo, "project": project, "question": qid, "verdict": verdict, "level": level,
         "by": args.by or env("AGENT") or "agent"}
    if reason:
        e["reason"] = reason
    for k in ("stars", "pushed"):
        if meta.get(k) is not None:
            e[k] = meta[k]
    if meta.get("desc"):
        e["desc"] = str(meta["desc"])[:120]
    if scan:
        e["scan"] = scan
    return e


def _table_file(store: Store, project: str, qid: str) -> Path:
    return store.root / "cache" / "tables" / project / f"{qid}.json"


def _remember_table(store: Store, scan: dict, rows: list[dict], rise: list[dict], show_all: bool) -> None:
    """The rows a table numbered, so `pick` reads numbers against what was shown (in cache/, not committed)."""
    p = _table_file(store, scan["project"], scan["question"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"scan": scan.get("id"), "all": show_all, "rows": [c["repo"] for c in rows],
                             "rising": [c["repo"] for c in rise]}) + "\n", encoding="utf-8")


def _shown_table(store: Store, scan: dict) -> dict | None:
    """The table last printed for this question, if it was printed from the latest scans."""
    try:
        t = json.loads(_table_file(store, scan["project"], scan["question"]).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return t if isinstance(t, dict) and t.get("scan") == scan.get("id") else None


# ---------------------------------------------------------------------------
# commands


def cmd_import(args):
    text = read_source(args.file)
    goal, stage = report_goal(text)
    cjk = any("\u4e00" <= ch <= "\u9fff" for ch in text[:4000])
    store = _store(args, create_lang="zh" if cjk else "en")
    project, qid = store.split_ref(args.q)
    if not store.question_path(project, qid).is_file():
        if not store.project(project):
            repo = _git_root(Path.cwd())
            new_project(store, project, project, "", str(repo) if repo and _project_id(repo.name) == project else "")
        new_question(store, f"{project}/{qid}", goal or f"(imported from {Path(args.file).name})", stage or "idea")
        print(f"question {project}/{qid} created from the report (stage {stage or 'idea'}: check it, and fill in where we stand)")
    doc = store.question(f"{project}/{qid}")
    words = parse_directions(text)
    searches = parse_search_log(text)
    if not (words["entities"] or words["mechanisms"]) and searches:
        words["entities"] = words_from_log(searches)          # no directions table: the words it searched with
    if words["entities"] or words["mechanisms"]:
        fresh = {k: v for k, v in words.items() if v and not doc.data.get(k)}   # never overwrite a local plan
        if fresh:
            doc.data.update(fresh)
            store.save_question(doc)
            print("directions read into the question: " + ", ".join(f"{len(v)} {k}" for k, v in fresh.items()))
    q = doc.data
    slugs, rows = parse_report(text)
    if not slugs:
        raise StoreError(f"no github.com/<owner>/<repo> links in {args.file}")
    client = make_client(args, store)
    sc = Scan(store, client, q)
    n = sc.add_slugs(slugs, "W")
    missing, moved = [], []
    for s in slugs:
        if s.lower() in sc.cands or s.lower() in sc.dropped:
            continue
        now = client.repo(s)                      # the REST API follows renames and transfers
        if now and now.get("full_name", "").lower() != s.lower():
            moved.append(f"{s} -> {now['full_name']}")
            sc.add_slugs([now["full_name"]], "W")
            if s.lower() in rows:
                rows[now["full_name"].lower()] = {**rows.pop(s.lower()), "repo": now["full_name"]}
        else:
            missing.append(s)
    for key, r in rows.items():
        if key in sc.cands and r.get("reason"):
            sc.cands[key]["said"] = r["reason"]
    where = args.note or Path(args.file).name
    for s in searches:                            # what the report says it searched, kept for the next scan
        sc.log.append({"lens": "W", "kind": "cloud " + (s["lens"] or "search")[:20],
                       "query": " · ".join(x for x in (s["direction"], s["lang"], s["query"]) if x)[:200],
                       "hits": len(s["kept"]) if s["kept"] else s["looked"]})
    sc.log.append({"lens": "W", "kind": "import", "query": f"import {where}"[:200], "hits": n})
    scan = sc.finish("W")
    path = store.save_scan(scan)
    entries, low = [], []
    limit = min_stars()
    by = {c["repo"].lower(): c for c in merged(store, project, qid)["candidates"]}   # floors relaxed with every scan
    for key, r in rows.items():
        if r.get("take") and key in sc.cands:
            c = {**sc.cands[key], **by.get(key, {})}
            verdict = VERDICT_OF_TAKE[r["take"]]
            reason = f"{where}: {r['take']}" + (f": {r['reason']}" if r.get("reason") else "")
            stars = stars_of(c.get("stars"))
            relaxed = None
            if verdict == "short" and stars is not None and stars < floor_of(c, limit):   # no reference: kept for later
                verdict, reason = "later", f"under {floor_of(c, limit)} stars; {reason}"
                low.append(c["repo"])
            elif verdict == "short" and stars is not None and stars < limit:
                relaxed = relaxed_reason(c, limit)
            e = _entry(args, c["repo"], project, qid, verdict, "meta", reason[:300], c, scan["id"])
            entries.append({**e, "low_stars": relaxed} if relaxed else e)
    store.append_ledger(entries)
    print(f"{len(slugs)} repos linked; {n} exist on GitHub and were added ({path.relative_to(store.root).as_posix()}); "
          f"{len(sc.dropped)} dropped (no push in 12 months); {len(entries)} verdicts from the report's table; "
          f"{len(searches)} searches from its search log")
    if moved:
        print(f"moved ({len(moved)}), added under the new name: " + ", ".join(moved))
    if missing:
        print(f"not on GitHub ({len(missing)}), possibly invented by the report's author: " + ", ".join(missing))
    if low:
        print(f"under {limit} stars (or the relaxed floor), recorded as later, not shortlisted ({len(low)}): {', '.join(low)} "
              f"(pick <q> owner/repo --low-stars \"why\" to shortlist one anyway)")
    if q.get("entities") or q.get("mechanisms"):
        print(f"next: github-scout scan {project}/{qid}   (GitHub's API on the same directions, no model needed; "
              f"rows without W are repos the report did not list)")
    else:
        print(f"next: github-scout scan {project}/{qid} --show   (they rank high: someone pointed at them)")


def cmd_brief(args):
    path = brief(_store(args), args.ref, Path(args.out).expanduser() if args.out else None)
    print(f"{path}\nhand this file to the coding agent, which adopts it with the github-scout-adopt skill; "
          "nothing in the project was changed")


def cmd_init(args):
    store = Store.init(Path(args.dir), args.name, args.lang)
    print(f"registry created: {store.root}\nnext: export GITHUB_SCOUT_STORE={store.root}  (or put it in the config file)\n"
          f"      github-scout new-project <id> --name \"...\" --code <path to its code>")


def cmd_new_project(args):
    print(new_project(_store(args), args.id, args.name, args.summary or "", args.code or ""))


def _project_id(name: str) -> str:
    """A project id from a folder name: "My App" -> my-app; scratch when nothing usable is left."""
    s = re.sub(r"[^a-z0-9._-]", "", re.sub(r"\s+", "-", name.strip().lower())).lstrip("._-")
    return s or "scratch"


def _git_root(path: Path) -> Path | None:
    for p in [path, *path.parents]:
        if (p / ".git").exists():
            return p
    return None


def cmd_ask(args):
    cjk = any("\u4e00" <= ch <= "\u9fff" for ch in args.question)
    store = _store(args, create_lang="zh" if cjk else "en")
    if "/" not in args.ref and not (store.settings.get("default_project") or read_config().get("GITHUB_SCOUT_PROJECT")):
        args.ref = f"{_project_id(_git_root(Path.cwd()).name) if _git_root(Path.cwd()) else 'scratch'}/{args.ref}"
    project, qid = store.split_ref(args.ref)
    if not args.update and not store.project(project):
        repo = _git_root(Path.cwd().resolve())
        code = args.code or (str(repo) if repo and _project_id(repo.name) == project else "")
        new_project(store, project, project, "", code)
        print(f"project {project} created" + (f" (code: {code})" if code else
              " (no code path: pass --code <path> to compare answers with your own code)"))
    langs = parse_langs(args.langs) if args.langs else None
    if args.update:
        doc = store.question(args.ref)
        doc.data["ask"] = args.question
        doc.data["stage"] = args.stage
        if langs:
            doc.data["langs"] = langs
        store.save_question(doc)
        print(f"{doc.path}: {'ask, stage and langs' if langs else 'ask and stage'} updated "
              "(edit the body's stage line by hand if it differs)")
        for w in lang_gaps(doc.data):
            print(f"warn  {w}")
        return
    path = new_question(store, args.ref, args.question, args.stage, langs)
    langs = question_langs(store.question(args.ref).data)
    print(f"{path}\n"
          f"stage {args.stage}: {stage_help(store, args.stage)}\n"
          "before searching, edit the file:\n"
          "  1. Where we are: what we already have (paths) and what is not good enough.\n"
          "  2. What good looks like: 2-3 finished results to match (links), or checks anyone can run on an output.\n"
          "  3. Vocabulary: entities (platforms, formats, products) and mechanisms (how a solution would work,\n"
          f"     in README words), each group with a term in every language of langs ({', '.join(langs)}), synonyms\n"
          "     with |, in the words those users write, not translations: \"xiaohongshu|小红书|xhs|红书\".\n"
          "     Then forms, and 2-4 short problem phrases, one per language.\n"
          f"then: github-scout scan {args.ref} --plan  (show the directions to the user before the full scan)")


def cmd_find(args):
    res = find(_store(args), args.words, args.limit)
    _out(args, render_find(res), {"cards": [c.data for c in res["cards"]],
                                  "questions": [q.data for q in res["questions"]], "ledger": res["ledger"]})


def _read_source(src: str) -> str:
    if src == "-":
        return sys.stdin.read()
    if src.startswith(("http://", "https://")) and not github_slug(src):
        req = urllib.request.Request(src, headers={"User-Agent": f"github-scout/{__version__}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    p = Path(src)
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else src


def cmd_scan(args):
    store = _store(args)
    doc = store.question(args.ref)
    q = doc.data
    ref = f"{q['project']}/{q['id']}"
    earlier = [s for p in store.scans(q["project"], q["id"]) for s in json.loads(p.read_text(encoding="utf-8"))["searches"]]
    gaps = [f"warn  {w}" for w in lang_gaps(q) + plan_warnings(q, earlier)]
    if args.plan:
        rows = plan(q, args.lenses)
        for r in rows:
            print(f"{r['lens']} {LENS_NAMES[r['lens']]:<12} {r['query']}")
        print("\n".join(gaps + [f"{len(rows)} searches. Run them: github-scout scan {ref}"]))
        return
    if not args.show:
        if gaps and not (args.add or args.expand):
            print("\n".join(gaps), file=sys.stderr)
        client = make_client(args, store)
        sc = Scan(store, client, q, progress=not args.quiet)
        if args.add or args.expand:
            if args.add:
                slugs = slugs_in_text("\n".join(_read_source(s) for s in args.add))
                if not slugs:
                    raise StoreError("no github.com/<owner>/<repo> links found in --add")
                n = sc.add_slugs(slugs, "W")
                sc.log.append({"lens": "W", "kind": "add", "query": (args.note or ", ".join(args.add))[:200], "hits": n})
            for lst in args.expand or []:
                slug = _slug(lst)
                links = [s for s in slugs_in_text(client.readme(slug) or "") if s.lower() != slug.lower()]
                n = sc.add_slugs(links[:400], "L", filter_vocab=not args.all)
                sc.log.append({"lens": "L", "kind": "list", "query": f"expand {slug}", "hits": n})
            scan = sc.finish("WL")
        else:
            scan = sc.run(args.lenses, args.budget, args.per_query)
            q["scanned"] = today()
            store.save_question(doc)
        path = store.save_scan(scan)
        print(f"saved {path.relative_to(store.root).as_posix()} · {client.calls} API calls", file=sys.stderr)
    table = merged(store, q["project"], q["id"])
    if (args.add or args.expand) and not args.show and not args.json:
        rows, rise = visible(table), rising(table)
        _remember_table(store, table, rows, rise, False)
        index = {c["repo"].lower(): i for i, c in enumerate(rows, 1)}
        index.update({c["repo"].lower(): f"h{i}." for i, c in enumerate(rise, 1)})
        added = [c["repo"] for c in scan["candidates"]]
        print(f"added {len(added)} repos ({scan.get('dropped', 0)} dropped: no push in 12 months). Where they rank now:")
        by = {c["repo"].lower(): c for c in table["candidates"]}
        limit = min_stars()
        for slug in added:
            c = by.get(slug.lower())
            if c is None:
                continue
            i = index.get(slug.lower())
            print(row(i, c) if i else f"  -  {slug}  ({why_hidden(c, limit)})")
        print(f"full table: github-scout scan {ref} --show")
        return
    if not args.json:
        _remember_table(store, table, visible(table, args.all), rising(table, args.all), args.all)
    _out(args, render(table, args.top, args.all)
         + f"\nnext: github-scout pick {ref} <#>... --rest \"<why the rest do not help>\" "
           f"(numbers refer to this table)", table)


def cmd_pick(args):
    store = _store(args)
    project, qid = store.split_ref(args.ref)
    scan = merged(store, project, qid)
    rows = visible(scan)
    rise = rising(scan)
    by_repo = {c["repo"].lower(): c for c in scan["candidates"]}
    # Numbers refer to the table last shown (with --all it numbers hidden rows too); --rest covers the open rows.
    shown = _shown_table(store, scan)
    numbered = [by_repo.get(r.lower(), {"repo": r}) for r in shown["rows"]] if shown else rows
    numbered_rise = [by_repo.get(r.lower(), {"repo": r}) for r in shown["rising"]] if shown else rise
    table = f"scan {args.ref} --show" + (" --all" if shown and shown.get("all") else "")

    def resolve(item: str) -> tuple[dict, str | None]:
        ref, _, reason = item.partition("=")
        ref = ref.strip()
        if ref.isdigit():
            i = int(ref)
            if not 1 <= i <= len(numbered):
                raise StoreError(f"#{i} is not in the last table (1-{len(numbered)}, `github-scout {table}`)")
            return numbered[i - 1], reason or None
        if ref[:1].lower() == "h" and ref[1:].isdigit():
            i = int(ref[1:])
            if not 1 <= i <= len(numbered_rise):
                raise StoreError(f"h{i} is not in the last rising list (h1-h{len(numbered_rise)}, `github-scout {table}`)")
            return numbered_rise[i - 1], reason or None
        slug = _slug(ref)
        return by_repo.get(slug.lower(), {"repo": slug}), reason or None

    entries, decided, low, unknown = [], set(), [], []
    limit = min_stars()
    for verdict, items in (("short", args.items), ("list", args.list), ("later", args.later), ("skip", args.skip)):
        for item in items or []:
            c, reason = resolve(item)
            decided.add(c["repo"].lower())
            e = _entry(args, c["repo"], project, qid, verdict, "meta", reason or (args.why if verdict == "skip" else None),
                       c, scan.get("id"))
            stars = stars_of(c.get("stars"))
            if verdict == "short" and stars is None:
                unknown.append(c["repo"])
            elif verdict == "short" and stars < limit:            # no reference without a reason: written, or the
                if args.low_stars or stars >= floor_of(c, limit):  # relaxed floor of its direction
                    e["low_stars"] = args.low_stars or relaxed_reason(c, limit)
                else:
                    low.append(f"{c['repo']} ({stars})")
            entries.append(e)
    if low:
        raise StoreError(f"under {limit} stars (or the relaxed floor of their direction), no references: {', '.join(low)}. "
                         f"Shortlist one only with --low-stars \"<why it is an exception>\" (an official organisation's "
                         "new repo, say); otherwise --later or --skip it")
    if args.rest:
        lists = [c for c in scan["candidates"] if c.get("list") and is_open(c) and not is_stale(c)][:8]
        for c in rows[: args.top] + lists + rise[:RISE_SHOW]:
            if c["repo"].lower() not in decided:
                entries.append(_entry(args, c["repo"], project, qid, "skip", "meta", args.rest, c, scan.get("id")))
    store.append_ledger(entries)
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1
    print("recorded: " + (", ".join(f"{k} {v}" for k, v in counts.items()) or "nothing"))
    for verdict in ("short", "list", "later"):
        names = [e["repo"] for e in entries if e["verdict"] == verdict]
        if names:
            print(f"  {verdict}: " + ", ".join(names))
    explicit = [e["repo"] for e in entries if e["verdict"] == "skip" and e.get("reason") != args.rest]
    if explicit:
        print("  skip: " + ", ".join(explicit))
    if unknown:
        print(f"warn  stars unknown (not in a scan): {', '.join(unknown)}. A reference needs {limit}+ stars: "
              "check before you read it")
    short = [e["repo"] for e in entries if e["verdict"] == "short"]
    if short:
        print(f"next: github-scout look --q {project}/{qid} " + " ".join(short))
    for e in entries:
        if e["verdict"] == "list":
            print(f"next: github-scout scan {project}/{qid} --expand {e['repo']}")


def cmd_look(args):
    store = _store(args)
    client = make_client(args, store)
    texts, results, entries = [], [], []
    for r in args.repos:
        card = store.card(r)
        slug = card.id if card else _slug(r)
        row = scan_row(store, *store.split_ref(args.q), slug) if args.q else {}   # its relaxed floor, its installs
        try:
            p = peek(client, slug, min(args.readme, 600) if args.source else args.readme,
                     installs=0 if is_farmed(row) else int(row.get("installs") or 0))
        except (LookupError, GitHubError) as exc:
            texts.append(f"## {r}: {exc}")
            continue
        p.update({k: row[k] for k in ("floor", "relaxed") if row.get(k)})
        results.append(p)
        text = render_peek(p)
        if card:
            text = f"(already carded: {card.path})\n" + text
        if args.source:
            path = fetch(store, client, p["repo"], args.ref)
            text += "\n\nsource:\n" + digest(path)
            if args.pack:
                text += "\n" + pack(path, args.include)
        texts.append(text)
        if args.q:
            project, qid = store.split_ref(args.q)
            entries.append(_entry(args, p["repo"], project, qid, "peeked", "read" if args.source else "look", None, p))
    store.append_ledger(entries)
    _out(args, "\n\n".join(texts) + ("\n\nnext: open its verifiable effect, then github-scout note <repo> --q <question> "
                                     "--take use|adapt|learn|later|skip --results <links> --note \"...\"" if results else ""),
         results)


def pack(path: Path, include: list[str] | None) -> str:
    """Compress fetched source with repomix (Tree-sitter signatures), if it is installed."""
    import shutil
    import subprocess

    tool = shutil.which("repomix")
    if not tool:
        return "--pack needs repomix on PATH (https://github.com/yamadashy/repomix); nothing packed."
    out = path.with_name(path.name + ".repomix.txt")
    cmd = [tool, str(path), "--compress", "--style", "plain", "--output", str(out)]
    if include:
        cmd += ["--include", ",".join(include)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        return f"repomix failed ({r.returncode}): {(r.stderr or r.stdout).strip()[-400:]}"
    total = next((ln.strip() for ln in r.stdout.splitlines() if "Total Tokens" in ln), "")
    return f"packed: {out}" + (f" ({total})" if total else "")


def _gate(args, slug: str, stars, results: list, carded: bool = False, row: dict | None = None) -> str | None:
    """use, adapt and learn make a repo a reference: it needs a verifiable effect (a mid or strong item) and enough
    stars, or a written reason for each (owner, 2026-10-18 and 10-19). Enough stars is the threshold, or the relaxed
    floor of its direction in the question's scans (`row`). Refused before anything is written. Returns the reason
    the repo counts under the threshold, for the take and the ledger."""
    if args.take not in REFERENCE_TAKES:
        return args.low_stars
    row = row or {}
    limit, stars, problems = min_stars(), stars_of(stars), []
    floor = floor_of(row, limit)
    low = args.low_stars
    if stars is None:
        print(f"warn  {slug}: stars unknown. A reference needs {limit}+")
    elif stars < limit and not low:
        if stars >= floor:
            low = relaxed_reason(row, limit)
        else:
            problems.append(f"{slug} has {stars} stars" + (" on its card (updates --done refreshes the count)" if carded else "")
                            + f", under {floor}{' (relaxed for its direction)' if floor < limit else ''}: no reference. Say "
                            "why it is an exception with --low-stars \"<why>\" (an official organisation's new repo, say), "
                            "or note it as later or skip")
    installs = 0 if is_farmed(row) else int(row.get("installs") or 0)
    if best_tier(results, slug, installs) == "weak" and not args.no_results:
        problems.append(f"{slug} shows {'only text in its own repo' if results else 'no verifiable effect on its card'}. "
                        "Give --results <links to what it does, seen outside its README text: a live site, a package or "
                        "store page, screenshots, GIFs or videos, posts on X, Bilibili, YouTube, blogs or Xiaohongshu>, "
                        "or --no-results \"<why it still counts>\"; with only a text description it is later or skip")
    if problems:
        raise StoreError("\n".join(problems))
    return low


def _links(items: list[str] | None) -> list[str]:
    bad = [x for x in items or [] if not URL.match(x)]
    if bad:
        raise StoreError(f"--results takes links (http or https) to its verifiable effect: {', '.join(bad)}")
    return list(dict.fromkeys(items or []))


def cmd_note(args):
    store = _store(args)
    project, qid = store.split_ref(args.q)
    results = _links(args.results)
    level = args.level or ("trial" if args.trial else None)
    card = store.card(args.repo)
    row = scan_row(store, project, qid, card.id if card else _slug(args.repo))

    def take(low: str | None) -> tuple[dict, dict]:
        use = {"project": project, "question": qid, "take": args.take, "where": args.where, "note": args.note,
               "low_stars": low, "no_results": args.no_results}
        return use, {k: v for k, v in (("low_stars", low), ("no_results", args.no_results)) if v}

    if card:
        low = _gate(args, card.id, card.data.get("stars"), [*map(str, as_list(card.data.get("results"))), *results], True,
                    row)
        use, extra = take(low)
        set_use(store, card.id, use, level)
        if results:
            add_results(store, card.id, results)
        if args.idea:
            put_idea(store, card.id, args.idea, f"{project}/{qid}")
        if args.trial:
            put_trial(store, card.id, args.trial, f"{project}/{qid}")
        if args.watch:
            add_watch(store, card.id, args.watch)
        if args.summary:
            fresh = store.card(card.id)
            fresh.data["summary"] = args.summary
            store.save_card(fresh)
        store.append_ledger([{**_entry(args, card.id, project, qid, "card", level or "read",
                                       f"{args.take}: {args.note or ''}"), **extra}])
        print(f"{card.path}: {project}/{qid} -> {args.take}")
        return
    slug = _slug(args.repo)
    if args.take == "skip" and not args.card:
        reason = "; ".join(x for x in (args.note, f"trial: {args.trial}" if args.trial else None) if x)
        store.append_ledger([_entry(args, slug, project, qid, "skip", level or "look", reason or None)])
        print(f"recorded skip for {slug} under {project}/{qid} (no card; --card makes one)")
        return
    client = make_client(args, store)
    meta = peek(client, slug, 0, effect=False)
    low = _gate(args, meta["repo"], meta.get("stars"), results, row=row or scan_row(store, project, qid, meta["repo"]))
    use, extra = take(low)
    kind = args.kind or meta["kind"]
    doc = new_card(store, meta, kind, meta["form"], [{k: v for k, v in use.items() if v}], args.watch or [],
                   level or "read", args.summary, args.idea, results)
    if args.idea:
        put_idea(store, doc.id, args.idea)
    if args.trial:
        put_trial(store, doc.id, args.trial, f"{project}/{qid}")
    store.append_ledger([{**_entry(args, meta["repo"], project, qid, "card", level or "read",
                                   f"{args.take}: {args.note or ''}", meta), **extra}])
    print(f"{doc.path}\nkind {kind} ({meta['form']}; {'; '.join(meta['evidence'])})\n"
          "fill the card (the idea, then its verifiable effect and any trial), list upstream paths we depend on under "
          "watch:, then write the report in the question file and run github-scout check")


def _paths(text: str | None) -> list[str]:
    return [p.strip() for p in (text or "").split(",") if p.strip()]


def _code_dir(store: Store, project: str) -> Path | None:
    """The project's code directory from its profile, when that is a local folder."""
    doc = store.project(project)
    code = str((doc.data.get("code") if doc else None) or "")
    path = Path(code).expanduser() if code and "://" not in code else None
    return path.resolve() if path and path.is_dir() else None


def _head(repo: Path) -> str:
    """The short sha of HEAD in a git repository; empty without git or without commits."""
    import subprocess

    try:
        r = subprocess.run(["git", "-C", str(repo), "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                           timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def _check_from(args, store: Store, slug: str, src: list[str], at: str) -> None:
    """Their paths must exist at their commit: GitHub lists no commits for a path that is not there, so a typo would
    read as unchanged for good. Refused when GitHub says no; a warning when it cannot be asked."""
    if not src:
        return
    client = make_client(args, store)
    try:
        full = client.commit(slug, at)
        gone = [p for p in src if not client.exists(slug, p, full["sha"])] if full else None
    except GitHubError as exc:
        if exc.status != 422:
            print(f"warn  --from not checked upstream ({exc})")
            return
        full = gone = None
    except OSError as exc:
        print(f"warn  --from not checked upstream (network: {exc})")
        return
    if full is None:
        raise StoreError(f"{slug} has no commit {at}: give --at their commit sha")
    if gone:
        raise StoreError(f"not in {slug} at {at[:7]}: {', '.join(gone)}. --from takes their files or folders, "
                         "from the root of their repository")


def cmd_adopt(args):
    store = _store(args)
    project, qid = store.split_ref(args.q)
    ref = f"{project}/{qid}"
    store.question(ref)                                       # refuses a question that does not exist
    card = store.card(args.repo)
    if card and card.error:
        raise StoreError(f"{card.path}: {card.error}")
    if not card:
        slug = github_slug(args.repo) or args.repo
        raise StoreError(f"{slug} has no card. Look at it and note what we take first: github-scout look --q {ref} {slug}, "
                         f"then github-scout note {slug} --q {ref} --take use|adapt|learn --note \"...\"")
    if not args.drop and not args.mode:
        raise StoreError(f"--mode is required: {', '.join(MODES)}")
    into = _paths(args.into)
    if not into:
        raise StoreError("--into takes our paths, comma-separated")
    src = [(p[2:] if p.startswith("./") else p).strip("/") for p in _paths(args.from_)]
    if any(ch in p for p in src for ch in "*?["):
        raise StoreError("--from takes their files or folders, not globs: GitHub's history is asked for one path at a time")
    # Relative paths are read from here inside the project, else from the project's code path; they are
    # stored from the root of the git repository that holds them (a worktree counts as its own root).
    root = _code_dir(store, project)
    cwd = Path.cwd().resolve()
    base = cwd if root is None or cwd == root or root in cwd.parents else root
    full = [(Path(p).expanduser() if Path(p).expanduser().is_absolute() else base / p).resolve() for p in into]
    repo = _git_root(full[0])
    top = repo or root or base
    rel = []
    for p in full:
        try:
            rel.append(p.relative_to(top).as_posix())
        except ValueError:
            raise StoreError(f"{p} is outside the project ({top})") from None
    if args.drop:
        entry = {"project": project, "question": qid, "into": rel, "note": args.note}
    else:
        for p, r in zip(full, rel):
            if not p.exists():
                print(f"warn  {r}: not found in {top} (relative paths are read from {base})")
        # Recorded again (after updating our copy): --from, --at and --note left out keep what was recorded.
        old = live_adoption(card.data, {"project": project, "question": qid, "into": rel}) or {}
        at = (args.at or str(old.get("at") or card.data.get("commit") or "")).lower()
        if not SHA.match(at):
            raise StoreError(f"--at takes their commit sha, 7-40 hex characters (the card's commit is "
                             f"{card.data.get('commit')!r})")
        ours = (args.ours or (_head(repo) if repo else "")).lower()
        if ours and not SHA.match(ours):
            raise StoreError("--ours takes our commit sha, 7-40 hex characters")
        _check_from(args, store, card.id, src or [str(p) for p in as_list(old.get("from"))], at)
        entry = {"project": project, "question": qid, "mode": args.mode, "into": rel, "from": src, "at": at,
                 "ours": ours, "date": today(), "note": args.note}
    a = set_adoption(store, card.id, entry, args.drop)
    verb = "dropped adoption" if args.drop else "adopted"
    store.append_ledger([_entry(args, card.id, project, qid, "card", str(card.data.get("level") or "read"),
                                f"{verb}: {adoption_text(a, short=True)}"[:300])])
    print(f"{card.path}: {card.id} {verb} under {ref}: {adoption_text(a, short=True)}")
    if args.drop:
        print("kept on the card as history; updates no longer reports it")
    elif a.get("from"):
        print(f"next: github-scout updates {card.id}   (reports the upstream commits that touch {', '.join(a['from'])})")
    else:
        print(f"next: github-scout updates {card.id}   (the whole repo only; --from <their files> narrows it to what we took)")


def cmd_show(args):
    store = _store(args)
    ref = args.ref
    if ref.count("/") == 1 and store.question_path(*ref.split("/")).is_file():
        print(show_question(store, ref))
    else:
        print(show_card(store, ref))


def cmd_updates(args):
    store = _store(args)
    client = make_client(args, store)
    if args.diff:
        print(diff(store, client, args.diff, args.all_files, args.max_lines))
        return
    if args.done:
        r = bump(store, client, args.done, args.to)
        print(f"{r['repo']}: {r['from']} -> {r['to']} (reviewed today)")
        return
    rows = outdated(store, client, args.repos or None, args.project)
    hint = "\nnext: github-scout updates --diff <repo>, update the card, then --done <repo>"
    if any(p.get("changes") for r in rows for a in r.get("adopted", []) for p in a.get("paths", [])):
        hint += ("\n      files we took changed: update our copy, then record it again with github-scout adopt <repo> "
                 "--q <p/q> --mode <mode> --into <the same paths> --at <their new commit>")
    _out(args, render_outdated(rows) + hint, rows)


def cmd_site(args):
    from .site import build_site

    store = _store(args)
    print(build_site(store, Path(args.out) if args.out else None))


def cmd_check(args):
    store = _store(args)
    errors, warns = store.check()
    for w in warns:
        print(f"warn  {w}")
    for e in errors:
        print(f"error {e}")
    if not errors:
        write_index(store)
    print(f"{len(errors)} error(s), {len(warns)} warning(s)" + ("" if errors else "; INDEX.md updated"))
    return 1 if errors else 0


# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="github-scout", description="Ask a question, find what open source already "
                                 "answers it, take the ideas and parts that fit, and remember every verdict.",
                                 epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"github-scout {__version__}")
    ap.add_argument("--store", dest="global_store", metavar="DIR", help="registry directory (also accepted after the command)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--store", help="registry directory")
    common.add_argument("--quiet", action="store_true", help="no progress on stderr")
    common.add_argument("--by", help="who records verdicts (default: $GITHUB_SCOUT_AGENT or 'agent')")
    js = argparse.ArgumentParser(add_help=False)
    js.add_argument("--json", action="store_true", help="machine-readable output")
    sub = ap.add_subparsers(dest="cmd", metavar="<command>")

    def add(name, fn, help_, parents=(common,)):
        p = sub.add_parser(name, help=help_, description=help_, parents=list(parents))
        p.set_defaults(fn=fn)
        return p

    p = add("init", cmd_init, "create a registry directory")
    p.add_argument("dir")
    p.add_argument("--name")
    p.add_argument("--lang", default="en", choices=["en", "zh"], help="language of the templates (default en)")

    p = add("new-project", cmd_new_project, "add a project profile")
    p.add_argument("id")
    p.add_argument("--name", required=True)
    p.add_argument("--summary")
    p.add_argument("--code", help="where the project's code is (path or URL)")

    p = add("ask", cmd_ask, "start a question: what we want, where we stand, and its search vocabulary")
    p.add_argument("ref", help="<project>/<question-id>, or <question-id> alone: the project is then named after the "
                   "git repository you are in (its code path recorded), or 'scratch' outside one")
    p.add_argument("question", help="one sentence: the result we want, not the tool we imagine")
    p.add_argument("--code", help="where the project's code is, when ask creates the project")
    p.add_argument("--stage", required=True, choices=STAGES, help="where our own work stands")
    p.add_argument("--update", action="store_true", help="change the ask and stage (and --langs) of an existing question")
    p.add_argument("--langs", metavar="CODES", help="languages every vocabulary group should cover, comma-separated "
                   "from en, zh, ja, ko (default en,zh)")

    p = add("find", cmd_find, "search questions, cards and the ledger: has anyone looked at this?", (common, js))
    p.add_argument("words", nargs="+")
    p.add_argument("--limit", type=int, default=20)

    lens_help = f"lens letters from {LENSES} (default {DEFAULT_LENSES}); see --plan"
    p = add("scan", cmd_scan, "search for a question and print ranked candidates (all scans merged)", (common, js))
    p.add_argument("ref")
    p.add_argument("--plan", action="store_true", help="print the searches without running them")
    p.add_argument("--show", action="store_true", help="print saved results again, no network")
    p.add_argument("--add", nargs="+", metavar="SRC", help="add repos found elsewhere: files, URLs, '-' or text")
    p.add_argument("--note", help="with --add: where the links came from")
    p.add_argument("--expand", nargs="+", metavar="LIST", help="add the repos an awesome list links to")
    p.add_argument("--lenses", default=DEFAULT_LENSES, help=lens_help)
    p.add_argument("--budget", type=int, default=250, help="max API calls (default 250)")
    p.add_argument("--per-query", type=int, default=30)
    p.add_argument("--top", type=int, default=40)
    p.add_argument("--all", action="store_true", help="also show decided and stale rows; with --expand keep every link")

    p = add("pick", cmd_pick, "record verdicts on scan rows: numbers from the table, or owner/repo")
    p.add_argument("ref")
    p.add_argument("items", nargs="*", metavar="ITEM", help="worth a look: a verifiable effect and 50+ stars, or the "
                   "relaxed floor of its direction (the scan header names them)")
    p.add_argument("--low-stars", metavar="REASON", help="shortlist items under the star floor anyway, with this "
                   "reason (an official organisation's new repo, say); it goes into the ledger")
    p.add_argument("--list", nargs="+", metavar="ITEM", help="awesome lists to expand (no star threshold)")
    p.add_argument("--later", nargs="+", metavar="ITEM", help="maybe later")
    p.add_argument("--skip", nargs="+", metavar="ITEM[=reason]", help="no help for this question")
    p.add_argument("--why", help="reason for --skip items without their own")
    p.add_argument("--rest", metavar="REASON", help="skip every other row shown, with this reason")
    p.add_argument("--top", type=int, default=40, help="rows --rest covers (default 40)")

    p = add("look", cmd_look, "look at repos: facts, activity, kind, verifiable effect (strong, mid or weak), tree, "
            "README start; --source reads the code", (common, js))
    p.add_argument("repos", nargs="+")
    p.add_argument("--q", help="<project>/<question>: record that we looked; its scans give relaxed floors and installs")
    p.add_argument("--readme", type=int, default=2500, help="README characters (default 2500)")
    p.add_argument("--source", action="store_true", help="download the source and print where the code is")
    p.add_argument("--ref", help="with --source: commit, tag or branch (default: card commit or default branch)")
    p.add_argument("--pack", action="store_true", help="with --source: also write a repomix digest if installed")
    p.add_argument("--include", nargs="+", metavar="GLOB", help="with --pack: only these paths")

    p = add("note", cmd_note, "record what we take from a repo; creates or updates its card. use, adapt and learn need "
            "a verifiable effect (mid or strong) and 50+ stars (or the relaxed floor of its direction), or a written reason")
    p.add_argument("repo")
    p.add_argument("--q", required=True, help="<project>/<question>")
    p.add_argument("--take", required=True, choices=TAKES)
    p.add_argument("--results", nargs="+", metavar="URL", help="links to its verifiable effect: a live site, a package or "
                   "store page, screenshots, GIFs or videos, posts on X, Bilibili, YouTube, blogs, Xiaohongshu; added to "
                   "the card. Text pages in the repo itself are weak and do not count")
    p.add_argument("--no-results", metavar="REASON", help="why it is a reference without a verifiable effect")
    p.add_argument("--low-stars", metavar="REASON", help="why it is a reference under the star threshold")
    p.add_argument("--trial", metavar="TEXT", help="what we ran and what came out; written into the card, level trial")
    p.add_argument("--note", help="one line: what we take, or why not")
    p.add_argument("--where", help="where it lands in our project")
    p.add_argument("--kind", choices=KINDS, help="default: guessed")
    p.add_argument("--watch", nargs="+", metavar="PATH", help="upstream paths we depend on (globs ok)")
    p.add_argument("--summary", help="one line; default: the repo description")
    p.add_argument("--level", choices=LEVELS, help="how deep we looked (default read)")
    p.add_argument("--card", action="store_true", help="with --take skip: make a card anyway")
    p.add_argument("--idea", help="the idea, written into the card's first section")

    p = add("show", cmd_show, "a question with its coverage and answer, or a card with its history")
    p.add_argument("ref", help="<project>/<question>, owner/repo, or an alias")

    p = add("updates", cmd_updates, "what changed upstream since each card was reviewed", (common, js))
    p.add_argument("repos", nargs="*")
    p.add_argument("--project")
    p.add_argument("--diff", metavar="REPO", help="the upstream patch to a card's watched paths")
    p.add_argument("--all-files", action="store_true", help="with --diff: every changed file")
    p.add_argument("--max-lines", type=int, default=400)
    p.add_argument("--done", metavar="REPO", help="mark the card reviewed at the current upstream head")
    p.add_argument("--to", help="with --done: a specific commit")

    p = add("import", cmd_import, "read a report made elsewhere (a cloud chat, a teammate): check every GitHub "
            "link, keep the table's notes and verdicts")
    p.add_argument("file", help="a Markdown or text file with github.com links (tables with repo / take / why columns are read)")
    p.add_argument("--q", required=True, metavar="P/Q", help="the question the report answers")
    p.add_argument("--note", help="where the report came from, e.g. 'ChatGPT Pro 2026-10-17'")

    p = add("brief", cmd_brief, "turn an answered question into a hand-off for the coding agent (changes nothing)")
    p.add_argument("ref", metavar="P/Q")
    p.add_argument("--out", help="output file (default <store>/projects/<p>/briefs/<q>.md)")

    p = add("adopt", cmd_adopt, "record a repo brought into a project (stage 6): how, into which of our paths, from "
            "which of theirs, at which commits; updates then watches those files")
    p.add_argument("repo", help="owner/repo or an alias; it needs a card")
    p.add_argument("--q", required=True, metavar="P/Q", help="the question whose brief it came from")
    p.add_argument("--mode", choices=MODES, help="depend: a package at a pinned version · vendor: files copied at a "
                   "pinned commit · port: the idea rewritten in our code · skill: an agent skill as is · tool: their "
                   "CLI or app called as is · data: datasets, fonts, prompts, assets")
    p.add_argument("--into", required=True, metavar="PATHS", help="our paths, comma-separated: read from the current "
                   "directory inside the project, else from its code path; stored relative to the root of the git repository "
                   "holding them")
    p.add_argument("--from", dest="from_", metavar="PATHS", help="their files or folders we took, comma-separated, no "
                   "globs; updates reports the upstream commits that touch them")
    p.add_argument("--at", metavar="SHA", help="their commit we took it at (default: the card's reviewed commit)")
    p.add_argument("--ours", metavar="SHA", help="our commit that brought it in (default: HEAD of the git repository "
                   "holding the first --into path)")
    p.add_argument("--note", help="one line: the pinned version, what we changed, why")
    p.add_argument("--drop", action="store_true", help="mark the adoption with these --q and --into dropped; it stays "
                   "on the card as history")

    p = add("site", cmd_site, "write a static page to browse the registry (site/index.html)")
    p.add_argument("--out", help="output file (default <store>/site/index.html)")

    add("check", cmd_check, "validate the registry and regenerate INDEX.md")
    return ap


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):              # piped on Windows, the default codepage cannot write Chinese
        if (getattr(stream, "encoding", "") or "").lower().replace("-", "") != "utf8" and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 0
    if getattr(args, "store", None) is None:
        args.store = args.global_store
    try:
        return args.fn(args) or 0                    # a command returns its exit code, or nothing for 0
    except (StoreError, LookupError) as exc:
        print(f"github-scout: {exc}", file=sys.stderr)
        return 1
    except GitHubError as exc:
        hint = " (set GITHUB_TOKEN or run `gh auth login`)" if exc.status in (401, 403) else ""
        print(f"github-scout: GitHub {exc}{hint}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"github-scout: network or file error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
