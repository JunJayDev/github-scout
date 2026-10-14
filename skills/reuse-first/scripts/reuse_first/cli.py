"""Command line for reuse-first. `reuse-first <command> --help` for details."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from . import __version__
from .discover import DEFAULT_LENSES, LENS_NAMES, LENSES, Scan, annotate, plan, render, rescore, slugs_in_text, visible
from .examine import bump, diff, digest, fetch, outdated, peek, render_outdated, render_peek
from .github import Client, GitHubError, github_slug
from .registry import (
    find, new_card, new_need, new_project, relate, render_find, show_card, show_need, write_index,
)
from .store import KINDS, LEVELS, RELATIONS, VERDICTS, Store, StoreError, locate, today

EPILOG = """workflow (see the skill's SKILL.md):
  find -> new-need -> plan/scan -> triage -> peek -> fetch + read -> card/relate -> index
  later: outdated -> diff -> bump

store: --store DIR, else $REUSE_FIRST_STORE, else the config file, else the nearest
parent directory that contains reuse-first.json."""


def _store(args) -> Store:
    return Store(locate(args.store))


def make_client(args) -> Client:
    return Client(verbose=not args.quiet)


def _client(args) -> Client:
    return make_client(args)


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


def _entry(args, store: Store, repo: str, project: str, need: str, verdict: str, level: str,
           reason: str | None = None, meta: dict | None = None, scan: str | None = None) -> dict:
    meta = meta or {}
    e = {"date": today(), "repo": repo, "project": project, "need": need, "verdict": verdict, "level": level,
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


def _latest_scan(store: Store, project: str, need: str, scan_id: str | None = None) -> dict:
    scans = store.scans(project, need)
    if scan_id:
        scans = [p for p in scans if p.stem == scan_id]
    if not scans:
        raise StoreError(f"no scan for {project}/{need} yet (reuse-first scan {project}/{need})")
    return json.loads(scans[-1].read_text(encoding="utf-8"))


def _merge_scans(store: Store, project: str, need: str, since: str | None = None) -> dict:
    return rescore(_merge(store, project, need, since), store.need(f"{project}/{need}").data)


def _merge(store: Store, project: str, need: str, since: str | None = None) -> dict:
    """All candidates from the scans of a need (newest metadata wins)."""
    merged: dict[str, dict] = {}
    searches: list = []
    last = None
    for p in store.scans(project, need):
        s = json.loads(p.read_text(encoding="utf-8"))
        if since and s["id"] < since:
            continue
        last = s
        searches += s["searches"]
        for c in s["candidates"]:
            key = c["repo"].lower()
            if key in merged:
                lenses = sorted(set(merged[key]["lenses"]) | set(c["lenses"]), key=LENSES.index)
                merged[key] = {**c, "lenses": lenses}
            else:
                merged[key] = dict(c)
    if last is None:
        raise StoreError(f"no scan for {project}/{need} yet (reuse-first scan {project}/{need})")
    return {**last, "searches": searches, "candidates": list(merged.values())}


# ---------------------------------------------------------------------------
# commands


def cmd_init(args):
    store = Store.init(Path(args.dir), args.name)
    print(f"registry created: {store.root}\nnext: export REUSE_FIRST_STORE={store.root}  (or add it to the config file)\n"
          f"      reuse-first new-project <id> --name \"...\"")


def cmd_new_project(args):
    store = _store(args)
    print(new_project(store, args.id, args.name, args.summary or ""))


def cmd_new_need(args):
    store = _store(args)
    path = new_need(store, args.ref, args.want)
    print(f"{path}\nfill entities, mechanisms, forms, problems (every language you search in), then:"
          f" reuse-first plan {args.ref}")


def cmd_find(args):
    store = _store(args)
    res = find(store, args.words, args.limit)
    data = {"cards": [c.data for c in res["cards"]], "needs": [n.data for n in res["needs"]], "ledger": res["ledger"]}
    _out(args, render_find(res), data)


def cmd_plan(args):
    store = _store(args)
    doc = store.need(args.ref)
    rows = plan(doc.data, args.lenses)
    for r in rows:
        print(f"{r['lens']} {LENS_NAMES[r['lens']]:<10} {r['query']}")
    print(f"{len(rows)} searches. Run them: reuse-first scan {args.ref}" + (f" --lenses {args.lenses}" if args.lenses != DEFAULT_LENSES else ""))


def cmd_scan(args):
    store = _store(args)
    doc = store.need(args.ref)
    d = doc.data
    client = _client(args)
    sc = Scan(store, client, d["project"], d["id"], d)
    scan = sc.run(args.lenses, args.budget, args.per_query)
    path = store.save_scan(scan)
    doc.data["scanned"] = today()
    from .store import NEED_ORDER, write_doc

    write_doc(doc.path, doc.data, doc.body, NEED_ORDER)
    merged = annotate(store, _merge_scans(store, d["project"], d["id"]) if args.merge else scan)
    _out(args, render(merged, args.top, args.all) + f"\nsaved {path.relative_to(store.root)} · {client.calls} API calls"
         f"\nnext: reuse-first triage {d['project']}/{d['id']} --short <#|repo>... --rest \"<why the rest are out>\"",
         merged)


def cmd_results(args):
    store = _store(args)
    project, need = store.split_ref(args.ref)
    scan = rescore(_latest_scan(store, project, need, args.scan), store.need(args.ref).data) if args.scan \
        else _merge_scans(store, project, need)
    scan = annotate(store, scan)
    _out(args, render(scan, args.top, args.all), scan)


def _ingest_scan(store: Store, client: Client, project: str, need_doc, slugs: list[str], lens: str, source: str,
                 filter_vocab: bool) -> dict:
    sc = Scan(store, client, project, need_doc.data["id"], need_doc.data)
    n = sc._add_slugs(slugs, lens, filter_vocab)
    sc.log.append({"lens": lens, "kind": "ingest", "query": source[:200], "hits": n})
    scan = sc.finish(lens)
    store.save_scan(scan)
    return scan


def _read_source(src: str) -> str:
    if src == "-":
        return sys.stdin.read()
    if src.startswith(("http://", "https://")) and not github_slug(src):
        req = urllib.request.Request(src, headers={"User-Agent": f"reuse-first/{__version__}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", "replace")
    p = Path(src)
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="replace")
    return src  # treat the argument itself as text (one or more URLs)


def cmd_ingest(args):
    store = _store(args)
    doc = store.need(args.ref)
    text = "\n".join(_read_source(s) for s in args.sources)
    slugs = slugs_in_text(text)
    if not slugs:
        raise StoreError("no github.com/<owner>/<repo> links found")
    client = _client(args)
    scan = _ingest_scan(store, client, doc.data["project"], doc, slugs, "W", args.note or ", ".join(args.sources), False)
    scan = annotate(store, scan)
    _out(args, render(scan, args.top, True) + f"\n{len(slugs)} links, {len(scan['candidates'])} repos resolved", scan)


def cmd_expand(args):
    store = _store(args)
    doc = store.need(args.ref)
    client = _client(args)
    slug = _slug(args.list)
    text = client.readme(slug) or ""
    slugs = [s for s in slugs_in_text(text) if s.lower() != slug.lower()]
    if not slugs:
        raise StoreError(f"{slug}: no GitHub links in its README")
    filt = not args.all
    scan = _ingest_scan(store, client, doc.data["project"], doc, slugs[: args.max], "L", f"expand {slug}", filt)
    scan = annotate(store, scan)
    _out(args, render(scan, args.top, False) + f"\n{len(slugs)} links in {slug}; kept {len(scan['candidates'])}"
         + (" matching the need's vocabulary (--all keeps every link)" if filt else ""), scan)


def cmd_triage(args):
    store = _store(args)
    project, need = store.split_ref(args.ref)
    scan = annotate(store, _merge_scans(store, project, need))
    open_rows = visible(scan)
    by_repo = {c["repo"].lower(): c for c in scan["candidates"]}

    def resolve(item: str) -> tuple[dict, str | None]:
        ref, _, reason = item.partition("=")
        ref = ref.strip()
        if ref.isdigit():
            i = int(ref)
            if not 1 <= i <= len(open_rows):
                raise StoreError(f"#{i} is not in the list (1-{len(open_rows)}); run `reuse-first results {args.ref}`")
            return open_rows[i - 1], reason or None
        slug = _slug(ref)
        return by_repo.get(slug.lower(), {"repo": slug}), reason or None

    entries, decided = [], set()
    for verdict, items in (("short", args.short), ("list", args.list), ("defer", args.defer), ("skip", args.skip)):
        for item in items or []:
            c, reason = resolve(item)
            decided.add(c["repo"].lower())
            entries.append(_entry(args, store, c["repo"], project, need, verdict, "meta",
                                  reason or (args.why if verdict == "skip" else None), c, scan.get("id")))
    if args.rest:
        from .discover import is_open

        open_lists = [c for c in scan["candidates"] if c.get("list") and is_open(c)]
        for c in open_rows + open_lists:
            if c["repo"].lower() not in decided:
                entries.append(_entry(args, store, c["repo"], project, need, "skip", "meta", args.rest, c, scan.get("id")))
    store.append_ledger(entries)
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["verdict"]] = counts.get(e["verdict"], 0) + 1
    short = [e["repo"] for e in entries if e["verdict"] == "short"]
    lists = [e["repo"] for e in entries if e["verdict"] == "list"]
    print("recorded: " + (", ".join(f"{k} {v}" for k, v in counts.items()) or "nothing"))
    if short:
        print("next: reuse-first peek --need " + f"{project}/{need} " + " ".join(short))
    for l in lists:
        print(f"next: reuse-first expand {project}/{need} {l}")


def cmd_mark(args):
    store = _store(args)
    project, need = store.split_ref(args.need)
    entries = [_entry(args, store, _slug(r), project, need, args.verdict, args.level, args.reason) for r in args.repos]
    store.append_ledger(entries)
    print(f"recorded {args.verdict} for {len(entries)} repo(s) under {project}/{need}")


def cmd_peek(args):
    store = _store(args) if args.need else None
    client = _client(args)
    results, texts, entries = [], [], []
    for r in args.repos:
        try:
            p = peek(client, _slug(r), args.readme)
        except (LookupError, GitHubError) as exc:
            texts.append(f"## {r}: {exc}")
            continue
        results.append(p)
        texts.append(render_peek(p))
        if store:
            project, need = store.split_ref(args.need)
            entries.append(_entry(args, store, p["repo"], project, need, "peeked", "peek", None, p))
    if store:
        store.append_ledger(entries)
    _out(args, "\n\n".join(texts) + ("\n\nnext: skip with `reuse-first mark ... --verdict skip --reason`, or read source"
                                     " with `reuse-first fetch <repo>` and register with `reuse-first card`" if results else ""),
         results)


def cmd_fetch(args):
    store = _store(args)
    client = _client(args)
    path = fetch(store, client, _slug(args.repo) if "/" in args.repo else args.repo, args.ref)
    print(digest(path))


def cmd_path(args):
    store = _store(args)
    card = store.card(args.repo)
    slug = card.id if card else _slug(args.repo)
    want = store.cache_dir(slug, str(card.data.get("commit"))) if card and card.data.get("commit") else None
    paths = store.cached(slug)
    if want and want.exists():
        print(want)
    elif paths:
        print(paths[-1])
        if want:
            print(f"(the card's commit is not cached: reuse-first fetch {slug})", file=sys.stderr)
    else:
        raise StoreError(f"{slug}: not cached (reuse-first fetch {slug})")


def cmd_card(args):
    store = _store(args)
    client = _client(args)
    slug = _slug(args.repo)
    meta = peek(client, slug, 0)
    project, need = store.split_ref(args.need)
    kind = args.kind or meta["kind"]
    use = {"project": project, "need": need, "relation": args.relation, "where": args.where, "note": args.note}
    doc = new_card(store, meta, kind, [{k: v for k, v in use.items() if v}], args.watch or [], args.level, args.summary)
    store.append_ledger([_entry(args, store, meta["repo"], project, need, "card", args.level,
                                args.note or args.relation, meta)])
    print(f"{doc.path}\nkind {kind} (guessed: {meta['kind']}; {'; '.join(meta['evidence'])})\n"
          f"fill the sections, list the files you depend on under watch:, then reuse-first check && reuse-first index")


def cmd_relate(args):
    store = _store(args)
    if args.need:
        project, need = store.split_ref(args.need)
    else:
        project, need = args.project, None
    if not project:
        raise StoreError("give --need <project>/<need> or --project <project>")
    card = relate(store, args.repo, {"project": project, "need": need, "relation": args.relation,
                                     "where": args.where, "note": args.note})
    store.append_ledger([_entry(args, store, card.id, project, need or "", "card", card.data.get("level") or "read",
                                f"relation {args.relation}" + (f": {args.note}" if args.note else ""))])
    print(f"{card.path}: {project}/{need or '-'} -> {args.relation}")


def cmd_show(args):
    store = _store(args)
    ref = args.ref
    if ref.count("/") == 1 and store.project(ref.split("/")[0]) and \
            store.need_path(*ref.split("/")).is_file():
        print(show_need(store, ref))
    else:
        print(show_card(store, ref))


def cmd_outdated(args):
    store = _store(args)
    client = _client(args)
    rows = outdated(store, client, args.repos or None, args.project)
    _out(args, render_outdated(rows), rows)


def cmd_diff(args):
    store = _store(args)
    print(diff(store, _client(args), args.repo, args.all_files, args.max_lines))


def cmd_bump(args):
    store = _store(args)
    r = bump(store, _client(args), args.repo, args.to)
    print(f"{r['repo']}: {r['from']} -> {r['to']} (reviewed today). Update the card text if anything you use changed.")


def cmd_index(args):
    store = _store(args)
    print(write_index(store))


def cmd_check(args):
    store = _store(args)
    errors, warns = store.check()
    for w in warns:
        print(f"warn  {w}")
    for e in errors:
        print(f"error {e}")
    print(f"{len(errors)} error(s), {len(warns)} warning(s)")
    if errors:
        sys.exit(1)


# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="reuse-first", description="Find, vet and register open-source repositories "
                                 "before building; keep a shared registry so nothing is reviewed twice.",
                                 epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"reuse-first {__version__}")
    ap.add_argument("--store", dest="global_store", metavar="DIR", help="registry directory (also accepted after the command)")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--store", help="registry directory (default: $REUSE_FIRST_STORE, config, or nearest reuse-first.json)")
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

    p = add("new-project", cmd_new_project, "add a project profile")
    p.add_argument("id")
    p.add_argument("--name", required=True)
    p.add_argument("--summary")

    p = add("new-need", cmd_new_need, "add a need (one capability a project wants) with a vocabulary template")
    p.add_argument("ref", help="<project>/<need>")
    p.add_argument("--want", required=True, help="one sentence: what must be possible")

    p = add("find", cmd_find, "search cards, needs and the ledger: has anyone looked at this?", (common, js))
    p.add_argument("words", nargs="+")
    p.add_argument("--limit", type=int, default=20)

    lens_help = "lens letters to run, from " + LENSES + f" (default {DEFAULT_LENSES}); see `plan`"
    p = add("plan", cmd_plan, "print the searches a scan would run (no network)")
    p.add_argument("ref")
    p.add_argument("--lenses", default=DEFAULT_LENSES, help=lens_help)

    p = add("scan", cmd_scan, "run the searches for a need, save the scan, print ranked new candidates", (common, js))
    p.add_argument("ref")
    p.add_argument("--lenses", default=DEFAULT_LENSES, help=lens_help)
    p.add_argument("--budget", type=int, default=150, help="max API calls (default 150)")
    p.add_argument("--per-query", type=int, default=30)
    p.add_argument("--top", type=int, default=40)
    p.add_argument("--all", action="store_true", help="also show candidates already triaged for this need")
    p.add_argument("--merge", action="store_true", help="show this scan merged with earlier scans of the need")

    p = add("results", cmd_results, "re-print a need's candidates from saved scans (no network)", (common, js))
    p.add_argument("ref")
    p.add_argument("--scan", help="one scan id instead of all scans merged")
    p.add_argument("--top", type=int, default=40)
    p.add_argument("--all", action="store_true")

    p = add("ingest", cmd_ingest, "add repos found elsewhere (web search, X, chat): files, URLs, '-' or text",
            (common, js))
    p.add_argument("ref")
    p.add_argument("sources", nargs="+")
    p.add_argument("--note", help="where these came from, e.g. 'web: site:github.com xiaohongshu cli'")
    p.add_argument("--top", type=int, default=60)

    p = add("expand", cmd_expand, "pull candidates out of an awesome-list README", (common, js))
    p.add_argument("ref")
    p.add_argument("list", help="owner/repo of the list")
    p.add_argument("--all", action="store_true", help="keep links that do not match the need's vocabulary")
    p.add_argument("--max", type=int, default=400)
    p.add_argument("--top", type=int, default=40)

    p = add("triage", cmd_triage, "record verdicts for scan rows (numbers from `results`, or owner/repo)")
    p.add_argument("ref")
    p.add_argument("--short", nargs="+", metavar="ITEM", help="worth a peek")
    p.add_argument("--list", nargs="+", metavar="ITEM", help="awesome-lists to expand")
    p.add_argument("--defer", nargs="+", metavar="ITEM", help="maybe later")
    p.add_argument("--skip", nargs="+", metavar="ITEM[=reason]", help="not for this need")
    p.add_argument("--why", help="reason for --skip items without their own")
    p.add_argument("--rest", metavar="REASON", help="skip every other open row with this reason")

    p = add("mark", cmd_mark, "record a verdict for repos directly")
    p.add_argument("repos", nargs="+")
    p.add_argument("--need", required=True)
    p.add_argument("--verdict", required=True, choices=VERDICTS)
    p.add_argument("--level", default="peek", choices=LEVELS)
    p.add_argument("--reason")

    p = add("peek", cmd_peek, "API-only digest of repos: facts, kind guess, tree, manifests, README start",
            (common, js))
    p.add_argument("repos", nargs="+")
    p.add_argument("--need", help="record 'peeked' in the ledger under this need")
    p.add_argument("--readme", type=int, default=2500, help="README characters (default 2500)")

    p = add("fetch", cmd_fetch, "download a commit's source to the cache and print where the code is")
    p.add_argument("repo")
    p.add_argument("--ref", help="commit, tag or branch (default: the card's commit, else the default branch)")

    p = add("path", cmd_path, "print the cached source directory of a repo")
    p.add_argument("repo")

    p = add("card", cmd_card, "register a repo you have read: creates repos/<owner>__<repo>.md")
    p.add_argument("repo")
    p.add_argument("--need", required=True, help="<project>/<need>")
    p.add_argument("--relation", required=True, choices=RELATIONS)
    p.add_argument("--kind", choices=list(KINDS), help="default: the peek guess")
    p.add_argument("--where", help="where it is used in our project (path, service)")
    p.add_argument("--note", help="one line: what we take, or why not")
    p.add_argument("--watch", nargs="+", metavar="PATH", help="upstream paths we depend on (globs ok)")
    p.add_argument("--summary", help="one line; default: the repo description")
    p.add_argument("--level", default="read", choices=LEVELS, help="how deep you looked (default read)")

    p = add("relate", cmd_relate, "add or update how a carded repo relates to a project or need")
    p.add_argument("repo")
    p.add_argument("--need")
    p.add_argument("--project")
    p.add_argument("--relation", required=True, choices=RELATIONS)
    p.add_argument("--where")
    p.add_argument("--note")

    p = add("show", cmd_show, "show a card with its ledger history, or a need with its coverage")
    p.add_argument("ref", help="owner/repo, an alias, or <project>/<need>")

    p = add("outdated", cmd_outdated, "what changed upstream since each card was reviewed", (common, js))
    p.add_argument("repos", nargs="*")
    p.add_argument("--project")

    p = add("diff", cmd_diff, "upstream changes to a card's watched paths since its reviewed commit")
    p.add_argument("repo")
    p.add_argument("--all-files", action="store_true")
    p.add_argument("--max-lines", type=int, default=400)

    p = add("bump", cmd_bump, "mark a card reviewed at the current upstream head (after re-reading)")
    p.add_argument("repo")
    p.add_argument("--to", help="a specific commit sha")

    add("index", cmd_index, "regenerate INDEX.md")
    add("check", cmd_check, "validate the registry")
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
