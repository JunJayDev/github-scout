"""Looking at a repository as cheaply as possible, and checking it again later.

peek   ~1-1.5k tokens: facts, kind guess with evidence, tree summary, manifests, the start
       of the README, and the verifiable effect (strong, mid or weak, with the links to open:
       a live site checked with one short request, npm downloads, media in the README).
fetch  download one commit's source into the cache and print a digest that
       says where the code is and how big each part is, so reading can be targeted.
outdated / diff  what changed upstream since the commit a card was reviewed at,
       narrowed to the paths the card watches; for repos adopted into a project, the
       commits that touched each upstream file we took since the commit we took it at.
"""

from __future__ import annotations

import fnmatch
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from .github import Client, GitHubError
from .discover import DROP, HIDE, SLOW, human, months_since
from .store import INSTALLS_REAL, SHA, Store, adoptions, as_list, min_stars, repo_ref, today

MANIFESTS = ["package.json", "pyproject.toml", "setup.py", "Cargo.toml", "go.mod", "Package.swift",
             ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json", "manifest.json", "action.yml",
             "Dockerfile", "docker-compose.yml", "mcp.json", "smithery.yaml", "AGENTS.md", "CLAUDE.md"]
SKIP_DIRS = {".git", "node_modules", "dist", "build", "vendor", "__pycache__", ".venv", "venv", "target",
             ".next", "coverage"}
TEXT_EXT = {".md", ".txt", ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".go", ".rs", ".swift", ".rb",
            ".java", ".kt", ".c", ".h", ".cpp", ".cs", ".php", ".sh", ".json", ".yaml", ".yml", ".toml", ".html",
            ".css", ".vue", ".svelte", ".lua", ".sql"}


FORM_KIND = {"skill": "skill", "skill-pack": "skill", "rules": "skill", "list": "list", "example": "other",
             "data": "other"}


def kind_of(form: str) -> str:
    """The four kinds the registry uses: skill, software, list, other."""
    return FORM_KIND.get(form, "software")


def guess_kind(paths: list[str], files: dict[str, str], name: str, readme: str, desc: str = "") -> tuple[str, list[str]]:
    """Best guess of a repo's form (cli, mcp, skill-pack, ...) from its tree and manifests, with the evidence."""
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
    entry = bool(pkg.get("bin")) or "[project.scripts]" in pyproj or "Cargo.toml" in files \
        or any(p.startswith("cmd/") for p in paths) or "main.go" in paths or "src/main.rs" in paths
    if skills:
        ev.append(f"{len(skills)} SKILL.md: " + ", ".join(skills[:4]) + (" ..." if len(skills) > 4 else ""))
        plugin = any(p.startswith(".claude-plugin/") for p in paths)
        if plugin:
            ev.append(".claude-plugin manifest")
        # A real code base that also ships skills is software, unless it presents itself as a skill.
        says_skill = bool(re.search(r"\bskills?\b", (name.replace("-", " ") + " " + desc + " " + (readme or "")[:600]).lower()))
        if says_skill:
            ev.append("calls itself a skill")
        if entry or (len(code) > 150 and not says_skill):
            ev.append(f"{len(code)} code files" + (" and a CLI entry point" if entry else "") + ": software that ships skills")
        else:
            return ("skill-pack" if len(skills) > 1 or plugin else "skill"), ev
    mf = _json(files.get("manifest.json"))
    if mf.get("manifest_version"):
        return "extension", [f"browser extension manifest v{mf['manifest_version']}"]
    if entry:
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


# What a repo shows of what it does (owner, 2026-10-19). Most show it outside the repo, so `look` grades it:
#   strong  a live site that answers (the repo's homepage, a demo or app link in the README), an npm package with
#           real downloads, real installs recorded by the scan (skills.sh)
#   mid     screenshots, GIFs or videos in the README (badges, logos and icons left out)
#   weak    none of these: only a text description
# Posts outside the repo (X, Bilibili, YouTube, blogs) are mid too; the agent finds them and gives them to `note`.
SITE_WORDS = re.compile(r"demo|playground|\btry\b|\blive\b|online|\bapp\b|website|homepage|gallery|showcase|preview|"
                        r"在线|体验|演示|试用|官网|作品|展示|案例", re.I)
NOT_EFFECT = re.compile(r"shields\.io|badgen\.net|badge|/actions/workflows/|codecov|star-history|contrib\.rocks|trendshift|"
                        r"visitor|komarev|readme-stats|buymeacoffee|ko-fi\.com|/sponsors/|producthunt\.com/widgets", re.I)
SMALL_PART = re.compile(r"(?<![a-z])(logo|logos|icon|icons|badge|badges|avatar|favicon|emoji|qr|qrcode|wechat|weixin|"
                        r"alipay|wxpay|donate|donation|sponsors?|discord)(?![a-z])", re.I)   # and QR codes to join a group
TINY = re.compile(r"[?&](?:s|size|w|width|h|height)=(\d+)|/(\d{1,2})x\d{1,2}/", re.I)
IMAGE = re.compile(r"\.(png|jpe?g|webp|gif|avif)(?:[?#]|$)", re.I)
VIDEO = re.compile(r"\.(mp4|webm|mov|m4v)(?:[?#]|$)|github\.com/user-attachments/assets/|"
                   r"(?:^|//)(?:www\.)?(youtube\.com/watch|youtu\.be/|bilibili\.com/video|b23\.tv/|vimeo\.com/\d|loom\.com/share)",
                   re.I)
GITHUB_HOSTS = re.compile(r"^https?://(?:[^/]*\.)?(github\.com|githubusercontent\.com)/", re.I)
SITES_PROBED, MEDIA_SHOWN, NPM_REAL = 3, 4, 100   # live sites checked per repo; media links printed; npm downloads a
                                                  # month that count as real use


def _absolute(url: str, slug: str, branch: str) -> str:
    if url.startswith(("http://", "https://")):
        return url
    path = re.sub(r"^(?:\./)+", "", url).lstrip("/")
    return f"https://github.com/{slug}/blob/{branch}/{path}"


def _small(url: str, alt: str = "", width: str = "", height: str = "") -> bool:
    """A badge, logo, icon or QR code rather than a picture of what it does: by host, name, alt text or a tiny size."""
    name = url.split("?")[0].split("#")[0].rstrip("/").rsplit("/", 1)[-1]
    if NOT_EFFECT.search(url) or SMALL_PART.search(name) or SMALL_PART.search(alt):
        return True
    sizes = [int(x) for x in (width, height) if x.isdigit()]
    sizes += [int(g) for m in TINY.finditer(url) for g in m.groups() if g]
    return any(n <= 64 for n in sizes)


def readme_effect(readme: str, slug: str, branch: str) -> tuple[list[dict], list[str]]:
    """From a README: media that shows what it does (mid), and links that may be its live site, for `look` to check.
    Relative links point into the repo."""
    media: list[dict] = []
    sites: list[str] = []

    def add_media(url: str, alt: str = "", width: str = "", height: str = "") -> None:
        if url.startswith(("#", "mailto:", "data:")) or _small(url, alt, width, height):
            return
        kind = "video" if VIDEO.search(url) else "image" if IMAGE.search(url) else None
        url = _absolute(url, slug, branch)
        if kind and url not in {m["url"] for m in media}:
            media.append({"what": kind, "url": url})

    def add_site(text: str, url: str) -> None:
        if (url.startswith(("http://", "https://")) and not GITHUB_HOSTS.match(url) and not NOT_EFFECT.search(url)
                and not IMAGE.search(url) and (SITE_WORDS.search(text) or SITE_WORDS.search(url.split("?")[0]))
                and url not in sites):
            sites.append(url)

    for alt, url, link in re.findall(r"\[!\[([^\]]*)\]\(\s*<?([^)\s>]+)[^)]*\)\]\(\s*<?([^)\s>]+)", readme):
        add_media(url, alt)                                     # a picture linked to its demo: both count
        add_site(alt, link)
    for alt, url in re.findall(r"!\[([^\]]*)\]\(\s*<?([^)\s>]+)", readme):
        add_media(url, alt)
    for tag in re.findall(r"<(?:img|video|source)\b[^>]*>", readme, re.I):
        attr = dict((k.lower(), v) for k, v in re.findall(r"\b(\w+)\s*=\s*[\"']([^\"']*)[\"']", tag))
        if attr.get("src"):
            add_media(attr["src"], attr.get("alt", ""), attr.get("width", ""), attr.get("height", ""))
    for text, url in re.findall(r"(?<!!)\[([^\]]*)\]\(\s*<?([^)\s>]+)>?[^)]*\)", readme):
        if VIDEO.search(url):
            add_media(url, text)
        else:
            add_site(text, url)
    for url in re.findall(r"(?m)^\s*(https?://\S+)\s*$", readme):     # a bare link on its own line: GitHub embeds videos
        if VIDEO.search(url):
            add_media(url)
        else:
            add_site("", url)
    for url in re.findall(r"href=[\"']([^\"']+)[\"']", readme):
        add_site("", url)
    return media, sites


def effect_of(client: Client, readme: str, slug: str, branch: str, homepage: str = "", package: str = "",
           installs: int = 0) -> dict:
    """The repo's verifiable effect: its tier, the strong and mid items, and the sites that did not answer.
    Asks the homepage and up to two README demo links whether they answer (no token, a few seconds each), and npm
    for a package's downloads."""
    media, links = readme_effect(readme, slug, branch)
    strong: list[dict] = []
    silent: list[str] = []
    home = homepage.strip() if homepage and not GITHUB_HOSTS.match(homepage.strip()) else ""
    sites = list(dict.fromkeys(([home] if home.startswith(("http://", "https://")) else []) + links))[:SITES_PROBED]
    for url in sites:
        if client.reachable(url):
            strong.append({"what": "live site" + (" (homepage)" if url == home else ""), "url": url})
        else:
            silent.append(url)
    if package:
        n = client.npm_downloads(package)
        if n is not None and n >= NPM_REAL:
            strong.append({"what": f"npm {package}: {human(n)} downloads last month",
                           "url": f"https://www.npmjs.com/package/{package}"})
    if installs >= INSTALLS_REAL:
        strong.append({"what": f"skills.sh: {human(installs)} installs", "url": ""})
    tier = "strong" if strong else "mid" if media else "weak"
    return {"tier": tier, "strong": strong, "mid": media, "silent": silent}


def render_effect(e: dict) -> list[str]:
    """`look`'s lines on the verifiable effect: the tier first, then what to open."""
    if e["tier"] == "weak":
        return ["verifiable effect: weak, only a text description (no live site, package downloads, installs or media "
                "found). Look for posts outside the repo (X, Bilibili, YouTube, blogs) before you pick; with none it is "
                "later or skip"] + ([f"  did not answer: {' '.join(e['silent'])}"] if e["silent"] else [])
    lines = [f"verifiable effect: {e['tier']}" + "".join(f" · {x['what']}" + (f" {x['url']}" if x["url"] else "")
                                                         for x in e["strong"])]
    if e["mid"]:
        kinds = {k: sum(m["what"] == k for m in e["mid"]) for k in ("image", "video")}
        what = ", ".join(f"{n} {k}{'s' if n > 1 else ''}" for k, n in kinds.items() if n)
        shown = e["mid"][:MEDIA_SHOWN]
        lines.append(f"  mid: {what} in the README: " + " ".join(m["url"] for m in shown)
                     + (f" (+{len(e['mid']) - len(shown)})" if len(e["mid"]) > len(shown) else ""))
    if e["silent"]:
        lines.append(f"  did not answer: {' '.join(e['silent'])}")
    return lines


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
    return out if len(out) <= limit else out[:limit].rsplit("\n", 1)[0] + "\n[... README cut; github-scout look --readme N for more]"


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


def peek(client: Client, slug: str, readme_chars: int = 2500, effect: bool = True, installs: int = 0) -> dict:
    """What `look` prints. With `effect`, also the verifiable effect: a few short requests outside GitHub."""
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
    kind, evidence = guess_kind(paths, files, r["name"], readme, r.get("description") or "")
    rel = client.latest_release(slug)
    import datetime as _dt
    since30 = (_dt.date.today() - _dt.timedelta(days=30)).isoformat() + "T00:00:00Z"
    commits30 = client.commits_since(slug, since30)
    releases90 = [x for x in client.releases(slug, 30)
                  if months_since((x.get("published_at") or "")[:10]) <= 3]
    people = client.contributors(slug, 10)
    total = sum(int(x.get("contributions") or 0) for x in people)
    top_share = round(100 * int(people[0].get("contributions") or 0) / total) if people and total else None
    skills = [p for p in paths if p.endswith("SKILL.md")]
    pkg = _json(files.get("package.json"))
    return {
        "repo": slug, "url": r.get("html_url") or f"https://github.com/{slug}",
        "desc": r.get("description") or "", "homepage": r.get("homepage") or "",
        "stars": r.get("stargazers_count", 0), "forks": r.get("forks_count", 0),
        "open_issues": r.get("open_issues_count", 0),
        "created": (r.get("created_at") or "")[:10], "pushed": (r.get("pushed_at") or "")[:10],
        "archived": r.get("archived", False),
        "lang": r.get("language"), "topics": r.get("topics", []), "branch": branch, "commit": sha[:12],
        "release": {"tag": rel.get("tag_name"), "date": (rel.get("published_at") or "")[:10]} if rel else None,
        "kind": kind_of(kind), "form": kind, "evidence": evidence, "files": len(paths),
        "truncated": bool(tree.get("truncated")),
        "activity": {"idle_months": round(months_since((r.get("pushed_at") or "")[:10]), 1),
                     "commits_30d": commits30, "releases_90d": len(releases90),
                     "contributors": len(people), "top_contributor_pct": top_share},
        "tree": tree_summary(entries), "skills": skills[:15],
        "manifests": [m for m in MANIFESTS if m in paths],
        "package": {k: pkg[k] for k in ("name", "version", "bin") if k in pkg} if pkg else None,
        "effect": effect_of(client, readme, slug, branch, r.get("homepage") or "",
                            str(pkg.get("name") or "") if pkg and not pkg.get("private") else "", installs)
        if effect else None,                                    # to open before picking; not on the card until noted
        "readme": clean_readme(readme, readme_chars),
    }


def maintenance(idle: float) -> str:
    if idle > DROP:
        return f"UNMAINTAINED: no push in {idle:.0f} months; excluded by rule"
    if idle > HIDE:
        return f"stale: no push in {idle:.0f} months; ignore unless nothing newer exists"
    if idle > SLOW:
        return f"slowing: no push in {idle:.0f} months"
    return "active"


def render_peek(p: dict) -> str:
    a = p["activity"]
    limit = min_stars()
    lines = [f"## {p['repo']}  ({p['kind']}: {p['form']}?)  {p['url']}",
             f"{p['desc']}",
             f"stars {p['stars']}" + ((f" (under {limit}, but {p['relaxed']} is relaxed to {p['floor']}: a reference)"
                                        if p.get("floor") and p["stars"] >= p["floor"] else
                                        f" (UNDER {limit}: no reference without a written reason)") if p["stars"] < limit else "")
             + f" · forks {p['forks']} · issues {p['open_issues']} · created {p['created']} · pushed {p['pushed']}"
             f" · {p['lang'] or '-'}" + (" · ARCHIVED" if p["archived"] else ""),
             f"head {p['branch']}@{p['commit']}" + (f" · release {p['release']['tag']} {p['release']['date']}" if p["release"] else " · no releases"),
             f"maintenance: {maintenance(a['idle_months'])} · {a['commits_30d']}{'+' if a['commits_30d'] >= 100 else ''} commits in 30 days"
             f" · {a['releases_90d']} releases in 90 days · {a['contributors']}{'+' if a['contributors'] >= 10 else ''} contributors"
             + (f", top one {a['top_contributor_pct']}% of commits" if a['top_contributor_pct'] is not None else ""),
             f"kind evidence: {'; '.join(p['evidence'])}"]
    if p.get("homepage"):
        lines.append(f"homepage: {p['homepage']}")
    if p.get("effect"):
        lines += render_effect(p["effect"])
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
            entries.append((path.relative_to(root).as_posix(), path.stat().st_size))
    total = sum(s for _, s in entries)
    text = [(p, s) for p, s in entries if Path(p).suffix.lower() in TEXT_EXT]
    lines = [f"{root}", f"{len(entries)} files, ~{_tok(total)} total, ~{_tok(sum(s for _, s in text))} in text/code"]
    lines.append("top level: " + " | ".join(tree_summary(entries, 1, width)))
    by_dir = defaultdict(int)
    for p, s in text:
        by_dir[Path(p).parent.as_posix()] += s
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


ADOPTION_FIELDS = ("project", "question", "mode", "into", "from", "at", "ours", "date")


def upstream_changes(client: Client, slug: str, branch: str, a: dict, dates: dict) -> dict:
    """What happened upstream to the files an adoption took (`from`) since the commit it took them at (`at`):
    per path, the commits on the branch that touched it since that commit's date, newest first."""
    out = {k: a[k] for k in ADOPTION_FIELDS if a.get(k)}
    at = str(a.get("at") or "")
    if not as_list(a.get("from")):
        return out
    if not at:
        out["error"] = "no upstream commit recorded (adopt --at)"
        return out
    if at not in dates:                      # one lookup per commit: "" not found, None unreachable
        try:
            c = client.commit(slug, at)
            dates[at] = (((c or {}).get("commit") or {}).get("committer") or {}).get("date") or ""
        except GitHubError as exc:
            dates[at] = "" if exc.status == 422 else None
        except OSError:
            dates[at] = None
    if not dates[at]:
        out["error"] = "upstream history unreachable" if dates[at] is None else f"commit {at[:7]} not found upstream"
        return out
    out["paths"] = []
    for path in map(str, as_list(a.get("from"))):
        try:
            hist = client.path_commits(slug, path, branch, dates[at])
        except (GitHubError, OSError):
            hist = None
        if hist is None:
            out["paths"].append({"path": path, "error": "history unreachable"})
            continue
        more = len(hist) >= 100
        hist = [c for c in hist if not str(c.get("sha", "")).startswith(at)]
        p = {"path": path, "changes": len(hist), "more": more}
        try:                                 # GitHub lists no commits for a path that is not there: say so
            if not client.exists(slug, path, branch):
                p["gone"] = branch
        except (GitHubError, OSError):
            pass
        if hist:
            c = hist[0].get("commit") or {}
            p["newest"] = {"sha": str(hist[0].get("sha", ""))[:7],
                           "date": ((c.get("committer") or c.get("author") or {}).get("date") or "")[:10],
                           "message": (c.get("message") or "").split("\n", 1)[0][:80]}
        out["paths"].append(p)
    return out


def outdated(store: Store, client: Client, refs: list[str] | None = None, project: str | None = None) -> list[dict]:
    rows = []
    wanted = {repo_ref(x).lower() for x in refs or []}
    for card in store.cards():
        if card.error:
            continue
        d = card.data
        if wanted and card.id.lower() not in wanted and not {str(a).lower() for a in as_list(d.get("aliases"))} & wanted:
            continue
        adopted = adoptions(d, project)
        if project and not adopted and not any(isinstance(u, dict) and u.get("project") == project for u in as_list(d.get("uses"))):
            continue
        slug = card.id
        row = {"repo": slug, "reviewed": d.get("reviewed"), "commit": str(d.get("commit") or "")}
        r = client.repo(slug)
        if not r:
            row["state"] = "gone (404: deleted, renamed or private)"
            if adopted:
                row["adopted"] = [{**{k: a[k] for k in ADOPTION_FIELDS if a.get(k)}, "error": "the repo is gone"}
                                  for a in adopted]
            rows.append(row)
            continue
        row["stars"], row["stars_then"] = r.get("stargazers_count", 0), d.get("stars")
        if r["full_name"].lower() != slug.lower():
            row["renamed"] = r["full_name"]
        if r.get("archived"):
            row["archived"] = True
        idle = months_since((r.get("pushed_at") or "")[:10])
        if idle > SLOW:
            row["unmaintained"] = f"no push in {idle:.0f} months"
        branch = r.get("default_branch") or d.get("branch") or "main"     # upstream may have renamed it
        if d.get("branch") and d["branch"] != branch:
            row["branch"] = f"{d['branch']} -> {branch}"
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
        if adopted:
            dates: dict = {}
            row["adopted"] = [upstream_changes(client, r["full_name"], branch, a, dates) for a in adopted]
        took_changed = any(p.get("changes") or p.get("gone") for a in row.get("adopted", []) for p in a.get("paths", []))
        if cmp is not None and row.get("ahead", 0) == 0 and not row["releases"] and not row.get("archived") \
                and not row.get("unmaintained") and not took_changed:
            row["state"] = "up to date"
        elif row.get("watched_changed") or row.get("archived") or row.get("unmaintained") or took_changed:
            row["state"] = "review"
        elif row.get("ahead") or row["releases"]:
            row["state"] = "changed (not in watched paths)" if as_list(d.get("watch")) else "changed (card watches no paths)"
        rows.append(row)
    return rows


def adoption_lines(r: dict) -> list[str]:
    """Under a repo's line, one line per adoption: what happened upstream to the files we took."""
    out = []
    for a in r.get("adopted", []):
        head = f"  adopted into {a.get('project')} ({a.get('mode')} {', '.join(map(str, as_list(a.get('into'))))})"
        at = str(a.get("at") or "")[:7]
        if a.get("error"):
            out.append(f"{head}: {a['error']}")
            continue
        if not a.get("from"):
            out.append(f"{head}: no upstream paths recorded (adopt --from), so only the line above applies")
            continue
        quiet = []
        for p in a.get("paths", []):
            if p.get("error"):
                out.append(f"{head}: upstream {p['path']}: {p['error']}")
            elif p.get("gone"):
                out.append(f"{head}: upstream {p['path']} is not on {p['gone']} any more (moved or deleted, or a wrong "
                           f"--from)" + (f"; changed {p['changes']} times since {at}" if p.get("changes") else ""))
            elif p.get("changes"):
                n, new = p["changes"], p.get("newest") or {}
                times = "once" if n == 1 else f"{n}{'+' if p.get('more') else ''} times"
                out.append(f"{head}: upstream {p['path']} changed {times} since {at} — newest {new.get('sha')} "
                           f"{new.get('date')} \"{new.get('message')}\"")
            else:
                quiet.append(p["path"])
        if quiet:
            out.append(f"{head}: upstream {', '.join(quiet)} unchanged since {at}")
    return out


def render_outdated(rows: list[dict]) -> str:
    out = []
    order = {"review": 0, "gone (404: deleted, renamed or private)": 0}
    for r in sorted(rows, key=lambda r: (not r.get("adopted"), order.get(r.get("state", ""), 1), r["repo"])):
        bits = [r.get("state", "?")]
        if r.get("ahead"):
            bits.append(f"{r['ahead']} commits, {r.get('files_changed', 0)} files")
        if r.get("watched_changed"):
            w = r["watched_changed"]
            bits.append("watched: " + ", ".join(w[:5]) + (f" +{len(w) - 5}" if len(w) > 5 else ""))
        if r.get("releases"):
            bits.append("releases " + ", ".join(r["releases"]))
        for k in ("archived", "unmaintained", "renamed"):
            if r.get(k):
                bits.append(f"{k}: {r[k]}" if r[k] is not True else k)
        if r.get("branch"):
            bits.append(f"default branch {r['branch']}")
        if r.get("stars") and r.get("stars_then") and r["stars"] != r["stars_then"]:
            bits.append(f"stars {r['stars_then']}->{r['stars']}")
        out.append(f"{r['repo']:<40} reviewed {r.get('reviewed')}: " + " · ".join(bits))
        out += adoption_lines(r)
    return "\n".join(out) or "no cards matched"


def diff(store: Store, client: Client, slug: str, every_file: bool = False, max_lines: int = 400) -> str:
    card = store.card(slug)
    if not card:
        raise LookupError(f"{slug}: no card")
    d = card.data
    r = client.repo(card.id)
    if not r:
        raise LookupError(f"{card.id}: not found upstream")
    branch = r.get("default_branch") or d.get("branch") or "main"
    cmp = client.compare(r["full_name"], str(d.get("commit")), branch)
    if not cmp:
        raise LookupError(f"cannot compare {d.get('commit')}...{branch}")
    files = cmp.get("files", [])
    names = [f["filename"] for f in files]
    patterns = as_list(d.get("watch")) + [p for a in adoptions(d) for p in as_list(a.get("from"))]   # and what we took
    keep = set(names if every_file or not patterns else watched(names, patterns))
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
    branch = r.get("default_branch") or card.data.get("branch") or "main"
    if to and not SHA.match(to.lower()):              # a tag or branch: the commit it points at
        sha = (client.commit(r["full_name"], to) or {}).get("sha")
        if not sha:
            raise LookupError(f"{card.id}: --to {to} is no commit, tag or branch upstream; the card is unchanged")
    else:
        sha = to or client.head(r["full_name"], branch)
        if not sha:
            raise LookupError(f"{card.id}: no head commit on {branch}; the card is unchanged")
    old = card.data.get("commit")
    card.data.update(branch=branch, commit=str(sha).lower()[:12], reviewed=today(), stars=r.get("stargazers_count", 0),
                     pushed=(r.get("pushed_at") or "")[:10])
    store.save_card(card)
    return {"repo": card.id, "from": old, "to": card.data["commit"]}
