"""Command line for reuse-first. `reuse-first <command> --help` for details."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from . import __version__
from .discover import (
    DEFAULT_LENSES, LENS_NAMES, LENSES, Scan, annotate, is_open, is_stale, plan, render, rescore, slugs_in_text, visible,
)
from .examine import bump, diff, digest, fetch, outdated, peek, render_outdated, render_peek
from .github import Client, GitHubError, github_slug
from .registry import (
    find, new_card, new_project, new_question, render_find, set_use, show_card, show_question, stage_help, write_index,
)
from .store import KINDS, LEVELS, STAGES, TAKES, Store, StoreError, locate, today

EPILOG = """the loop (see SKILL.md):
  find -> ask -> scan -> pick -> look -> note -> write the answer -> check
  later: updates

store: --store DIR, else $REUSE_FIRST_STORE, else the config file, else the nearest
parent directory that contains reuse-first.json."""


def _store(args) -> Store:
    return Store(locate(args.store))


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
         "by": args.by or os.environ.get("REUSE_FIRST_AGENT") or "agent"}
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


def _merged(store: Store, project: str, qid: str) -> dict:
    """All candidates from every scan of a question, rescored against its current vocabulary."""
    merged: dict[str, dict] = {}
    searches: list = []
    last = None
    dropped = 0
    for p in store.scans(project, qid):
        s = json.loads(p.read_text(encoding="utf-8"))
        last = s
        searches += s["searches"]
        dropped += int(s.get("dropped") or 0)
        for c in s["candidates"]:
            key = c["repo"].lower()
            if key in merged:
                lenses = sorted(set(merged[key]["lenses"]) | set(c["lenses"]), key=LENSES.index)
                installs = max(merged[key].get("installs") or 0, c.get("installs") or 0)
                merged[key] = {**c, "lenses": lenses, **({"installs": installs} if installs else {})}
            else:
                merged[key] = dict(c)
    if last is None:
        raise StoreError(f"no scan for {project}/{qid} yet (reuse-first scan {project}/{qid})")
    scan = {**last, "searches": searches, "dropped": dropped, "candidates": list(merged.values())}
    return annotate(store, rescore(scan, store.question(f"{project}/{qid}").data))


# ---------------------------------------------------------------------------
# commands


def cmd_init(args):
    store = Store.init(Path(args.dir), args.name, args.lang)
    print(f"registry created: {store.root}\nnext: export REUSE_FIRST_STORE={store.root}  (or put it in the config file)\n"
          f"      reuse-first new-project <id> --name \"...\" --code <path to its code>")


def cmd_new_project(args):
    print(new_project(_store(args), args.id, args.name, args.summary or "", args.code or ""))


def cmd_ask(args):
    store = _store(args)
    path = new_question(store, args.ref, args.question, args.stage)
    print(f"{path}\n"
          f"stage {args.stage}: {stage_help(store, args.stage)}\n"
          "before searching, edit the file:\n"
          "  1. Where we are: what we already have (paths) and what is not good enough.\n"
          "  2. Vocabulary: entities (platforms, formats, products; synonyms and other languages with |),\n"
          "     mechanisms (how a solution would work, in README words), forms, 2-4 short problem phrases.\n"
          f"then: reuse-first scan {args.ref} --plan")


def cmd_find(args):
    res = find(_store(args), args.words, args.limit)
    _out(args, render_find(res), {"cards": [c.data for c in res["cards"]],
                                  "questions": [q.data for q in res["questions"]], "ledger": res["ledger"]})


def _read_source(src: str) -> str:
    if src == "-":
        return sys.stdin.read()
    if src.startswith(("http://", "https://")) and not github_slug(src):
        req = urllib.request.Request(src, headers={"User-Agent": f"reuse-first/{__version__}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    p = Path(src)
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else src


def cmd_scan(args):
    store = _store(args)
    doc = store.question(args.ref)
    q = doc.data
    ref = f"{q['project']}/{q['id']}"
    if args.plan:
        rows = plan(q, args.lenses)
        for r in rows:
            print(f"{r['lens']} {LENS_NAMES[r['lens']]:<12} {r['query']}")
        print(f"{len(rows)} searches. Run them: reuse-first scan {ref}")
        return
    if not args.show:
        client = make_client(args, store)
        sc = Scan(store, client, q)
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
        print(f"saved {path.relative_to(store.root)} · {client.calls} API calls", file=sys.stderr)
    merged = _merged(store, q["project"], q["id"])
    _out(args, render(merged, args.top, args.all)
         + f"\nnext: reuse-first pick {ref} <#>... --rest \"<why the rest do not help>\"", merged)


def cmd_pick(args):
    store = _store(args)
    project, qid = store.split_ref(args.ref)
    scan = _merged(store, project, qid)
    rows = visible(scan)
    by_repo = {c["repo"].lower(): c for c in scan["candidates"]}

    def resolve(item: str) -> tuple[dict, str | None]:
        ref, _, reason = item.partition("=")
        ref = ref.strip()
        if ref.isdigit():
            i = int(ref)
            if not 1 <= i <= len(rows):
                raise StoreError(f"#{i} is not in the list (1-{len(rows)}); run `reuse-first scan {args.ref} --show`")
            return rows[i - 1], reason or None
        slug = _slug(ref)
        return by_repo.get(slug.lower(), {"repo": slug}), reason or None

    entries, decided = [], set()
    for verdict, items in (("short", args.items), ("list", args.list), ("later", args.later), ("skip", args.skip)):
        for item in items or []:
            c, reason = resolve(item)
            decided.add(c["repo"].lower())
            entries.append(_entry(args, c["repo"], project, qid, verdict, "meta",
                                  reason or (args.why if verdict == "skip" else None), c, scan.get("id")))
    if args.rest:
        lists = [c for c in scan["candidates"] if c.get("list") and is_open(c) and not is_stale(c)][:8]
        for c in rows[: args.top] + lists:
            if c["repo"].lower() not in decided:
                entries.append(_entry(args, c["repo"], project, qid, "skip", "meta", args.rest, c, scan.get("id")))
    store.append_ledger(entries)
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1
    print("recorded: " + (", ".join(f"{k} {v}" for k, v in counts.items()) or "nothing"))
    short = [e["repo"] for e in entries if e["verdict"] == "short"]
    if short:
        print(f"next: reuse-first look --q {project}/{qid} " + " ".join(short))
    for e in entries:
        if e["verdict"] == "list":
            print(f"next: reuse-first scan {project}/{qid} --expand {e['repo']}")


def cmd_look(args):
    store = _store(args)
    client = make_client(args, store)
    texts, results, entries = [], [], []
    for r in args.repos:
        card = store.card(r)
        slug = card.id if card else _slug(r)
        try:
            p = peek(client, slug, args.readme)
        except (LookupError, GitHubError) as exc:
            texts.append(f"## {r}: {exc}")
            continue
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
    _out(args, "\n\n".join(texts) + ("\n\nnext: reuse-first note <repo> --q <question> --take use|adapt|learn|later|skip"
                                     " --note \"...\"" if results else ""), results)


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


def cmd_note(args):
    store = _store(args)
    project, qid = store.split_ref(args.q)
    card = store.card(args.repo)
    use = {"project": project, "question": qid, "take": args.take, "where": args.where, "note": args.note}
    if card:
        set_use(store, card.id, use, args.level)
        store.append_ledger([_entry(args, card.id, project, qid, "card", args.level or "read", f"{args.take}: {args.note or ''}")])
        print(f"{card.path}: {project}/{qid} -> {args.take}")
        return
    slug = _slug(args.repo)
    if args.take == "skip" and not args.card:
        store.append_ledger([_entry(args, slug, project, qid, "skip", args.level or "look", args.note)])
        print(f"recorded skip for {slug} under {project}/{qid} (no card; --card makes one)")
        return
    client = make_client(args, store)
    meta = peek(client, slug, 0)
    kind = args.kind or meta["kind"]
    doc = new_card(store, meta, kind, meta["form"], [{k: v for k, v in use.items() if v}], args.watch or [],
                   args.level or "read", args.summary)
    store.append_ledger([_entry(args, meta["repo"], project, qid, "card", args.level or "read",
                                f"{args.take}: {args.note or ''}", meta)])
    print(f"{doc.path}\nkind {kind} ({meta['form']}; {'; '.join(meta['evidence'])})\n"
          "fill the card (the idea first), list upstream paths we depend on under watch:, "
          "then write the answer in the question file and run reuse-first check")


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
    _out(args, render_outdated(rows) + "\nnext: reuse-first updates --diff <repo>, update the card, then --done <repo>", rows)


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
    if errors:
        sys.exit(1)


# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="reuse-first", description="Ask a question, find what open source already "
                                 "answers it, take the ideas and parts that fit, and remember every verdict.",
                                 epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"reuse-first {__version__}")
    ap.add_argument("--store", dest="global_store", metavar="DIR", help="registry directory (also accepted after the command)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--store", help="registry directory")
    common.add_argument("--quiet", action="store_true", help="no progress on stderr")
    common.add_argument("--by", help="who records verdicts (default: $REUSE_FIRST_AGENT or 'agent')")
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
    p.add_argument("ref", help="<project>/<question-id>")
    p.add_argument("question", help="one sentence: the result we want, not the tool we imagine")
    p.add_argument("--stage", required=True, choices=STAGES, help="where our own work stands")

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
    p.add_argument("--budget", type=int, default=150, help="max API calls (default 150)")
    p.add_argument("--per-query", type=int, default=30)
    p.add_argument("--top", type=int, default=40)
    p.add_argument("--all", action="store_true", help="also show decided and stale rows; with --expand keep every link")

    p = add("pick", cmd_pick, "record verdicts on scan rows: numbers from the table, or owner/repo")
    p.add_argument("ref")
    p.add_argument("items", nargs="*", metavar="ITEM", help="worth a look")
    p.add_argument("--list", nargs="+", metavar="ITEM", help="awesome lists to expand")
    p.add_argument("--later", nargs="+", metavar="ITEM", help="maybe later")
    p.add_argument("--skip", nargs="+", metavar="ITEM[=reason]", help="no help for this question")
    p.add_argument("--why", help="reason for --skip items without their own")
    p.add_argument("--rest", metavar="REASON", help="skip every other row shown, with this reason")
    p.add_argument("--top", type=int, default=40, help="rows --rest covers (default 40)")

    p = add("look", cmd_look, "look at repos: facts, activity, kind, tree, README start; --source reads the code",
            (common, js))
    p.add_argument("repos", nargs="+")
    p.add_argument("--q", help="<project>/<question>: record that we looked")
    p.add_argument("--readme", type=int, default=2500, help="README characters (default 2500)")
    p.add_argument("--source", action="store_true", help="download the source and print where the code is")
    p.add_argument("--ref", help="with --source: commit, tag or branch (default: card commit or default branch)")
    p.add_argument("--pack", action="store_true", help="with --source: also write a repomix digest if installed")
    p.add_argument("--include", nargs="+", metavar="GLOB", help="with --pack: only these paths")

    p = add("note", cmd_note, "record what we take from a repo; creates or updates its card")
    p.add_argument("repo")
    p.add_argument("--q", required=True, help="<project>/<question>")
    p.add_argument("--take", required=True, choices=TAKES)
    p.add_argument("--note", help="one line: what we take, or why not")
    p.add_argument("--where", help="where it lands in our project")
    p.add_argument("--kind", choices=KINDS, help="default: guessed")
    p.add_argument("--watch", nargs="+", metavar="PATH", help="upstream paths we depend on (globs ok)")
    p.add_argument("--summary", help="one line; default: the repo description")
    p.add_argument("--level", choices=LEVELS, help="how deep we looked (default read)")
    p.add_argument("--card", action="store_true", help="with --take skip: make a card anyway")

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

    p = add("site", cmd_site, "write a static page to browse the registry (site/index.html)")
    p.add_argument("--out", help="output file (default <store>/site/index.html)")

    add("check", cmd_check, "validate the registry and regenerate INDEX.md")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "fn", None):
        ap.print_help()
        return 0
    if getattr(args, "store", None) is None:
        args.store = args.global_store
    try:
        args.fn(args)
    except (StoreError, LookupError) as exc:
        print(f"reuse-first: {exc}", file=sys.stderr)
        return 1
    except GitHubError as exc:
        hint = " (set GITHUB_TOKEN or run `gh auth login`)" if exc.status in (401, 403) else ""
        print(f"reuse-first: GitHub {exc}{hint}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"reuse-first: network or file error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
