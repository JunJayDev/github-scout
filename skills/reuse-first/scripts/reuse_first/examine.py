"""Looking at a repository as cheaply as possible, and checking it again later.

peek   API only, ~1-1.5k tokens: facts, kind guess with evidence, tree summary,
       manifests, the start of the README. Enough to decide whether to read source.
fetch  download one commit's source into the cache and print a digest that
       says where the code is and how big each part is, so reading can be targeted.
outdated / diff  what changed upstream since the commit a card was reviewed at,
       narrowed to the paths the card watches.
"""

from __future__ import annotations

import fnmatch
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .github import Client
from .store import Store, as_list, today

MANIFESTS = ["package.json", "pyproject.toml", "setup.py", "Cargo.toml", "go.mod", "Package.swift",
             ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "manifest.json", "action.yml",
             "Dockerfile", "docker-compose.yml", "mcp.json", "smithery.yaml", "AGENTS.md", "CLAUDE.md"]
SKIP_DIRS = {".git", "node_modules", "dist", "build", "vendor", "__pycache__", ".venv", "venv", "target",
             ".next", "coverage"}
TEXT_EXT = {".md", ".txt", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".swift", ".rb",
            ".java", ".kt", ".c", ".h", ".cpp", ".cs", ".php", ".sh", ".json", ".yaml", ".yml", ".toml", ".html",
            ".css", ".vue", ".svelte", ".lua", ".sql"}


def guess_kind(paths: list[str], files: dict[str, str], name: str, readme: str) -> tuple[str, list[str]]:
    """Best guess of a repo's kind from its tree and root manifests, with the evidence."""
    ev: list[str] = []
    skills = [p for p in paths if p.endswith("SKILL.md")]
    pkg = _json(files.get("package.json"))
    deps = {**(pkg.get("dependencies") or {}), **(pkg.get("devDependencies") or {})} if pkg else {}
    pyproj = files.get("pyproject.toml") or ""
    low = name.lower()
    links = len(re.findall(r"\]\((?:https?://)", readme or ""))
    code = [p for p in paths if Path(p).suffix in TEXT_EXT - {".md", ".txt", ".json", ".yaml", ".yml", ".toml"}]
    if low.startswith("awesome") or (links > 60 and len(code) < 5):
        return "list", [f"{links} links in README, {len(code)} code files"]
    if "@modelcontextprotocol/sdk" in deps or re.search(r"\b(fastmcp|mcp)\b", pyproj) or "mcp" in re.split(r"[-_.]", low):
        ev.append("MCP SDK dependency or mcp in name")
        return "mcp", ev
    if skills:
        ev.append(f"{len(skills)} SKILL.md: " + ", ".join(skills[:4]) + (" ..." if len(skills) > 4 else ""))
        plugin = any(p.startswith(".claude-plugin/") for p in paths)
        if plugin:
            ev.append(".claude-plugin manifest")
        # A tool that also ships a skill is still software when it has a real code base.
        if len(code) > 40 and (pkg.get("bin") or "[project.scripts]" in pyproj or "Cargo.toml" in files):
            ev.append(f"{len(code)} code files and a CLI entry point: software that ships skills")
        else:
            return ("skill-pack" if len(skills) > 1 or plugin else "skill"), ev
    mf = _json(files.get("manifest.json"))
    if mf.get("manifest_version"):
        return "extension", [f"browser extension manifest v{mf['manifest_version']}"]
    if pkg.get("bin") or "[project.scripts]" in pyproj or any(p.startswith("cmd/") for p in paths) \
            or "src/main.rs" in paths:
        ev.append("CLI entry point (bin / project.scripts / cmd / main.rs)")
        return "cli", ev
    if any(p.endswith((".xcodeproj/project.pbxproj", "tauri.conf.json")) for p in paths) or "electron" in deps:
        return "app", ["app project (Xcode / Tauri / Electron)"]
    if any(p.endswith(("AGENTS.md", ".cursorrules", "CLAUDE.md")) for p in paths) and len(code) < 5:
        return "rules", ["agent instruction files without code"]
    if pkg or pyproj or "Cargo.toml" in files or "go.mod" in files or "Package.swift" in files:
        return "library", ["package manifest without an entry point"]
    if len(code) < 5:
        return "example", [f"{len(code)} code files"]
    return "library", ["code without a manifest the tool recognises"]


def _json(text: str | None) -> dict:
    try:
        v = json.loads(text) if text else {}
        return v if isinstance(v, dict) else {}
    except ValueError:
        return {}


def clean_readme(text: str, limit: int) -> str:
    lines = []
    in_code = False
    for line in text.splitlines():
        s = line.rstrip()
        if s.strip().startswith("```"):
            in_code = not in_code
        if not in_code:
            if re.match(r"^\s*(<p|</p|<div|</div|<img|<a |<br|<picture|</picture|<source|<h\d|</h\d|<!--|-->)", s):
                continue
            s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)                       # images
            s = re.sub(r"\[\s*\]\([^)]*\)", "", s)                             # empty links left by badges
            s = re.sub(r"<[^>]+>", "", s)
            if not s.strip() and (not lines or not lines[-1].strip()):
                continue
        lines.append(s)
    out = "\n".join(lines).strip()
    return out if len(out) <= limit else out[:limit].rsplit("\n", 1)[0] + "\n[... README cut; reuse-first peek --readme N for more]"


def tree_summary(paths: list[tuple[str, int]], depth: int = 1, width: int = 14) -> list[str]:
    files = Counter()
    size = Counter()
    for p, s in paths:
        parts = p.split("/")
        key = "/".join(parts[:depth]) + ("/" if len(parts) > depth else "")
        files[key] += 1
        size[key] += s
    rows = sorted(files, key=lambda k: (-size[k], k))
    out = [f"{k} {files[k]}f ~{_tok(size[k])}" if k.endswith("/") else f"{k} ~{_tok(size[k])}" for k in rows[:width]]
    if len(rows) > width:
        out.append(f"+{len(rows) - width} more")
    return out


def _tok(nbytes: int) -> str:
    t = nbytes // 4
    return f"{t / 1000:.0f}k tok" if t >= 1000 else f"{t} tok"


def peek(client: Client, slug: str, readme_chars: int = 2500) -> dict:
    r = client.repo(slug)
    if not r:
        raise LookupError(f"{slug}: not found")
    slug = r["full_name"]
    branch = r.get("default_branch") or "main"
    sha = client.head(slug, branch) or branch
    tree = client.tree(slug, sha) or {}
    entries = [(e["path"], int(e.get("size") or 0)) for e in tree.get("tree", []) if e.get("type") == "blob"]
    paths = [p for p, _ in entries]
    files = {}
    for m in MANIFESTS:
        if m in paths and m not in ("AGENTS.md", "CLAUDE.md", "Dockerfile"):
            files[m] = client.file(slug, m, sha) or ""
    readme = client.readme(slug, sha) or ""
    kind, evidence = guess_kind(paths, files, r["name"], readme)
    rel = client.latest_release(slug)
    skills = [p for p in paths if p.endswith("SKILL.md")]
    pkg = _json(files.get("package.json"))
    return {
        "repo": slug, "url": r.get("html_url") or f"https://github.com/{slug}",
        "desc": r.get("description") or "", "homepage": r.get("homepage") or "",
        "stars": r.get("stargazers_count", 0), "forks": r.get("forks_count", 0),
        "open_issues": r.get("open_issues_count", 0),
        "created": (r.get("created_at") or "")[:10], "pushed": (r.get("pushed_at") or "")[:10],
        "license": (r.get("license") or {}).get("spdx_id"), "archived": r.get("archived", False),
        "lang": r.get("language"), "topics": r.get("topics", []), "branch": branch, "commit": sha[:12],
        "release": {"tag": rel.get("tag_name"), "date": (rel.get("published_at") or "")[:10]} if rel else None,
        "kind": kind, "evidence": evidence, "files": len(paths), "truncated": bool(tree.get("truncated")),
        "tree": tree_summary(entries), "skills": skills[:15],
        "manifests": [m for m in MANIFESTS if m in paths],
        "package": {k: pkg[k] for k in ("name", "version", "bin") if k in pkg} if pkg else None,
        "readme": clean_readme(readme, readme_chars),
    }


def render_peek(p: dict) -> str:
    lines = [f"## {p['repo']}  ({p['kind']}?)  {p['url']}",
             f"{p['desc']}",
             f"stars {p['stars']} · forks {p['forks']} · issues {p['open_issues']} · created {p['created']} · pushed {p['pushed']}"
             f" · license {p['license'] or 'none'} · {p['lang'] or '-'}" + (" · ARCHIVED" if p["archived"] else ""),
             f"head {p['branch']}@{p['commit']}" + (f" · release {p['release']['tag']} {p['release']['date']}" if p["release"] else " · no releases"),
             f"kind evidence: {'; '.join(p['evidence'])}"]
    if p["topics"]:
        lines.append("topics: " + ", ".join(p["topics"][:10]))
    if p["package"]:
        lines.append("package: " + json.dumps(p["package"], ensure_ascii=False)[:200])
    lines.append(f"tree ({p['files']} files{', truncated' if p['truncated'] else ''}): " + " | ".join(p["tree"]))
    if p["skills"]:
        lines.append("skills: " + ", ".join(p["skills"]))
    if p["manifests"]:
        lines.append("manifests: " + ", ".join(p["manifests"]))
    lines += ["README:", p["readme"]]
    return "\n".join(lines)


def digest(root: Path, width: int = 20) -> str:
    """Where the code is in a fetched tree, with sizes in estimated tokens."""
    entries: list[tuple[str, int]] = []
    for path in root.rglob("*"):
        if path.is_file() and not any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            entries.append((str(path.relative_to(root)), path.stat().st_size))
    total = sum(s for _, s in entries)
    text = [(p, s) for p, s in entries if Path(p).suffix.lower() in TEXT_EXT]
    lines = [f"{root}", f"{len(entries)} files, ~{_tok(total)} total, ~{_tok(sum(s for _, s in text))} in text/code"]
    lines.append("top level: " + " | ".join(tree_summary(entries, 1, width)))
    by_dir = defaultdict(int)
    for p, s in text:
        by_dir[str(Path(p).parent)] += s
    big = sorted(by_dir.items(), key=lambda kv: -kv[1])[:12]
    lines.append("largest code dirs: " + " | ".join(f"{d} ~{_tok(s)}" for d, s in big))
    entry = [p for p, _ in entries if re.search(r"(^|/)(SKILL\.md|README\.md|main\.\w+|index\.\w+|cli\.\w+|__main__\.py|server\.\w+)$", p)]
    lines.append("entry points: " + ", ".join(sorted(entry, key=lambda p: (p.count("/"), p))[:20]))
    return "\n".join(lines)


def fetch(store: Store, client: Client, slug: str, ref: str | None = None) -> Path:
    card = store.card(slug)
    slug = card.id if card else slug
    if not ref:
        ref = str(card.data.get("commit")) if card and card.data.get("commit") else None
    if not ref:
        r = client.repo(slug)
        if not r:
            raise LookupError(f"{slug}: not found")
        slug = r["full_name"]
        ref = client.head(slug, r.get("default_branch") or "main")
    else:
        full = client.get_or_none(f"repos/{slug}/commits/{ref}")
        ref = full["sha"] if full else ref
    dest = store.cache_dir(slug, ref)
    if dest.exists():
        return dest
    tmp = dest.with_name(dest.name + ".part")
    if tmp.exists():
        raise RuntimeError(f"an earlier download did not finish: {tmp} (move it away and retry)")
    client.tarball(slug, ref, tmp)
    tmp.rename(dest)
    return dest


def watched(paths: list[str], patterns: list[str]) -> list[str]:
    if not patterns:
        return []
    out = []
    for p in paths:
        for pat in patterns:
            pat = str(pat)
            if fnmatch.fnmatch(p, pat) or p == pat or (pat.endswith("/") and p.startswith(pat)) \
                    or fnmatch.fnmatch(p, pat.rstrip("/") + "/*") or (pat.endswith("/**") and p.startswith(pat[:-2])):
                out.append(p)
                break
    return out


def outdated(store: Store, client: Client, refs: list[str] | None = None, project: str | None = None) -> list[dict]:
    rows = []
    for card in store.cards():
        if card.error:
            continue
        d = card.data
        if refs and card.id.lower() not in {x.lower() for x in refs} and not set(map(str.lower, map(str, as_list(d.get("aliases"))))) & {x.lower() for x in refs}:
            continue
        if project and not any(isinstance(u, dict) and u.get("project") == project for u in as_list(d.get("uses"))):
            continue
        slug = card.id
        row = {"repo": slug, "reviewed": d.get("reviewed"), "commit": str(d.get("commit") or "")}
        r = client.repo(slug)
        if not r:
            row["state"] = "gone (404: deleted, renamed or private)"
            rows.append(row)
            continue
        row["stars"], row["stars_then"] = r.get("stargazers_count", 0), d.get("stars")
        if r["full_name"].lower() != slug.lower():
            row["renamed"] = r["full_name"]
        lic = (r.get("license") or {}).get("spdx_id")
        if lic and d.get("license") and lic != d.get("license") and lic != "NOASSERTION":
            row["license_changed"] = f"{d.get('license')} -> {lic}"
        if r.get("archived"):
            row["archived"] = True
        branch = d.get("branch") or r.get("default_branch") or "main"
        cmp = client.compare(r["full_name"], row["commit"], branch) if row["commit"] else None
        if cmp is None:
            row["state"] = "cannot compare (commit not on branch?)"
        else:
            row["ahead"] = cmp.get("ahead_by", 0)
            files = [f["filename"] for f in cmp.get("files", [])]
            row["files_changed"] = len(files)
            row["watched_changed"] = watched(files, as_list(d.get("watch")))
            row["head"] = (cmp.get("commits") or [{}])[-1].get("sha", "")[:12] if cmp.get("commits") else row["commit"]
        rels = [x for x in client.releases(r["full_name"]) if (x.get("published_at") or "")[:10] > str(d.get("reviewed") or "")]
        row["releases"] = [x.get("tag_name") for x in rels][:6]
        if row.get("ahead", 0) == 0 and not row["releases"] and not row.get("archived") and not row.get("license_changed"):
            row["state"] = "up to date"
        elif row.get("watched_changed") or row.get("archived") or row.get("license_changed"):
            row["state"] = "review"
        elif row.get("ahead") or row["releases"]:
            row["state"] = "changed (not in watched paths)" if as_list(d.get("watch")) else "changed (card watches no paths)"
        rows.append(row)
    return rows


def render_outdated(rows: list[dict]) -> str:
    out = []
    order = {"review": 0, "gone (404: deleted, renamed or private)": 0}
    for r in sorted(rows, key=lambda r: (order.get(r.get("state", ""), 1), r["repo"])):
        bits = [r.get("state", "?")]
        if r.get("ahead"):
            bits.append(f"{r['ahead']} commits, {r.get('files_changed', 0)} files")
        if r.get("watched_changed"):
            w = r["watched_changed"]
            bits.append("watched: " + ", ".join(w[:5]) + (f" +{len(w) - 5}" if len(w) > 5 else ""))
        if r.get("releases"):
            bits.append("releases " + ", ".join(r["releases"]))
        for k in ("archived", "license_changed", "renamed"):
            if r.get(k):
                bits.append(f"{k}: {r[k]}" if r[k] is not True else k)
        if r.get("stars") and r.get("stars_then"):
            bits.append(f"stars {r['stars_then']}->{r['stars']}")
        out.append(f"{r['repo']:<40} reviewed {r.get('reviewed')}: " + " · ".join(bits))
    return "\n".join(out) or "no cards matched"


def diff(store: Store, client: Client, slug: str, every_file: bool = False, max_lines: int = 400) -> str:
    card = store.card(slug)
    if not card:
        raise LookupError(f"{slug}: no card")
    d = card.data
    r = client.repo(card.id)
    if not r:
        raise LookupError(f"{card.id}: not found upstream")
    branch = d.get("branch") or r.get("default_branch") or "main"
    cmp = client.compare(r["full_name"], str(d.get("commit")), branch)
    if not cmp:
        raise LookupError(f"cannot compare {d.get('commit')}...{branch}")
    files = cmp.get("files", [])
    names = [f["filename"] for f in files]
    keep = set(names if every_file or not as_list(d.get("watch")) else watched(names, as_list(d.get("watch"))))
    out = [f"{card.id} {str(d.get('commit'))[:12]}...{branch}: {cmp.get('ahead_by', 0)} commits, {len(files)} files; "
           f"showing {len(keep)}" + ("" if every_file else " watched") + " file(s)",
           f"compare: https://github.com/{r['full_name']}/compare/{d.get('commit')}...{branch}"]
    msgs = [c["commit"]["message"].split("\n", 1)[0] for c in cmp.get("commits", [])][-15:]
    if msgs:
        out.append("commits (latest 15): " + " | ".join(m[:80] for m in msgs))
    budget = max_lines
    for f in files:
        if f["filename"] not in keep:
            continue
        patch = (f.get("patch") or "(binary or too large; open the compare link)").splitlines()
        out.append(f"--- {f['filename']} ({f.get('status')}, +{f.get('additions')} -{f.get('deletions')})")
        out.extend(patch[:budget])
        budget -= len(patch[:budget])
        if budget <= 0:
            out.append(f"[... cut at {max_lines} lines; --max-lines N]")
            break
    return "\n".join(out)


def bump(store: Store, client: Client, slug: str, to: str | None = None) -> dict:
    card = store.card(slug)
    if not card:
        raise LookupError(f"{slug}: no card")
    r = client.repo(card.id)
    if not r:
        raise LookupError(f"{card.id}: not found upstream")
    branch = card.data.get("branch") or r.get("default_branch") or "main"
    sha = to or client.head(r["full_name"], branch)
    old = card.data.get("commit")
    card.data.update(commit=str(sha)[:12], reviewed=today(), stars=r.get("stargazers_count", 0),
                     pushed=(r.get("pushed_at") or "")[:10])
    lic = (r.get("license") or {}).get("spdx_id")
    if lic and lic != "NOASSERTION":
        card.data["license"] = lic
    store.save_card(card)
    return {"repo": card.id, "from": old, "to": card.data["commit"]}
