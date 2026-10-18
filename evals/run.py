#!/usr/bin/env python3
"""Recall eval: scan each case in evals.json with its fixed vocabulary and report which must_find repos came back.

It searches GitHub for real, so it needs the network and a token (GITHUB_TOKEN, GH_TOKEN or `gh auth login`).
A scan takes five to ten minutes and about 150 API calls; cases with the same vocabulary share one. Run it by
hand after a change to search or ranking, and say what the change did to each case:

    python evals/run.py                         # every case
    python evals/run.py --case logged-in-browser
    python evals/run.py --json results.json     # also write the results
    python evals/run.py --keep evals-out        # keep each case's registry, to read its table later
    python evals/run.py --cases variant.json    # cases from another file, e.g. a vocabulary to compare

Each case runs in a registry of its own, so no earlier scan or verdict helps it. A repo counts as found when the
scan keeps it; the report also says where it sits (a table row, a rising row, a list, or why it is hidden),
because the table is what an agent reads first. Results drift: repos gain stars, go quiet or age out of the
rising window, so a miss can be the repo's change rather than the tool's.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "github-scout" / "scripts"))

from github_scout import discover, registry  # noqa: E402
from github_scout.github import Client  # noqa: E402
from github_scout.store import Store, min_stars  # noqa: E402

CASES = ROOT / "evals" / "evals.json"
VOCAB = ("langs", "entities", "mechanisms", "forms", "problems", "topics")


def load(path: Path | None = None) -> list[dict]:
    path = path or CASES
    cases = json.loads(path.read_text(encoding="utf-8"))["evals"]
    for c in cases:
        missing = [k for k in ("id", "prompt", "must_find", "vocabulary") if not c.get(k)]
        if missing:
            raise SystemExit(f"{path.name}: case {c.get('id', '?')} lacks {', '.join(missing)}")
    return cases


def scan_case(case: dict, client: Client, root: Path) -> tuple[dict, discover.Scan, dict]:
    """A fresh registry with the case as its only question, scanned with the default lenses and budget."""
    if root.exists():
        raise SystemExit(f"{root} exists: pass an empty folder to --keep")
    store = Store.init(root, "eval")
    registry.new_project(store, "eval", "Eval", "recall eval")
    ref = f"eval/{case['id']}"
    registry.new_question(store, ref, case["prompt"], case.get("stage", "working"))
    doc = store.question(ref)
    doc.data.update({k: v for k, v in case["vocabulary"].items() if k in VOCAB})
    store.save_question(doc)
    calls, start = client.calls, time.monotonic()
    sc = discover.Scan(store, client, doc.data)
    scan = sc.run()
    store.save_scan(scan)
    cost = {"calls": client.calls - calls, "seconds": round(time.monotonic() - start), "searches": len(scan["searches"]),
            "repos": len(scan["candidates"]), "errors": [f"{s['lens']} {s['query'][:60]}: {s['error'][:80]}"
                                                         for s in scan["searches"] if s.get("error")]}
    return discover.annotate(store, discover.rescore(scan, doc.data)), sc, cost


def where(scan: dict, sc: discover.Scan, slugs: list[str]) -> list[dict]:
    """Each repo: found or not, and where it sits."""
    rows = {c["repo"].lower(): i for i, c in enumerate(discover.visible(scan), 1)}
    rise = {c["repo"].lower(): i for i, c in enumerate(discover.rising(scan), 1)}
    kept = {c["repo"].lower(): c for c in scan["candidates"]}
    out = []
    for slug in slugs:
        k = slug.lower()
        c = kept.get(k) or sc.cands.get(k) or {}
        if k in rows:
            at = f"row {rows[k]}"
        elif k in rise:
            at = f"rising h{rise[k]}"
        elif k in kept:
            at = discover.why_hidden(c, min_stars())
        elif k in sc.cands:
            at = "returned by a search, but past the rows a scan keeps"
        elif k in sc.dropped:
            at = "returned by a search, but dropped: no push in 12 months"
        else:
            at = "not returned by any search"
        out.append({"repo": slug, "found": k in kept, "where": at, "lenses": "".join(c.get("lenses", []))})
    return out


def report(res: dict) -> str:
    lines = [f"{res['id']}: {sum(r['found'] for r in res['repos'])} of {len(res['repos'])} found"
             + (f" (scan shared with {res['shared']})" if res.get("shared") else
                f" · {res['calls']} API calls, {res['seconds'] / 60:.1f} min, {res['searches']} searches, {res['repos_kept']} repos")]
    for r in res["repos"]:
        lines.append(f"  {'found ' if r['found'] else 'MISSED'} {r['repo']}  {r['where']}" + (f"  [{r['lenses']}]" if r["lenses"] else ""))
    if res.get("errors"):
        lines.append(f"  errors ({len(res['errors'])}): " + "; ".join(res["errors"][:3]))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scan each eval case for real and report recall (network, by hand).")
    ap.add_argument("--case", nargs="+", metavar="ID", help="only these cases")
    ap.add_argument("--cases", metavar="FILE", help="read the cases from this file (default evals/evals.json)")
    ap.add_argument("--json", metavar="FILE", help="also write the results here")
    ap.add_argument("--keep", metavar="DIR", help="keep each case's registry here, one folder per case")
    ap.add_argument("--verbose", action="store_true", help="print every search as it runs")
    args = ap.parse_args(argv)
    cases = load(Path(args.cases) if args.cases else None)
    if args.case:
        unknown = sorted(set(args.case) - {c["id"] for c in cases})
        if unknown:
            raise SystemExit(f"no such case: {', '.join(unknown)} (cases: {', '.join(c['id'] for c in cases)})")
        cases = [c for c in cases if c["id"] in args.case]
    client = Client(verbose=args.verbose)
    if not client.token:
        raise SystemExit("needs a GitHub token: GITHUB_TOKEN, GH_TOKEN or `gh auth login` (code search requires one)")
    results, done = [], {}
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(args.keep) if args.keep else Path(tmp)
        for case in cases:
            key = json.dumps(case["vocabulary"], sort_keys=True, ensure_ascii=False)
            shared = done.get(key)
            if shared is None:
                print(f"scanning {case['id']} ...", file=sys.stderr, flush=True)
                done[key] = shared = (case["id"], *scan_case(case, client, base / case["id"]))
            first, scan, sc, cost = shared
            res = {"id": case["id"], "repos": where(scan, sc, case["must_find"]),
                   **({"shared": first} if first != case["id"] else
                      {k: cost[k] for k in ("calls", "seconds", "searches", "errors")} | {"repos_kept": cost["repos"]})}
            results.append(res)
            print(report(res), flush=True)
    found = sum(r["found"] for res in results for r in res["repos"])
    total = sum(len(res["repos"]) for res in results)
    calls = sum(res.get("calls", 0) for res in results)
    minutes = sum(res.get("seconds", 0) for res in results) / 60
    print(f"recall: {found} of {total} repos in {len(results)} cases · {calls} API calls, {minutes:.1f} min")
    if args.json:
        Path(args.json).write_text(json.dumps({"date": time.strftime("%Y-%m-%d"), "found": found, "of": total,
                                               "cases": results}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return 0 if found == total else 1


if __name__ == "__main__":
    sys.exit(main())
