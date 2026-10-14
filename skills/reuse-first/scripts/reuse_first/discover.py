"""Discovery: turn a need's vocabulary into many cheap searches, merge and rank.

Good repositories describe themselves with concrete nouns (the sites, formats
and APIs they support) and with how they work ("logged-in browser", "MCP
server"), rarely with the problem a newcomer would type ("social media
automation"). So a need lists four vocabularies and the tool crosses them:

    entities    concrete things: platforms, file formats, APIs, products
                synonyms in one item, separated by |   e.g. "xiaohongshu|小红书|rednote"
    mechanisms  how a solution would work: "logged-in browser", "chrome extension"
    forms       what shape it ships in: cli, mcp, skill, library, app
    problems    plain problem phrases, in every language you search in

Lenses (one letter each, shown next to every candidate):

    E entity        each entity term, name/description/topics, by stars
    P pair          two entities together in the README (multi-platform tools)
    M mechanism     each mechanism phrase, in name/description and in README
    C combo         mechanism x entity in the README
    Q problem       each problem phrase as typed
    T topic         GitHub topics derived from the vocabulary (+ last 12 months)
    R recent        entity / mechanism terms created in the last 12 months
    K skill code    SKILL.md files that mention an entity or mechanism
    S skills.sh     the skills.sh directory (records install counts, a usage signal)
    D MCP registry  the official MCP server registry
    N npm           npm packages whose repository is on GitHub
    U people        repos starred by the builders in people.txt and by owners of chosen repos
    G graph         GitHub repos linked from the READMEs of chosen repos
    W web / ingest  URLs you found elsewhere (web search, X, chat) fed in with `ingest`
    L list          links expanded from an awesome-list with `expand`
"""

from __future__ import annotations

import datetime as _dt
import itertools
import math
import re
import sys

from .github import Client, GitHubError, github_slug
from .store import Store, as_list, now_stamp, today

LENSES = "EPMCQTRKSDNUGWL"
LENS_NAMES = {"E": "entity", "P": "pair", "M": "mechanism", "C": "combo", "Q": "problem", "T": "topic",
              "R": "recent", "K": "skill code", "S": "skills.sh", "D": "mcp registry", "N": "npm", "U": "people", "G": "graph", "W": "web/ingest",
              "L": "list"}
DEFAULT_LENSES = "EPMCQTRKSDNUG"
KEEP = 400  # candidates saved per scan (best first); the search log is always kept whole


def groups(items) -> list[list[str]]:
    out = []
    for item in as_list(items):
        terms = [t.strip() for t in str(item).split("|") if t.strip()]
        if terms:
            out.append(terms)
    return out


def quote(term: str) -> str:
    return f'"{term}"' if re.search(r"\s", term) else term


def slugify(term: str) -> str | None:
    s = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
    return s if s and s.isascii() and len(s) <= 50 else None


def window(months: int = 12) -> str:
    d = _dt.date.today() - _dt.timedelta(days=int(months * 30.4))
    return d.isoformat()


def plan(need: dict, lenses: str = DEFAULT_LENSES, max_pairs: int = 10) -> list[dict]:
    """The searches a scan will run, cheapest-signal first. Pure: no network."""
    ents = groups(need.get("entities"))
    mechs = [g[0] for g in groups(need.get("mechanisms"))]
    forms = [g[0].lower() for g in groups(need.get("forms"))]
    probs = [g[0] for g in groups(need.get("problems"))]
    heads = [g[0] for g in ents]
    since = window(12)
    q: list[dict] = []

    def add(lens, kind, query):
        if lens in lenses and not any(x["lens"] == lens and x["query"] == query for x in q):
            q.append({"lens": lens, "kind": kind, "query": query})

    for g in ents:
        for term in g:
            add("E", "repos", quote(term))
    for a, b in itertools.islice(itertools.combinations(heads, 2), max_pairs):
        add("P", "repos", f"{quote(a)} {quote(b)} in:readme")
    for m in mechs:
        add("M", "repos", quote(m))
        add("M", "repos", f"{quote(m)} in:readme")
    for m in mechs[:3]:
        for e in heads[:3]:
            add("C", "repos", f"{quote(m)} {quote(e)} in:readme")
    for p in probs:
        add("Q", "repos", p)
    topics = [t for t in (slugify(x) for x in as_list(need.get("topics"))) if t]
    topics += [t for t in (slugify(x) for x in heads + mechs) if t and t not in topics]
    for t in topics[:10]:
        add("T", "repos", f"topic:{t}")
        add("T", "repos", f"topic:{t} created:>{since}")
    for term in (heads + mechs)[:8]:
        add("R", "repos", f"{quote(term)} in:name,description,readme created:>{since}")
    skillish = not forms or any(f in ("skill", "skills", "skill-pack", "rules", "plugin", "agent") for f in forms)
    if skillish:
        for term in (heads[:4] + mechs[:2]):
            add("K", "code", f"{quote(term)} filename:SKILL.md")
        for term in (heads[:4] + mechs[:2]):
            add("S", "skills", term)
    if not forms or "mcp" in forms:
        for term in (heads[:4] + mechs[:2]):
            add("D", "mcp", term)
    for term in (heads[:4] + mechs[:2]):
        add("N", "npm", term)
    add("U", "people", "starred by people.txt and owners of chosen repos")
    add("G", "graph", "links in READMEs of chosen repos")
    return q


def _months(since_iso: str | None) -> float:
    if not since_iso:
        return 1.0
    try:
        d = _dt.datetime.fromisoformat(since_iso.replace("Z", "+00:00")).date()
    except ValueError:
        return 1.0
    return max(1.0, (_dt.date.today() - d).days / 30.4)


def compact(r: dict) -> dict:
    lic = (r.get("license") or {}).get("spdx_id") if isinstance(r.get("license"), dict) else r.get("license")
    return {
        "repo": r["full_name"],
        "desc": (r.get("description") or "")[:200],
        "stars": int(r.get("stargazers_count") or 0),
        "created": (r.get("created_at") or "")[:10],
        "pushed": (r.get("pushed_at") or "")[:10],
        "license": None if lic in (None, "NOASSERTION") else lic,
        "lang": r.get("language"),
        "topics": (r.get("topics") or [])[:8],
        "archived": bool(r.get("archived")),
        "fork": bool(r.get("fork")),
    }


def _term_re(term: str):
    t = re.escape(term.lower())
    return re.compile(rf"(?<![a-z0-9]){t}(?![a-z0-9])") if term.isascii() else re.compile(t)


def fit(c: dict, need: dict) -> int:
    """How many vocabulary groups the repo's own name, description and topics mention.

    README-only matches do not count: big READMEs mention everything."""
    hay = " ".join([c["repo"].split("/")[1], c.get("desc") or "", " ".join(c.get("topics") or [])]).lower()
    hay += " " + hay.replace("-", " ")
    n = 0
    for key in ("entities", "mechanisms", "topics"):
        for g in groups(need.get(key)):
            if any(_term_re(t).search(hay) for t in g):
                n += 1
    for p in groups(need.get("problems")):
        words = [w for w in re.split(r"\s+", p[0].lower()) if w]
        if words and all(_term_re(w).search(hay) for w in words):
            n += 1
    return n


def is_list(c: dict) -> bool:
    name = c["repo"].split("/")[1].lower()
    desc = (c.get("desc") or "").lower()
    return name.startswith("awesome") or bool(re.search(r"\b(curated|awesome) (list|collection)|\ba (collective|curated) list", desc))


def score(c: dict, need: dict | None = None) -> float:
    stars = c.get("stars", 0)
    vel = stars / _months(c.get("created"))
    active = _months(c.get("pushed")) <= 4
    f = c.get("fit") if need is None else fit(c, need)
    f = f or 0
    s = 0.9 * math.log10(stars + 1) + 0.6 * math.log10(vel + 1) + 0.35 * len(set(c.get("lenses", [])))
    s += 1.3 * min(f, 4) - (1.2 if f == 0 else 0)
    s += 0.4 * math.log10((c.get("installs") or 0) + 1)
    if need is not None:
        forms = [g[0].lower() for g in groups(need.get("forms"))]
        hay = (c.get("desc") or "").lower() + " " + " ".join(c.get("topics") or [])
        if any(_term_re(x).search(hay) for x in forms):
            s += 0.4
    s += 0.4 if active else 0
    s -= 3 if c.get("archived") else 0
    s -= 1 if c.get("fork") else 0
    s -= 0.3 if not c.get("license") else 0
    return round(s, 2)


def vocab_terms(need: dict) -> list[str]:
    terms = []
    for key in ("entities", "mechanisms", "topics"):
        for g in groups(need.get(key)):
            terms.extend(t.lower() for t in g)
    return [t for t in terms if len(t) >= 3]


def matches_vocab(r: dict, terms: list[str]) -> bool:
    hay = " ".join([r.get("full_name") or "", r.get("description") or "", " ".join(r.get("topics") or [])]).lower()
    hay_dash = hay.replace("-", " ")
    return any(t in hay or t in hay_dash for t in terms)


GITHUB_URL = re.compile(r"github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9_.-]+)")


def slugs_in_text(text: str) -> list[str]:
    out, seen = [], set()
    for m in GITHUB_URL.finditer(text):
        slug = github_slug(f"github.com/{m.group(1)}/{m.group(2)}")
        if slug and slug.lower() not in seen:
            seen.add(slug.lower())
            out.append(slug)
    return out


class Scan:
    def __init__(self, store: Store, client: Client, project: str, need_id: str, need: dict):
        self.store, self.client = store, client
        self.project, self.need_id, self.need = project, need_id, need
        self.cands: dict[str, dict] = {}
        self.log: list[dict] = []

    def _add(self, raw: dict, lens: str):
        c = compact(raw)
        key = c["repo"].lower()
        if key not in self.cands:
            c["lenses"] = []
            self.cands[key] = c
        if lens not in self.cands[key]["lenses"]:
            self.cands[key]["lenses"].append(lens)

    def _add_slugs(self, slugs: list[str], lens: str, filter_vocab: bool = False):
        todo = [s for s in dict.fromkeys(slugs) if s.lower() not in self.cands]
        meta = self.client.graphql_repos(todo) if todo else {}
        terms = vocab_terms(self.need) if filter_vocab else []
        added = 0
        for s in slugs:
            key = s.lower()
            if key in self.cands:
                if lens not in self.cands[key]["lenses"]:
                    self.cands[key]["lenses"].append(lens)
                added += 1
                continue
            r = meta.get(key)
            if r and (not terms or matches_vocab(r, terms)):
                self._add(r, lens)
                added += 1
        return added

    def run(self, lenses: str = DEFAULT_LENSES, budget: int = 80, per_query: int = 30) -> dict:
        searches = plan(self.need, lenses)
        start = self.client.calls
        for s in searches:
            if self.client.calls - start >= budget:
                self.log.append({**s, "hits": None, "error": "skipped: budget"})
                continue
            try:
                hits = self._one(s, per_query)
                self.log.append({**s, "hits": hits})
            except GitHubError as exc:
                self.log.append({**s, "hits": None, "error": str(exc)})
            except OSError as exc:
                self.log.append({**s, "hits": None, "error": f"network: {exc}"})
            if self.client.verbose:
                print(f"  {s['lens']} {s['query'][:70]} -> {self.log[-1].get('hits')}", file=sys.stderr)
        return self.finish(lenses)

    def _one(self, s: dict, per_query: int) -> int:
        lens, kind, query = s["lens"], s["kind"], s["query"]
        if kind == "repos":
            items = self.client.search_repos(query, per_page=per_query)
            for r in items:
                self._add(r, lens)
            return len(items)
        if kind == "code":
            return self._add_slugs(self.client.search_code(query, per_page=per_query)[:per_query], lens)
        if kind == "npm":
            return self._add_slugs(self.client.npm_search(query)[:20], lens)
        if kind == "skills":
            found = self.client.skills_search(query)
            n = self._add_slugs([slug for slug, _, _ in found], lens)
            for slug, installs, _ in found:
                c = self.cands.get(slug.lower())
                if c is not None:
                    c["installs"] = max(c.get("installs") or 0, installs)
            return n
        if kind == "mcp":
            return self._add_slugs(self.client.mcp_search(query), lens)
        if kind == "people":
            logins = list(dict.fromkeys(self.store.people() + [c.split("/")[0] for c in as_list(self.need.get("chosen"))]))
            terms = vocab_terms(self.need)
            n = 0
            for login in logins[:20]:
                for r in self.client.starred(login, pages=3):
                    if matches_vocab(r, terms):
                        self._add(r, lens)
                        n += 1
            return n
        if kind == "graph":
            slugs: list[str] = []
            for chosen in as_list(self.need.get("chosen"))[:5]:
                text = self.client.readme(str(chosen)) or ""
                slugs += [x for x in slugs_in_text(text) if x.lower() != str(chosen).lower()]
            return self._add_slugs(slugs[:80], lens)
        raise ValueError(kind)

    def finish(self, lenses: str) -> dict:
        for c in self.cands.values():
            c["lenses"] = sorted(c["lenses"], key=LENSES.index)
            c["fit"] = fit(c, self.need)
            c["score"] = score(c, self.need)
            if is_list(c):
                c["list"] = True
        ranked = sorted(self.cands.values(), key=lambda c: (-c["score"], -c["stars"]))[:KEEP]
        scan = {
            "id": now_stamp(), "date": today(), "project": self.project, "need": self.need_id,
            "lenses": lenses, "searches": self.log, "candidates": ranked,
        }
        return scan


def annotate(store: Store, scan: dict) -> dict:
    """Mark candidates already carded or triaged so nobody re-reads them."""
    verdicts = store.verdicts()
    ref = f"{scan['project']}/{scan['need']}"
    carded = {c.id.lower(): c for c in store.cards() if not c.error}
    for c in scan["candidates"]:
        key = c["repo"].lower()
        c.pop("card", None), c.pop("seen", None)
        if key in carded:
            rels = [f"{u.get('project')}/{u.get('need') or '-'}:{u.get('relation')}"
                    for u in as_list(carded[key].data.get("uses")) if isinstance(u, dict)]
            c["card"] = ", ".join(rels) or "card"
            continue
        here = verdicts.get((key, ref))
        other = [e for (k, r), e in verdicts.items() if k == key and r != ref]
        if here:
            c["seen"] = {"verdict": here["verdict"], "date": here.get("date"), "stars": here.get("stars"),
                         "reason": here.get("reason"), "here": True}
            # Resurface a skipped repo that has grown a lot since.
            then = here.get("stars") or 0
            if here["verdict"] == "skip" and c["stars"] >= max(2 * then, then + 200):
                c["seen"]["resurfaced"] = True
        elif other:
            e = max(other, key=lambda e: e.get("date") or "")
            c["seen"] = {"verdict": e["verdict"], "date": e.get("date"), "need": f"{e.get('project')}/{e.get('need')}",
                         "reason": e.get("reason"), "here": False}
    return scan


def is_open(c: dict) -> bool:
    """Still needs a look for this need."""
    if c.get("card"):
        return False
    seen = c.get("seen")
    if not seen or not seen.get("here"):
        return True
    return bool(seen.get("resurfaced")) or seen["verdict"] in ("peeked", "short", "defer", "list")


def visible(scan: dict, show_all: bool = False) -> list[dict]:
    """Rows `render` numbers; `triage` resolves numbers against the same list."""
    return [c for c in scan["candidates"] if (show_all or is_open(c)) and not c.get("list") and not c.get("card")]


def rescore(scan: dict, need: dict) -> dict:
    for c in scan["candidates"]:
        c["fit"] = fit(c, need)
        c["score"] = score(c, need)
        c["list"] = is_list(c) or None
        if not c["list"]:
            c.pop("list")
    scan["candidates"].sort(key=lambda c: (-c["score"], -c["stars"]))
    return scan


def human(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def row(i: int, c: dict) -> str:
    vel = c["stars"] / _months(c.get("created"))
    flags = []
    if c.get("archived"):
        flags.append("ARCHIVED")
    if c.get("fork"):
        flags.append("fork")
    seen = c.get("seen")
    if seen and not seen.get("here"):
        flags.append(f"seen:{seen['verdict']}@{seen.get('need')}")
    elif seen:
        flags.append(f"{seen['verdict']}" + (" (grew, look again)" if seen.get("resurfaced") else ""))
    desc = re.sub(r"\s+", " ", c.get("desc") or "")[:90]
    if c.get("installs"):
        flags.insert(0, f"installs {human(c['installs'])}")
    flags.insert(0, f"fit {c.get('fit', 0)}")
    return (f"{i:>3}. {c['score']:>5.1f} {human(c['stars']):>6} {human(int(vel)) + '/mo':>8} {c.get('pushed', '')[2:]:>8}"
            f"  {(c.get('license') or '-')[:12]:<12} {c['repo']}  {desc}  [{''.join(c['lenses'])}]"
            + (f"  {' '.join(flags)}" if flags else ""))


def render(scan: dict, top: int = 40, show_all: bool = False) -> str:
    out = [f"scan {scan['project']}/{scan['need']} {scan['id']}: {len(scan['searches'])} searches, "
           f"{len(scan['candidates'])} repos"]
    by_lens: dict[str, list[int]] = {}
    errors = []
    for s in scan["searches"]:
        by_lens.setdefault(s["lens"], []).append(s.get("hits") or 0)
        if s.get("error"):
            errors.append(f"{s['lens']} {s['query'][:60]}: {s['error']}")
    out.append("lenses: " + "  ".join(f"{l}={sum(v)}" for l, v in sorted(by_lens.items(), key=lambda kv: LENSES.index(kv[0]))))
    if errors:
        out.append(f"errors ({len(errors)}): " + "; ".join(errors[:4]) + (" ..." if len(errors) > 4 else ""))
    carded = [c for c in scan["candidates"] if c.get("card")]
    if carded:
        out.append("already in the registry: " + "; ".join(f"{c['repo']} ({c['card']})" for c in carded[:12]))
    lists = [c for c in scan["candidates"] if c.get("list") and is_open(c)]
    if lists:
        out.append("lists to expand (reuse-first expand <need> <list>): "
                   + ", ".join(f"{c['repo']} ({human(c['stars'])})" for c in lists[:8]))
    rows = visible(scan, show_all)
    hidden = len([c for c in scan["candidates"] if not c.get("list") and not c.get("card")]) - len(rows)
    out.append(f"  #  score  stars   stars/mo  pushed  license      repo  description  [lenses]  (fit = vocabulary groups in name/description/topics)"
               + (f"   ({hidden} already triaged for this need hidden; --all shows them)" if hidden else ""))
    for i, c in enumerate(rows[:top], 1):
        out.append(row(i, c))
    if len(rows) > top:
        out.append(f"... {len(rows) - top} more (--top N)")
    return "\n".join(out)
