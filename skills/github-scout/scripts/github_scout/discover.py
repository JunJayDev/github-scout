"""Discovery: turn a question's vocabulary into many cheap searches, merge and rank.

Good repositories describe themselves with concrete nouns (the sites, formats and APIs
they support) and with how they work ("logged-in browser", "MCP server"), rarely with the
problem a newcomer would type ("social media automation"). So a question lists four
vocabularies and the tool crosses them:

    entities    concrete things: platforms, file formats, APIs, products
                synonyms in one item, separated by |   e.g. "xiaohongshu|小红书|rednote"
    mechanisms  how a solution would work: "logged-in browser", "chrome extension"
    forms       what shape it ships in: cli, mcp, skill, library, app
    problems    short problem phrases, in every language you search in

Every entity and mechanism group should carry a term in each language of the question's `langs`
(default en and zh: in real runs Chinese projects supplied half of the repos picked). Terms are
told apart by script. Pairs and combos are built per language, and the capped lenses take turns
between languages, so each language gets a fair share of the searches. Topics (T) and the MCP
registry (D) take Latin-script terms only: both are ASCII names.

Lenses (one letter each, kept with every candidate):

    E entity        each entity term, name/description/topics, by stars
    P pair          two entities of one language together in the README (multi-platform tools)
    M mechanism     each mechanism phrase in name/description; the leading ones also in README
    C combo         mechanism x entity of one language in the README
    Q problem       each problem phrase as typed
    T topic         GitHub topics derived from the vocabulary (+ last 12 months)
    R recent        entity / mechanism terms created in the last 12 months
    H rising        no vocabulary: repos created in the last 2 months in the question's form
                    (skill or MCP topics, or any repo past 500 stars in a month), most stars first.
                    A repo says what it makes, not every use people find for it, so words miss
                    some of the best new ones. Those that match no vocabulary are listed apart
                    for the agent to judge by description (`h1`, `h2`... in `pick`).
    K skill code    SKILL.md files that mention an entity or mechanism
    S skills.sh     the skills.sh directory (records install counts, a usage signal)
    D MCP registry  the official MCP server registry
    N npm           npm packages whose repository is on GitHub
    U people        repos starred by the builders in people.txt and by owners of picked/shortlisted repos
    G graph         GitHub repos linked from the READMEs of picked/shortlisted repos
                    (U and G find nothing before you pick: rerun `scan <q> --lenses UG` after picking)
    W web / add     links found elsewhere (web search, X, chat), fed in with `scan --add`
    L list          links expanded from an awesome list with `scan --expand`

Ranking favours what is relevant and alive over what is famous: in the agent era, a repo
created this year and pushed this week usually beats an older one with ten times the stars.
Maintenance is a hard rule, by the last push:

    over 3 months   ranked far down
    over 6 months   hidden by default (`--all` shows them); GitHub searches ask only for newer ones
    over 12 months  dropped: not saved, not shown, no verdict needed
"""

from __future__ import annotations

import datetime as _dt
import itertools
import math
import re
import sys

from .github import Client, GitHubError, github_slug
from .store import HAN, Store, as_list, groups, lang_of, now_stamp, question_langs, today

LENSES = "EPMCQTRHKSDNUGWL"
LENS_NAMES = {"E": "entity", "P": "pair", "M": "mechanism", "C": "combo", "Q": "problem", "T": "topic",
              "R": "recent", "H": "rising", "K": "skill code", "S": "skills.sh", "D": "mcp registry", "N": "npm", "U": "people",
              "G": "graph", "W": "web/add", "L": "list"}
DEFAULT_LENSES = "EPMCQTRHKSDNUG"
KEEP = 400  # candidates saved per scan (best first); the search log is always kept whole
SKILL_FORMS = ("skill", "skills", "skill-pack", "rules", "plugin", "agent")
RISE_TOPICS = {"skill": ("agent-skill", "agent-skills", "claude-skills", "claude-skill", "claude-code-skill", "skills"),
               "mcp": ("mcp-server", "mcp")}
RISE_MONTHS, RISE_STARS = 2, 50          # H: created in the last 2 months, past 50 stars, in the form's topics
BREAKOUT_MONTHS, BREAKOUT_STARS = 1, 500  # H for other forms: any repo past 500 stars within a month
RISE_KEEP, RISE_SHOW = 300, 30           # rising repos kept beyond KEEP; rows shown apart
RISE_TOPIC_SET = {t for ts in RISE_TOPICS.values() for t in ts}
SLOW, HIDE, DROP = 3, 6, 12  # months since the last push: penalised, hidden by default, dropped


def quote(term: str) -> str:
    return f'"{term}"' if re.search(r"\s", term) else term


def slugify(term: str) -> str | None:
    s = re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")
    return s if s and s.isascii() and len(s) <= 50 else None


def window(months: int = 12) -> str:
    return (_dt.date.today() - _dt.timedelta(days=int(months * 30.4))).isoformat()


def _in(gs: list[list[str]], lang: str) -> list[list[str]]:
    """The groups that have terms in `lang`, cut down to those terms."""
    return [x for x in ([t for t in g if lang_of(t) == lang] for g in gs) if x]


def _breadth(gs: list[list[str]]) -> list[str]:
    """First terms of every group, then second terms, and so on: a capped lens reaches more groups."""
    return [g[i] for i in range(max(map(len, gs), default=0)) for g in gs if i < len(g)]


def _turns(lists: list[list], limit: int | None = None) -> list:
    """Round robin over the lists, without repeats: each language gets a fair share of the slots,
    and a language that runs out leaves its slots to the others."""
    out: list = []
    for row in itertools.zip_longest(*lists):
        for x in row:
            if x is not None and x not in out:
                out.append(x)
    return out[:limit] if limit is not None else out


def _in_order(lists: list[list], limit: int | None = None) -> list:
    """The first language's items first; the others only fill the slots it leaves."""
    out = list(dict.fromkeys(x for row in lists for x in row))
    return out[:limit] if limit is not None else out


def _top_first(a: list, b: list | None = None) -> list[tuple]:
    """Pairs ordered so the leading items meet first: (0,1) (0,2) (1,2) (0,3)... or, from two lists,
    (0,0) (0,1) (1,0) (1,1) (0,2)..."""
    if b is None:
        return [(a[i], a[j]) for j in range(1, len(a)) for i in range(j)]
    return sorted(((x, y) for x in a for y in b), key=lambda p: (max(a.index(p[0]), b.index(p[1])), a.index(p[0])))


def vocab_langs(q: dict) -> list[str]:
    """The question's languages, then any other language its vocabulary is written in."""
    terms = [t for key in ("entities", "mechanisms") for g in groups(q.get(key)) for t in g]
    return list(dict.fromkeys(question_langs(q) + [lang_of(t) for t in terms]))


def plan(q: dict, lenses: str = DEFAULT_LENSES, max_pairs: int = 15, max_combos: int = 9) -> list[dict]:
    """The searches a scan will run. Pure: no network.

    Every synonym in a `|` group is searched by the single-term lenses (E, M). The capped lenses
    take turns between languages (the question's `langs` first), so each gets a fair share of the
    slots. Pairs and combos are built per language from each group's first term in that language,
    never mixing languages; adding a language shares the same totals (max_pairs, max_combos)
    instead of growing them. Pairs (P) and recent (R) give the first language its full share and
    the others only what is left: replayed on three real questions, Chinese pairs and recent
    queries returned almost only noise (Chinese READMEs list the author's own social accounts),
    while Chinese mechanisms and combos found the Chinese projects that were picked."""
    langs = vocab_langs(q)
    ents = groups(q.get("entities"))
    mech_groups = groups(q.get("mechanisms"))
    forms = [g[0].lower() for g in groups(q.get("forms"))]
    probs = [g[0] for g in groups(q.get("problems"))]
    ent_terms = [t for g in ents for t in g]
    mech_terms = [t for g in mech_groups for t in g]

    def spread(gs: list[list[str]], limit: int | None = None) -> list[str]:
        return _turns([_breadth(_in(gs, lang)) for lang in langs], limit)

    def lead(limit: int, only: list[str] | None = None) -> list[str]:   # per language: first 4 entity, 2 mechanism groups
        return _turns([_breadth(_in(ents, lang)[:4] + _in(mech_groups, lang)[:2]) for lang in only or langs], limit)

    def heads(gs: list[list[str]], lang: str, n: int) -> list[str]:
        return list(dict.fromkeys(g[0] for g in _in(gs, lang)))[:n]

    since = window(12)
    alive = f" pushed:>{window(HIDE)}"
    out: list[dict] = []

    def add(lens, kind, query):
        if kind == "repos":
            query += alive
        if lens in lenses and not any(x["lens"] == lens and x["query"] == query for x in out):
            out.append({"lens": lens, "kind": kind, "query": query})

    for term in spread(ents):
        add("E", "repos", quote(term))
    for a, b in _in_order([_top_first(heads(ents, lang, 6)) for lang in langs], max_pairs):
        add("P", "repos", f"{quote(a)} {quote(b)} in:readme")
    for m in spread(mech_groups):
        add("M", "repos", quote(m))
    for m in spread(mech_groups, 10):
        add("M", "repos", f"{quote(m)} in:readme")
    for m, e in _turns([_top_first(heads(mech_groups, lang, 3), heads(ents, lang, 3)) for lang in langs], max_combos):
        add("C", "repos", f"{quote(m)} {quote(e)} in:readme")
    for p in probs:
        add("Q", "repos", p)
    topics = [t for t in (slugify(x) for x in as_list(q.get("topics"))) if t]
    topics += [t for t in (slugify(x) for x in ent_terms + mech_terms) if t and t not in topics]
    for t in topics[:12]:
        add("T", "repos", f"topic:{t}")
        add("T", "repos", f"topic:{t} created:>{since}")
    for term in _in_order([_breadth(_in(ents + mech_groups, lang)) for lang in langs], 12):
        add("R", "repos", f"{quote(term)} in:name,description,readme created:>{since}")
    rise = window(RISE_MONTHS)
    if not forms or any(f in SKILL_FORMS for f in forms):
        for t in RISE_TOPICS["skill"]:
            add("H", "repos", f"topic:{t} created:>{rise} stars:>{RISE_STARS}")
    if not forms or "mcp" in forms:
        for t in RISE_TOPICS["mcp"]:
            add("H", "repos", f"topic:{t} created:>{rise} stars:>{RISE_STARS}")
    if not forms or any(f not in SKILL_FORMS and f != "mcp" for f in forms):
        add("H", "repos", f"created:>{window(BREAKOUT_MONTHS)} stars:>{BREAKOUT_STARS}")
    if not forms or any(f in SKILL_FORMS for f in forms):
        for term in lead(10):
            add("K", "code", f"{quote(term)} filename:SKILL.md")
        for term in lead(10):
            add("S", "skills", term)
    if not forms or "mcp" in forms:
        for term in lead(8, ["en"]):          # the registry matches server names, which are ASCII
            add("D", "mcp", term)
    for term in lead(8):
        add("N", "npm", term)
    add("U", "people", "starred by people.txt and owners of picked or shortlisted repos")
    add("G", "graph", "links in READMEs of picked or shortlisted repos")
    return out


WORD_LENSES = "EPMCQRKSDN"   # lenses whose queries carry vocabulary words


def search_langs(searches: list[dict]) -> dict[str, int]:
    """Searches per language of their words; lenses without words (topics, rising, people, graph) are left out."""
    out: dict[str, int] = {}
    for s in searches:
        if s.get("lens") in WORD_LENSES:
            lang = lang_of(s.get("query") or "")
            out[lang] = out.get(lang, 0) + 1
    return out


def months_since(iso: str | None) -> float:
    if not iso:
        return 120.0
    try:
        d = _dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
    except ValueError:
        return 120.0
    return max(0.0, (_dt.date.today() - d).days / 30.4)


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


def _stem(w: str) -> str:
    for suffix, keep in (("ing", 5), ("ies", 5), ("es", 5), ("ed", 4), ("s", 3)):
        if w.endswith(suffix) and len(w) > keep:
            return w[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return w


def _tokens(text: str) -> set[str]:
    return {_stem(w) for w in re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)*", text.lower())}


def _has(term: str, hay_text: str, hay_tokens: set[str]) -> bool:
    """A term matches when all its (stemmed) words appear, in any order; non-Latin terms match as substrings."""
    if not term.isascii():
        return term.lower() in hay_text
    words = [_stem(w) for w in re.findall(r"[a-z0-9]+(?:\.[a-z0-9]+)*", term.lower())]
    return bool(words) and all(w in hay_tokens for w in words)


def _term_re(term: str):
    t = re.escape(term.lower())
    return re.compile(rf"(?<![a-z0-9]){t}(?![a-z0-9])") if term.isascii() else re.compile(t)


def fit(c: dict, q: dict) -> int:
    """How many vocabulary groups the repo's own name, description and topics mention.

    README-only matches do not count: big READMEs mention everything. Words are compared after
    light stemming and in any order, so "Edit videos with coding agents" matches "agent video editing"."""
    text = " ".join([c["repo"].split("/")[1], c.get("desc") or "", " ".join(c.get("topics") or [])])
    hay = text.lower()
    tokens = _tokens(text.replace("-", " ").replace("_", " "))
    n = 0
    for key in ("entities", "mechanisms", "topics"):
        for g in groups(q.get(key)):
            if any(_has(t, hay, tokens) for t in g):
                n += 1
    for p in groups(q.get("problems")):
        if not p[0].isascii():
            n += int(all(w in hay for w in p[0].lower().split()))
            continue
        words = [_stem(w) for w in re.findall(r"[a-z0-9]+", p[0].lower())]
        if not words:
            continue
        need = 1 if len(words) == 1 else max(2, -(-2 * len(words) // 3))   # two thirds of the words, at least two
        if sum(w in tokens for w in words) >= need:
            n += 1
    return n


# Lures: repos that pose as game cheats, cracks or key generators to get downloads (often malware).
LURE = re.compile(r"\b(infinite|unlimited) (money|gold|coins?|gems?|robux)\b|\bfree (robux|v-?bucks)\b|\bkeygen\b|"
                  r"\bcrack(ed)? (version|download)\b|\baimbot\b|\bspoofer\b|\bmod (menu|hub|suite|forge)\b|"
                  r"\bcheat(s| engine| menu| tool)\b|\bserial key\b|外挂|破解版|激活码|无限金币", re.I)
LURE_WEAK = re.compile(r"\b(trainer|executor|unlocker)\b", re.I)
PITCH = re.compile(r"\b(ultimate|pro|advanced|companion|gameplay|mastery|guide|boosts?|mods?)\b", re.I)
YEAR = re.compile(r"\b20[2-3]\d\b")
FARM_MIN, FARM_RATIO = 20000, 2000   # skills.sh installs that far beyond the repo's stars were bought or scripted


def is_lure(c: dict) -> bool:
    """Game-cheat and crack lures. A weak word (trainer, executor) counts only with a year and a sales
    word in the description ("Advanced Trainer 2026"); "LoRA trainer" and "our 2026 hack week" pass."""
    desc = c.get("desc") or ""
    text = c["repo"].split("/")[-1].replace("-", " ").replace("_", " ") + " " + desc
    return bool(LURE.search(text) or (LURE_WEAK.search(text) and YEAR.search(desc) and PITCH.search(desc)))


def is_farmed(c: dict) -> bool:
    """skills.sh installs far beyond the stars: in October 2026 six copies of one popular skill pack,
    each with 0-8 stars and flat weekly counts, showed 0.7-3.8 million installs."""
    installs = c.get("installs") or 0
    return installs >= FARM_MIN and installs > FARM_RATIO * ((c.get("stars") or 0) + 1)


def excluded(c: dict) -> bool:
    return is_lure(c) or is_farmed(c)


def is_list(c: dict) -> bool:
    name = c["repo"].split("/")[1].lower()
    desc = (c.get("desc") or "").lower()
    return name.startswith("awesome") or bool(
        re.search(r"\b(curated|awesome) (list|collection)|\ba (collective|curated) list", desc))


def score(c: dict, q: dict | None = None) -> float:
    """Relevance first, then life (new and moving), then reach. Stars count least."""
    f = (c.get("fit") if q is None else fit(c, q)) or 0
    stars = c.get("stars", 0)
    age = months_since(c.get("created"))
    idle = months_since(c.get("pushed"))
    lenses = set(c.get("lenses", []))
    s = 2.2 * min(f, 4) - (2.0 if f == 0 else 0)                      # relevance dominates
    s += 1.6 * max(0.0, 1 - age / 18)                                 # created in the last 18 months
    s -= 0.6 if age > 48 else 0
    s += 1.0 if idle < 1 else 0.6 if idle < SLOW else -2.5 if idle < HIDE else -4.0   # unmaintained sinks
    s += min(1.5, 0.5 * math.log10(stars / max(age, 1) + 1))          # momentum: stars per month, capped
    s += 0.2 * math.log10(stars + 1)                                  # reach
    s += (0.3 if f > 0 else 0.1) * len(lenses - {"W", "L"})           # independent routes found it
    s += 3.0 if "W" in lenses else 0.5 if "L" in lenses else 0        # a person or a curated list pointed at it
    inst = 0.0 if c.get("fork") or is_farmed(c) else math.log10((c.get("installs") or 0) + 1)   # real use
    s += 0.4 * inst if f > 0 else min(0.4, 0.1 * inst)
    if q is not None:
        forms = [g[0].lower() for g in groups(q.get("forms"))]
        hay = (c.get("desc") or "").lower() + " " + " ".join(c.get("topics") or [])
        if any(_term_re(x).search(hay) for x in forms):
            s += 0.3
    s -= 3 if c.get("archived") else 0
    s -= 1 if c.get("fork") else 0
    s -= 0.3 if not c.get("license") else 0
    return round(s, 2)


def vocab_terms(q: dict) -> list[str]:
    terms = []
    for key in ("entities", "mechanisms", "topics"):
        for g in groups(q.get(key)):
            terms.extend(t.lower() for t in g)
    return [t for t in terms if len(t) >= 3]


def matches_vocab(r: dict, terms: list[str]) -> bool:
    hay = " ".join([r.get("full_name") or "", r.get("description") or "", " ".join(r.get("topics") or [])]).lower()
    return any(t in hay or t in hay.replace("-", " ") for t in terms)


GITHUB_URL = re.compile(r"github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9_.-]+)")


def slugs_in_text(text: str) -> list[str]:
    out, seen = [], set()
    for m in GITHUB_URL.finditer(text):
        slug = github_slug(f"github.com/{m.group(1)}/{m.group(2).rstrip('.')}")   # a link ending a sentence
        if slug and slug.lower() not in seen:
            seen.add(slug.lower())
            out.append(slug)
    return out


class Scan:
    def __init__(self, store: Store, client: Client, question: dict):
        self.store, self.client, self.q = store, client, question
        self.project, self.qid = question["project"], question["id"]
        self.cands: dict[str, dict] = {}
        self.dropped: set[str] = set()   # unmaintained for over DROP months; only counted
        self.log: list[dict] = []

    def _add(self, raw: dict, lens: str):
        c = compact(raw)
        if months_since(c["pushed"]) > DROP:
            self.dropped.add(c["repo"].lower())
            return
        key = c["repo"].lower()
        if key not in self.cands:
            c["lenses"] = []
            self.cands[key] = c
        if lens not in self.cands[key]["lenses"]:
            self.cands[key]["lenses"].append(lens)

    def add_slugs(self, slugs: list[str], lens: str, filter_vocab: bool = False) -> int:
        todo = [s for s in dict.fromkeys(slugs) if s.lower() not in self.cands]
        meta = self.client.graphql_repos(todo) if todo else {}
        terms = vocab_terms(self.q) if filter_vocab else []
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

    def run(self, lenses: str = DEFAULT_LENSES, budget: int = 250, per_query: int = 30) -> dict:
        start = self.client.calls
        for s in plan(self.q, lenses):
            if self.client.calls - start >= budget:
                self.log.append({**s, "hits": None, "error": "skipped: budget"})
                continue
            try:
                self.log.append({**s, "hits": self._one(s, per_query)})
            except GitHubError as exc:
                self.log.append({**s, "hits": None, "error": str(exc)})
            except OSError as exc:
                self.log.append({**s, "hits": None, "error": f"network: {exc}"})
            if self.client.verbose:
                print(f"  {s['lens']} {s['query'][:70]} -> {self.log[-1].get('hits')}", file=sys.stderr)
        return self.finish(lenses)

    def _one(self, s: dict, per_query: int) -> int:
        kind, query, lens = s["kind"], s["query"], s["lens"]
        if kind == "repos":
            items = self.client.search_repos(query, per_page=100 if lens == "H" else per_query)
            for r in items:
                self._add(r, lens)
            return len(items)
        if kind == "code":
            return self.add_slugs(self.client.search_code(query, per_page=per_query)[:per_query], lens)
        if kind == "npm":
            return self.add_slugs(self.client.npm_search(query)[:20], lens)
        if kind == "skills":
            found = self.client.skills_search(query)
            n = self.add_slugs([slug for slug, _, _ in found], lens)
            for slug, installs, _ in found:
                c = self.cands.get(slug.lower())
                if c is not None:
                    c["installs"] = max(c.get("installs") or 0, installs)
            return n
        if kind == "mcp":
            return self.add_slugs(self.client.mcp_search(query), lens)
        picked = [str(x) for x in as_list(self.q.get("picked"))]
        if self.store is not None:
            ref = f"{self.project}/{self.qid}"
            picked += [e["repo"] for (k, r), e in self.store.verdicts().items()
                       if r == ref and e.get("verdict") in ("short", "card") and e["repo"] not in picked]
        if kind == "people":
            logins = list(dict.fromkeys(self.store.people() + [p.split("/")[0] for p in picked]))
            terms = vocab_terms(self.q)
            n = 0
            for login in logins[:20]:
                for r in self.client.starred(login, pages=3):
                    if matches_vocab(r, terms):
                        self._add(r, lens)
                        n += 1
            return n
        if kind == "graph":
            slugs: list[str] = []
            for p in picked[:5]:
                slugs += [x for x in slugs_in_text(self.client.readme(p) or "") if x.lower() != p.lower()]
            return self.add_slugs(slugs[:80], lens)
        raise ValueError(kind)

    def finish(self, lenses: str) -> dict:
        for c in self.cands.values():
            c["lenses"] = sorted(c["lenses"], key=LENSES.index)
        scan = {"id": now_stamp(), "date": today(), "project": self.project, "question": self.qid,
                "lenses": lenses, "searches": self.log, "dropped": len(self.dropped),
                "candidates": list(self.cands.values())}
        rescore(scan, self.q)
        ranked = scan["candidates"]
        scan["candidates"] = ranked[:KEEP] + [c for c in ranked[KEEP:] if is_rising(c)][:RISE_KEEP]
        return scan


def rescore(scan: dict, q: dict) -> dict:
    """Fit and score depend on the question's current vocabulary, so they are recomputed on every view."""
    for c in scan["candidates"]:
        c["fit"] = fit(c, q)
        c["score"] = score(c, q)
        if is_list(c):
            c["list"] = True
        else:
            c.pop("list", None)
    scan["candidates"].sort(key=lambda c: (-c["score"], -c["stars"]))
    return scan


def annotate(store: Store, scan: dict) -> dict:
    """Mark candidates already carded or triaged so nobody re-reads them."""
    verdicts = store.verdicts()
    ref = f"{scan['project']}/{scan['question']}"
    carded = {c.id.lower(): c for c in store.cards() if not c.error}
    for c in scan["candidates"]:
        key = c["repo"].lower()
        c.pop("card", None)
        c.pop("seen", None)
        if key in carded:
            takes = [f"{u.get('project')}/{u.get('question') or '-'}:{u.get('take')}"
                     for u in as_list(carded[key].data.get("uses")) if isinstance(u, dict)]
            c["card"] = ", ".join(takes) or "card"
            continue
        here = verdicts.get((key, ref))
        other = [e for (k, r), e in verdicts.items() if k == key and r != ref]
        if here:
            c["seen"] = {"verdict": here["verdict"], "date": here.get("date"), "stars": here.get("stars"),
                         "reason": here.get("reason"), "here": True}
            then = here.get("stars") or 0
            if here["verdict"] == "skip" and c["stars"] >= max(2 * then, then + 200):
                c["seen"]["resurfaced"] = True
        elif other:
            e = max(other, key=lambda e: e.get("date") or "")
            c["seen"] = {"verdict": e["verdict"], "date": e.get("date"),
                         "question": f"{e.get('project')}/{e.get('question')}", "reason": e.get("reason"), "here": False}
    return scan


def is_open(c: dict) -> bool:
    """Still needs a look for this question."""
    if c.get("card"):
        return False
    seen = c.get("seen")
    if not seen or not seen.get("here"):
        return True
    return bool(seen.get("resurfaced")) or seen["verdict"] in ("peeked", "short", "list")


def is_stale(c: dict) -> bool:
    return months_since(c.get("pushed")) > HIDE


def is_rising(c: dict) -> bool:
    """Found only because it is new and growing fast: none of the vocabulary is in its own words."""
    return "H" in c.get("lenses", []) and not c.get("fit") and not c.get("list") and not excluded(c)


def momentum(c: dict) -> float:
    return (c.get("stars") or 0) / max(months_since(c.get("created")), 0.25)


def visible(scan: dict, show_all: bool = False) -> list[dict]:
    """Rows `render` numbers; `pick` resolves numbers against the same list."""
    return [c for c in scan["candidates"] if not c.get("list") and not c.get("card") and not is_rising(c)
            and months_since(c.get("pushed")) <= DROP and (show_all or (is_open(c) and not is_stale(c) and not excluded(c)))]


def rising(scan: dict, show_all: bool = False) -> list[dict]:
    """Rows `render` lists apart as h1, h2...: fastest-growing first, those in the form's topics
    (skills, MCP servers) ahead of breakouts from anywhere, which keep a third of the shown rows."""
    rows = sorted((c for c in scan["candidates"] if is_rising(c) and not c.get("card") and not excluded(c)
                   and months_since(c.get("pushed")) <= DROP and (show_all or (is_open(c) and not is_stale(c)))),
                  key=lambda c: -momentum(c))
    form = [c for c in rows if RISE_TOPIC_SET & set(c.get("topics") or [])]
    other = [c for c in rows if not RISE_TOPIC_SET & set(c.get("topics") or [])]
    n_form = min(len(form), RISE_SHOW - min(len(other), RISE_SHOW // 3))
    n_other = min(len(other), RISE_SHOW - n_form)
    return form[:n_form] + other[:n_other] + sorted(form[n_form:] + other[n_other:], key=lambda c: -momentum(c))


def human(n: int) -> str:
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def row(i, c: dict) -> str:
    flags = [f"fit {c.get('fit', 0)}"] if not is_rising(c) else [f"{human(int(momentum(c)))} stars/month"]
    if c.get("installs"):
        flags.append(f"installs {human(c['installs'])}")
    if c.get("archived"):
        flags.append("ARCHIVED")
    if c.get("fork"):
        flags.append("fork")
    seen = c.get("seen")
    if seen and not seen.get("here"):
        flags.append(f"seen:{seen['verdict']}@{seen.get('question')}")
    elif seen:
        flags.append(seen["verdict"] + (" (grew, look again)" if seen.get("resurfaced") else ""))
    desc = re.sub(r"\s+", " ", c.get("desc") or "")[:90]
    label = f"{i:>3}." if isinstance(i, int) else f"{i:>4}"
    return (f"{label} {c['score']:>5.1f} {human(c['stars']):>6} {c.get('created', '')[2:7]:>6} {c.get('pushed', '')[2:]:>8}"
            f"  {c['repo']}  {desc}  [{''.join(c['lenses'])}] {' '.join(flags)}")


def render(scan: dict, top: int = 40, show_all: bool = False) -> str:
    out = [f"scan {scan['project']}/{scan['question']} {scan['id']}: {len(scan['searches'])} searches, "
           f"{len(scan['candidates'])} repos"]
    by_lens: dict[str, int] = {}
    errors = []
    for s in scan["searches"]:
        by_lens[s["lens"]] = by_lens.get(s["lens"], 0) + (s.get("hits") or 0)
        if s.get("error"):
            errors.append(f"{s['lens']} {s['query'][:60]}: {s['error'][:80]}")
    out.append("lenses: " + "  ".join(f"{k}={v}" for k, v in sorted(by_lens.items(), key=lambda kv: LENSES.index(kv[0]))))
    rows = visible(scan, show_all)
    shown = rows[:top]
    langs = search_langs([s for s in scan["searches"] if s.get("hits") is not None])   # those that ran
    out.append("languages: " + (", ".join(f"{k} {v}" for k, v in langs.items()) or "none") + " searches with words; "
               f"{sum(1 for c in shown if HAN.search(c.get('desc') or ''))} of {len(shown)} rows shown have a Chinese description")
    if errors:
        out.append(f"errors ({len(errors)}): " + "; ".join(errors[:3]) + (" ..." if len(errors) > 3 else ""))
    carded = [c for c in scan["candidates"] if c.get("card")]
    if carded:
        out.append("already in the registry: " + "; ".join(f"{c['repo']} ({c['card']})" for c in carded[:12]))
    stale = [c for c in scan["candidates"] if is_stale(c) and not c.get("card")]
    if scan.get("dropped") or stale:
        out.append(f"maintenance: {scan.get('dropped', 0)} dropped (no push in {DROP} months), "
                   f"{len(stale)} hidden (no push in {HIDE} months; --all shows them)")
    lures = [c for c in scan["candidates"] if is_lure(c)]
    farmed = [c for c in scan["candidates"] if is_farmed(c) and not is_lure(c)]
    if lures or farmed:
        out.append(f"excluded: {len(lures)} look like lures (game cheats, cracks; do not download), "
                   f"{len(farmed)} have install counts far beyond their stars (--all shows them)")
    lists = [c for c in scan["candidates"] if c.get("list") and is_open(c) and not is_stale(c) and not excluded(c)]
    if lists:
        out.append("lists (scan --expand <list>): " + ", ".join(f"{c['repo']} ({human(c['stars'])})" for c in lists[:8]))
    hidden = len([c for c in scan["candidates"] if not c.get("list") and not c.get("card") and not is_stale(c)
                  and not excluded(c) and not is_rising(c)]) - len(rows)
    out.append("  #  score  stars created   pushed  repo  description  [lenses] fit = vocabulary groups in its own name/description/topics"
               + (f"  ({hidden} already decided, hidden; --all shows them)" if hidden > 0 and not show_all else ""))
    out += [row(i, c) for i, c in enumerate(rows[:top], 1)]
    if len(rows) > top:
        out.append(f"... {len(rows) - top} more (--top N)")
    rise = rising(scan, show_all)
    if rise:
        out.append(f"rising: new in the last {RISE_MONTHS} months and growing fast, but no vocabulary in their own words "
                   f"({len(rise)}). Judge each by what it makes, not by its words; pick with h<#>")
        out += [row(f"h{i}.", c) for i, c in enumerate(rise[:RISE_SHOW], 1)]
        if len(rise) > RISE_SHOW:
            out.append(f"... {len(rise) - RISE_SHOW} more rising (--json lists them)")
    return "\n".join(out)
