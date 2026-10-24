"""The registry store: a plain directory (usually a git repo) of Markdown and JSON.

    github-scout.json                         marker + settings ({"format", "name", "lang"})
    INDEX.md                                 generated overview
    projects/<project>/project.md            what the project is, where its code is, its rules
    projects/<project>/questions/<q>.md      one question: stage, vocabulary, and the answer (the brief)
    repos/<owner>__<repo>.md                 one card per repository we looked at closely
    ledger.jsonl                             every verdict, append-only
    scans/<project>/<q>/<stamp>.json         what each search ran and found
    people.txt                               GitHub logins whose stars feed the people lens
    site/index.html                          generated viewer (github-scout site)
    cache/                                   downloaded source (not committed)

See references/store-format.md for the full specification.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from .github import github_slug
from .yamlish import FormatError, join_frontmatter, split_frontmatter

MARKER = "github-scout.json"
LEGACY_MARKERS = ("reuse-first.json",)   # registries made before the rename keep working
DEFAULT_STORE = Path("~/.github-scout")  # used, and created by `ask`, when nothing else names a registry


def env(name: str) -> str | None:
    """GITHUB_SCOUT_<name>, or the pre-rename REUSE_FIRST_<name>."""
    return os.environ.get(f"GITHUB_SCOUT_{name}") or os.environ.get(f"REUSE_FIRST_{name}")


def marker_of(root: Path) -> Path | None:
    for name in (MARKER, *LEGACY_MARKERS):
        if (root / name).is_file():
            return root / name
    return None
FORMAT = 2

# What a repository is. Skills and software are judged differently (references/evaluation.md).
KINDS = ["skill", "software", "list", "other"]
# What we take from it, strongest first. A card's status is its strongest take.
TAKES = ["use", "adapt", "learn", "later", "skip"]
# Takes that make a repo a reference: they need MIN_STARS or a written exception.
REFERENCE_TAKES = ("use", "adapt", "learn")
# Under this many stars a repo is no reference: not shortlisted, used, adapted or learned from unless a reason is
# written (user, 2026-10-18). GITHUB_SCOUT_MIN_STARS changes it. Lists are exempt: they are only for finding.
MIN_STARS = 50
# Where our own work stands. It decides what is worth borrowing.
STAGES = ["idea", "prototype", "working", "polishing"]
QUESTION_STATUS = ["open", "answered"]
VERDICTS = ["peeked", "short", "list", "later", "skip", "card"]
LEVELS = ["meta", "look", "read", "trial"]
# How a repository came into one of our projects (`adopt`, stage 6).
MODES = ["depend", "vendor", "port", "skill", "tool", "data"]
# Languages a question searches in. Terms are told apart by script, so Latin-script languages count as en.
# Default en + zh: in real runs Chinese projects supplied half of the repos picked.
LANGS = ["en", "zh", "ja", "ko"]
DEFAULT_LANGS = ["en", "zh"]

CARD_ORDER = ["id", "repo", "kind", "form", "summary", "license", "stars",  # license: old cards only, no longer written
              "created", "pushed", "branch", "commit",
              "reviewed", "level", "results", "watch", "aliases", "uses", "adopted"]
QUESTION_ORDER = ["id", "project", "ask", "stage", "status", "langs", "entities", "mechanisms", "forms", "problems",
                  "topics", "backbone", "alternate", "picked", "scanned"]
# Answer sections a check or a brief looks for, in both template languages. A report (2026-10-19) names the repos
# to try first; answers from 2026-10-18 named a backbone, which the coding agent now sets after trying.
TRY_TITLES = ("Try first", "先试")
BACKBONE_TITLES = ("Backbone", "主干")
PROJECT_ORDER = ["id", "name", "summary", "code", "stack", "constraints", "languages"]

SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]+$")
ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA = re.compile(r"^[0-9a-f]{7,40}$")
URL = re.compile(r"^https?://[^\s<>\"']+$")
KANA = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\uff66-\uff9f]")
HANGUL = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
# A scan's id is the second it ran; a second scan in the same second gets -2, -3 ...
SCAN_ID = re.compile(r"(\d{8}-\d{6})(?:-(\d+))?")
# Characters str.splitlines() breaks on that json.dumps(ensure_ascii=False) leaves raw inside a string.
LINE_BREAKS = {"\u2028": "\\u2028", "\u2029": "\\u2029", "\x85": "\\u0085"}


class StoreError(RuntimeError):
    pass


def today() -> str:
    return _dt.date.today().isoformat()


def min_stars() -> int:
    """The star threshold for a reference: MIN_STARS, or GITHUB_SCOUT_MIN_STARS."""
    raw = (env("MIN_STARS") or "").strip()
    if not raw:
        return MIN_STARS
    try:
        return max(0, int(raw))
    except ValueError:
        raise StoreError(f"GITHUB_SCOUT_MIN_STARS must be a whole number (got {raw!r})") from None


def stars_of(v) -> int | None:
    """A star count as recorded (an int, or digits in a hand-edited file); None when unknown."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def reference_gaps(card: dict, use: dict, limit: int, trial: bool = False) -> list[str]:
    """Check the star floor and, after choosing a backbone, its trial. Links are optional notes, not a quality gate."""
    out = []
    stars = stars_of(card.get("stars"))
    if trial and card.get("level") != "trial":
        out.append(f"was not tried (level {card.get('level') or '-'}): run its own example, then note --trial")
    if stars is not None and stars < limit and not use.get("low_stars"):
        out.append(f"has {stars} stars, under {limit}, and no reason (note --low-stars)")
    return out


def now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def repo_ref(text: str) -> str:
    """A repo as the registry names it: a github.com URL becomes owner/repo; anything else (an alias) is left as is."""
    return (github_slug(text) or text) if "/" in text else text


def ledger_line(entry: dict) -> str:
    """One ledger entry as one line, Chinese kept readable; U+2028 and its kind escaped, so a reader that splits
    on them cannot cut the entry in two."""
    line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
    for ch, esc in LINE_BREAKS.items():
        line = line.replace(ch, esc)
    return line


def card_filename(slug: str) -> str:
    owner, name = slug.lower().split("/", 1)
    return f"{owner}__{name}.md"


def as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def strongest(takes: list[str]) -> str | None:
    ranked = [t for t in TAKES if t in takes]
    return ranked[0] if ranked else None


def card_takes(data: dict) -> list[str]:
    return [str(u.get("take")) for u in as_list(data.get("uses")) if isinstance(u, dict)]


def adoptions(data: dict, project: str | None = None, dropped: bool = False) -> list[dict]:
    """A card's `adopted` entries (what came into our projects), without the dropped ones unless asked."""
    return [a for a in as_list(data.get("adopted")) if isinstance(a, dict)
            and (dropped or not a.get("dropped")) and (project is None or a.get("project") == project)]


def groups(items) -> list[list[str]]:
    """Vocabulary items as groups of synonyms: "xiaohongshu|小红书|xhs" -> ["xiaohongshu", "小红书", "xhs"]."""
    out = []
    for item in as_list(items):
        terms = [t.strip() for t in str(item).split("|") if t.strip()]
        if terms:
            out.append(terms)
    return out


def lang_of(text: str) -> str:
    """ja for kana, ko for hangul, zh for CJK ideographs, else en. Kana first: Japanese mixes both."""
    if KANA.search(text):
        return "ja"
    if HANGUL.search(text):
        return "ko"
    if HAN.search(text):
        return "zh"
    return "en"


def question_langs(data: dict) -> list[str]:
    langs = [str(x).strip().lower() for x in as_list(data.get("langs")) if str(x).strip()]
    return list(dict.fromkeys(langs)) or list(DEFAULT_LANGS)


def parse_langs(text: str) -> list[str]:
    langs = list(dict.fromkeys(x.strip().lower() for x in text.split(",") if x.strip()))
    bad = [x for x in langs if x not in LANGS]
    if bad or not langs:
        raise StoreError(f"--langs takes codes from {', '.join(LANGS)}, comma-separated (got {text!r}); "
                         "terms are told apart by script, so Latin-script languages count as en")
    return langs


def lang_gaps(data: dict) -> list[str]:
    """One line per language in `langs` that some entity or mechanism group has no term in."""
    gs = groups(data.get("entities")) + groups(data.get("mechanisms"))
    out = []
    for lang in question_langs(data):
        miss = [g[0] for g in gs if not any(lang_of(t) == lang for t in g)]
        if miss:
            out.append(f"{len(miss)} of {len(gs)} vocabulary groups have no {lang} term: "
                       f"{', '.join(miss[:6])}{' ...' if len(miss) > 6 else ''} "
                       f"(add what {lang} users write, after |; a name they write the same way needs nothing)")
    return out


@dataclass
class Doc:
    path: Path
    data: dict = field(default_factory=dict)
    body: str = ""
    error: str | None = None

    @property
    def id(self) -> str:
        return str(self.data.get("id") or "")


def read_doc(path: Path) -> Doc:
    try:
        data, body = split_frontmatter(path.read_text(encoding="utf-8"))
        return Doc(path, data, body)
    except (FormatError, UnicodeDecodeError) as exc:
        return Doc(path, {}, "", f"{exc}")


def write_doc(path: Path, data: dict, body: str, order: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(join_frontmatter(data, body, order), encoding="utf-8")


def _scaffold(par: str) -> bool:
    """A template hint (one parenthesised paragraph) or a table with a header and no rows."""
    t = par.strip()
    if t[:1] in "(（" and t[-1:] in ")）":
        return True
    rows = [ln for ln in t.splitlines() if ln.strip()]
    return all(ln.lstrip().startswith("|") for ln in rows) and len(rows) <= 2 and \
        (len(rows) < 2 or bool(re.match(r"^\s*\|?\s*:?-{2,}", rows[1])))


def section(body: str, titles: tuple[str, ...]) -> str | None:
    """The text under the first heading (levels 2-4) whose title starts with one of `titles`, up to the next heading
    of the same or a higher level, without unfilled template scaffolding. None when there is no such heading: an
    answer written before that section existed."""
    lines = body.splitlines()
    for i, ln in enumerate(lines):
        m = re.match(r"^(#{2,4})\s+(.*)$", ln)
        if m and any(m.group(2).strip().lower().startswith(t.lower()) for t in titles):
            out = []
            for nxt in lines[i + 1:]:
                h = re.match(r"^(#{1,4})\s", nxt)
                if h and len(h.group(1)) <= len(m.group(1)):
                    break
                out.append(nxt)
            pars = re.split(r"\n\s*\n", "\n".join(out).strip())
            return "\n\n".join(p for p in pars if p.strip() and not _scaffold(p))
    return None


# ---------------------------------------------------------------------------
# Locating the store


def _config_files() -> list[Path]:
    home = Path.home()
    xdg = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    files = []
    if env("CONFIG"):
        files.append(Path(env("CONFIG")).expanduser())
    skills_cfg = Path(os.environ.get("AGENT_SKILLS_CONFIG_DIR") or xdg / "agent-skills")
    for name in ("github-scout", "reuse-first"):
        files += [xdg / name / "config.env", skills_cfg / name / "config.env"]
    return files


def read_config() -> dict:
    """KEY=value lines; parsed, never executed. Unknown keys are an error.
    Keys come back as GITHUB_SCOUT_*; the pre-rename REUSE_FIRST_* spellings are read too."""
    allowed = {"GITHUB_SCOUT_STORE", "GITHUB_SCOUT_PROJECT", "REUSE_FIRST_STORE", "REUSE_FIRST_PROJECT"}
    for path in _config_files():
        if not path.is_file():
            continue
        out = {}
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                raise StoreError(f"{path}:{n}: expected KEY=value")
            key, val = (x.strip() for x in line.split("=", 1))
            if key not in allowed:
                raise StoreError(f"{path}:{n}: unknown key {key} (allowed: {', '.join(sorted(allowed))})")
            out[key.replace("REUSE_FIRST_", "GITHUB_SCOUT_")] = val.strip("'\"")
        return out
    return {}


def locate(explicit: str | None = None, create_lang: str | None = None) -> Path:
    """--store, else $GITHUB_SCOUT_STORE, else the config file, else the nearest parent holding a marker,
    else ~/.github-scout. With create_lang, a missing ~/.github-scout is created in that language."""
    if explicit:
        root = Path(explicit).expanduser()
    elif env("STORE"):
        root = Path(env("STORE")).expanduser()
    elif read_config().get("GITHUB_SCOUT_STORE"):
        root = Path(read_config()["GITHUB_SCOUT_STORE"]).expanduser()
    else:
        here = Path.cwd().resolve()
        found = next((p for p in [here, *here.parents] if marker_of(p)), None)
        root = found or DEFAULT_STORE.expanduser()
        if not found and not marker_of(root) and not create_lang:
            raise StoreError(f"no registry yet. The first `github-scout ask` creates one in {DEFAULT_STORE}; "
                             "to keep it elsewhere, set GITHUB_SCOUT_STORE=<dir> or pass --store.")
    if create_lang and not marker_of(root) and (not root.exists() or (root.is_dir() and not any(root.iterdir()))):
        Store.init(root, root.name if root.name not in (".github-scout", "") else "github-scout", create_lang)
    if not marker_of(root):
        raise StoreError(f"{root} is not a registry (no {MARKER}). Run `github-scout init {root}`.")
    return root.resolve()


# ---------------------------------------------------------------------------


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        marker = marker_of(self.root)
        if marker is None:
            raise StoreError(f"{self.root} is not a registry (no {MARKER})")
        self.settings = json.loads(marker.read_text(encoding="utf-8"))
        if int(self.settings.get("format", 1)) > FORMAT:
            raise StoreError(f"{self.root} uses registry format {self.settings['format']}; this github-scout reads "
                             f"format {FORMAT}. Upgrade github-scout.")
        self._cards: list[Doc] | None = None

    @property
    def lang(self) -> str:
        return "zh" if str(self.settings.get("lang", "en")).lower().startswith("zh") else "en"

    # -- init ------------------------------------------------------------
    @staticmethod
    def init(root: Path, name: str | None = None, lang: str = "en") -> Store:
        root = Path(root).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        marker = root / MARKER
        if marker_of(root):
            raise StoreError(f"{root} is already a registry")
        for sub in ("projects", "repos", "scans", "cache"):
            (root / sub).mkdir(exist_ok=True)
        marker.write_text(json.dumps({"format": FORMAT, "name": name or root.name, "lang": lang,
                                      "default_project": None}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        (root / "ledger.jsonl").touch()
        gi = root / ".gitignore"
        if not gi.exists():
            gi.write_text("cache/\n", encoding="utf-8")
        people = root / "people.txt"
        if not people.exists():
            people.write_text("# GitHub logins whose starred repos feed the people lens (one per line).\n"
                              "# Pick builders whose taste you trust in your field.\n", encoding="utf-8")
        readme = root / "README.md"
        if not readme.exists():
            readme.write_text(STORE_README.format(name=name or root.name), encoding="utf-8")
        return Store(root)

    # -- cards -----------------------------------------------------------
    def cards(self) -> list[Doc]:
        if self._cards is None:
            d = self.root / "repos"
            self._cards = [read_doc(p) for p in sorted(d.glob("*.md"))] if d.is_dir() else []
        return self._cards

    def card(self, ref: str) -> Doc | None:
        ref = repo_ref(ref)
        ref_l = ref.lower()
        if "/" in ref:
            path = self.root / "repos" / card_filename(ref)
            if path.is_file():
                return read_doc(path)
        for c in self.cards():
            if c.id.lower() == ref_l or ref_l in [str(a).lower() for a in as_list(c.data.get("aliases"))]:
                return c
        return None

    def card_path(self, slug: str) -> Path:
        return self.root / "repos" / card_filename(slug)

    def save_card(self, doc: Doc) -> None:
        write_doc(doc.path, doc.data, doc.body, CARD_ORDER)
        self._cards = None

    # -- projects and questions ------------------------------------------
    def projects(self) -> list[Doc]:
        d = self.root / "projects"
        if not d.is_dir():
            return []
        return [read_doc(p / "project.md") for p in sorted(d.iterdir()) if (p / "project.md").is_file()]

    def project(self, pid: str) -> Doc | None:
        p = self.root / "projects" / pid / "project.md"
        return read_doc(p) if p.is_file() else None

    def questions(self, project: str | None = None) -> list[Doc]:
        out = []
        for proj in self.projects():
            pid = proj.path.parent.name
            if project and pid != project:
                continue
            qd = proj.path.parent / "questions"
            if qd.is_dir():
                out.extend(read_doc(p) for p in sorted(qd.glob("*.md")))
        return out

    def question_path(self, project: str, qid: str) -> Path:
        return self.root / "projects" / project / "questions" / f"{qid}.md"

    def question(self, ref: str) -> Doc:
        project, qid = self.split_ref(ref)
        p = self.question_path(project, qid)
        if not p.is_file():
            raise StoreError(f"no question {project}/{qid} (create it: github-scout ask {project}/{qid} \"...\")")
        doc = read_doc(p)
        if doc.error:
            raise StoreError(f"{p}: {doc.error}")
        return doc

    def save_question(self, doc: Doc) -> None:
        write_doc(doc.path, doc.data, doc.body, QUESTION_ORDER)

    def split_ref(self, ref: str) -> tuple[str, str]:
        if "/" in ref:
            project, qid = ref.split("/", 1)
        else:
            project = self.settings.get("default_project") or read_config().get("GITHUB_SCOUT_PROJECT") or env("PROJECT")
            qid = ref
            if not project:
                raise StoreError(f"write the question as <project>/<question> (no default project set): {ref}")
        return project, qid

    # -- ledger ----------------------------------------------------------
    def ledger(self) -> list[dict]:
        p = self.root / "ledger.jsonl"
        if not p.is_file():
            return []
        out = []
        for line in p.read_text(encoding="utf-8").split("\n"):   # not splitlines(): U+2028 in old entries is text
            line = line.strip()
            if line:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    e = None
                out.append(e if isinstance(e, dict) else {"_bad": line})
        return out

    def append_ledger(self, entries: list[dict]) -> None:
        if not entries:
            return
        p = self.root / "ledger.jsonl"
        lead = ""
        if p.is_file() and p.stat().st_size:                   # a hand edit may have dropped the final newline
            with p.open("rb") as f:
                f.seek(-1, os.SEEK_END)
                lead = "" if f.read(1) == b"\n" else "\n"
        with p.open("a", encoding="utf-8") as f:
            f.write(lead + "".join(ledger_line(e) + "\n" for e in entries))

    def verdicts(self) -> dict[tuple[str, str], dict]:
        """Latest ledger entry per (repo, project/question)."""
        latest: dict[tuple[str, str], dict] = {}
        for e in self.ledger():
            if "repo" in e:
                latest[(str(e["repo"]).lower(), f"{e.get('project', '')}/{e.get('question', '')}")] = e
        return latest

    def history(self, slug: str) -> list[dict]:
        s = slug.lower()
        return [e for e in self.ledger() if str(e.get("repo", "")).lower() == s]

    # -- scans -----------------------------------------------------------
    def scan_dir(self, project: str, qid: str) -> Path:
        return self.root / "scans" / project / qid

    def scans(self, project: str, qid: str) -> list[Path]:
        """Scan files, oldest first (named by their id); other files may sit beside them."""
        d = self.scan_dir(project, qid)
        if not d.is_dir():
            return []
        found = [(m, p) for m, p in ((SCAN_ID.fullmatch(p.stem), p) for p in d.glob("*.json")) if m]
        return [p for m, p in sorted(found, key=lambda mp: (mp[0].group(1), int(mp[0].group(2) or 1)))]

    def save_scan(self, scan: dict) -> Path:
        """Write a new scan file. When a scan with the same id exists (two in one second), the id gets -2, -3 ..."""
        d = self.scan_dir(scan["project"], scan["question"])
        d.mkdir(parents=True, exist_ok=True)
        base, n = scan["id"], 1
        while True:
            p = d / f"{scan['id']}.json"
            try:
                with p.open("x", encoding="utf-8") as f:
                    f.write(json.dumps(scan, ensure_ascii=False, indent=1) + "\n")
                return p
            except FileExistsError:
                n += 1
                scan["id"] = f"{base}-{n}"

    def people(self) -> list[str]:
        p = self.root / "people.txt"
        if not p.is_file():
            return []
        return [ln.split("#", 1)[0].strip() for ln in p.read_text(encoding="utf-8").splitlines()
                if ln.split("#", 1)[0].strip()]

    # -- cache -----------------------------------------------------------
    def cache_dir(self, slug: str, sha: str) -> Path:
        owner, name = slug.lower().split("/", 1)
        return self.root / "cache" / f"{owner}__{name}@{sha[:7]}"

    def cached(self, slug: str) -> list[Path]:
        owner, name = slug.lower().split("/", 1)
        d = self.root / "cache"
        return sorted(d.glob(f"{owner}__{name}@*")) if d.is_dir() else []

    # -- validation ------------------------------------------------------
    def _reference_warnings(self, r: str, d: dict, pid: str, qid: str) -> list[str]:
        """Every repo a report names to try first (`picked`) has enough stars, or a written
        reason. A backbone and an alternate, set by the coding agent after trying, were also tried. A report is not
        asked for a backbone or for trials: trying and choosing come after it."""
        def slug(key: str) -> str | None:
            v = d.get(key)
            return v if isinstance(v, str) and SLUG.match(v) else None

        backbone, alternate = slug("backbone"), slug("alternate")
        if not (backbone or as_list(d.get("picked"))):
            return []
        limit = min_stars()
        out = []
        for s in dict.fromkeys(x for x in (backbone, alternate, *map(str, as_list(d.get("picked")))) if x):
            role = "backbone" if s == backbone else "alternate" if s == alternate else "picked"
            card = self.card(s)
            if not card or card.error:
                if role != "picked":                         # a picked repo without a card is reported already
                    out.append(f"{r}: {role} {s} has no card")
                continue
            use = next((u for u in as_list(card.data.get("uses")) if isinstance(u, dict)
                        and u.get("project") == pid and u.get("question") == qid), {})
            out += [f"{r}: {role} {s} {w}" for w in reference_gaps(card.data, use, limit, trial=role != "picked")]
        return out

    def check(self) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warns: list[str] = []

        def rel(p: Path) -> str:
            return p.relative_to(self.root).as_posix()

        projects = {p.path.parent.name: p for p in self.projects()}
        for pid, doc in projects.items():
            if doc.error:
                errors.append(f"{rel(doc.path)}: {doc.error}")
                continue
            if doc.id != pid:
                errors.append(f"{rel(doc.path)}: id must be {pid!r}")
            if not ID.match(pid):
                errors.append(f"{rel(doc.path)}: project ids use lowercase letters, digits, . _ -")
        qids: set[str] = set()
        for doc in self.questions():
            pid, qid = doc.path.parent.parent.name, doc.path.stem
            qids.add(f"{pid}/{qid}")
            r = rel(doc.path)
            if doc.error:
                errors.append(f"{r}: {doc.error}")
                continue
            d = doc.data
            if d.get("id") != qid:
                errors.append(f"{r}: id must be {qid!r}")
            if d.get("project") != pid:
                errors.append(f"{r}: project must be {pid!r}")
            if not d.get("ask"):
                errors.append(f"{r}: missing ask (the question, one sentence)")
            if d.get("stage") not in STAGES:
                errors.append(f"{r}: stage must be one of {', '.join(STAGES)}")
            if d.get("status") not in QUESTION_STATUS:
                errors.append(f"{r}: status must be one of {', '.join(QUESTION_STATUS)}")
            for key in ("langs", "entities", "mechanisms", "forms", "problems", "topics", "picked"):
                if d.get(key) is not None and not isinstance(d.get(key), list):
                    errors.append(f"{r}: {key} must be a list")
            if [x for x in as_list(d.get("langs")) if str(x).strip().lower() not in LANGS]:
                errors.append(f"{r}: langs must be codes from {', '.join(LANGS)} "
                              "(terms are told apart by script, so Latin-script languages count as en)")
            if not (as_list(d.get("entities")) or as_list(d.get("mechanisms")) or as_list(d.get("problems"))):
                warns.append(f"{r}: no search vocabulary yet (entities, mechanisms, problems)")
            warns += [f"{r}: {w}" for w in lang_gaps(d)]
            for slug in as_list(d.get("picked")):
                if not self.card(str(slug)):
                    warns.append(f"{r}: picked {slug} has no card")
            if d.get("scanned") and not DATE.match(str(d.get("scanned"))):
                errors.append(f"{r}: scanned must be YYYY-MM-DD")
            errors += [f"{r}: {key} must be one repository, owner/repo" for key in ("backbone", "alternate")
                       if d.get(key) is not None and not (isinstance(d[key], str) and SLUG.match(d[key]))]
            if d.get("status") == "answered" and not as_list(d.get("picked")) and section(doc.body, TRY_TITLES) == "":
                warns.append(f"{r}: answered without repos to try first: name 2-3 under Try first and in picked:, "
                             "or say there why none qualifies")
            warns += self._reference_warnings(r, d, pid, qid)
        seen_ids: dict[str, Path] = {}
        for doc in self.cards():
            r = rel(doc.path)
            if doc.error:
                errors.append(f"{r}: {doc.error}")
                continue
            d = doc.data
            slug = str(d.get("id") or "")
            if not SLUG.match(slug):
                errors.append(f"{r}: id must be owner/repo")
            elif card_filename(slug) != doc.path.name:
                errors.append(f"{r}: file name must be {card_filename(slug)}")
            if slug.lower() in seen_ids:
                errors.append(f"{r}: duplicate of {rel(seen_ids[slug.lower()])}")
            seen_ids[slug.lower()] = doc.path
            for key in ("repo", "kind", "summary", "commit", "reviewed"):
                if d.get(key) in (None, ""):
                    errors.append(f"{r}: missing {key}")
            if d.get("kind") and d["kind"] not in KINDS:
                errors.append(f"{r}: kind must be one of {', '.join(KINDS)}")
            if d.get("commit") and not SHA.match(str(d["commit"])):
                errors.append(f"{r}: commit must be a hex sha (7-40 chars)")
            for key in ("reviewed", "pushed", "created"):
                if d.get(key) and not DATE.match(str(d[key])):
                    errors.append(f"{r}: {key} must be YYYY-MM-DD")
            if d.get("level") and d["level"] not in LEVELS:
                errors.append(f"{r}: level must be one of {', '.join(LEVELS)}")
            if d.get("results") is not None and not isinstance(d.get("results"), list):
                errors.append(f"{r}: results must be a list of links")
            errors += [f"{r}: results are links (http or https): {x}" for x in as_list(d.get("results"))
                       if isinstance(d.get("results"), list) and not URL.match(str(x))]
            uses = d.get("uses")
            if uses is not None and not isinstance(uses, list):
                errors.append(f"{r}: uses must be a list")
                uses = []
            if not uses:
                warns.append(f"{r}: no uses (say what a project takes from it, even skip)")
            for u in as_list(uses):
                if not isinstance(u, dict):
                    errors.append(f"{r}: each uses item is a mapping (project, question, take, where, note)")
                    continue
                if u.get("take") not in TAKES:
                    errors.append(f"{r}: take must be one of {', '.join(TAKES)}")
                if not u.get("project"):
                    errors.append(f"{r}: uses item without project")
                elif u["project"] not in projects:
                    warns.append(f"{r}: project {u['project']!r} has no profile")
                elif u.get("question") and f"{u['project']}/{u['question']}" not in qids:
                    warns.append(f"{r}: question {u['project']}/{u['question']} does not exist")
                if u.get("take") in ("skip", "learn", "adapt") and not u.get("note"):
                    warns.append(f"{r}: {u.get('take')} without a note (say what, or why not)")
            adopted = d.get("adopted")           # optional: cards from before stage 6 have none
            if adopted is not None and not isinstance(adopted, list):
                errors.append(f"{r}: adopted must be a list")
                adopted = []
            for a in as_list(adopted):
                if not isinstance(a, dict):
                    errors.append(f"{r}: each adopted item is a mapping (project, question, mode, into, from, at, ours, date)")
                    continue
                if a.get("mode") not in MODES:
                    errors.append(f"{r}: adopted mode must be one of {', '.join(MODES)}")
                if not a.get("project"):
                    errors.append(f"{r}: adopted item without project")
                elif a["project"] not in projects:
                    warns.append(f"{r}: adopted into project {a['project']!r}, which has no profile")
                elif a.get("question") and f"{a['project']}/{a['question']}" not in qids:
                    warns.append(f"{r}: adopted under question {a['project']}/{a['question']}, which does not exist")
                if not isinstance(a.get("into"), list) or not a["into"]:
                    errors.append(f"{r}: adopted into must be a list of our paths")
                if a.get("from") is not None and not isinstance(a.get("from"), list):
                    errors.append(f"{r}: adopted from must be a list of upstream paths")
                for key in ("at", "ours"):
                    if a.get(key) and not SHA.match(str(a[key])):
                        errors.append(f"{r}: adopted {key} must be a hex sha (7-40 chars)")
                for key in ("date", "dropped"):
                    if a.get(key) and not DATE.match(str(a[key])):
                        errors.append(f"{r}: adopted {key} must be YYYY-MM-DD")
        for n, e in enumerate(self.ledger(), 1):
            if "_bad" in e:
                errors.append(f"ledger.jsonl:{n}: not a JSON object")
            elif not isinstance(e.get("repo"), str) or not e["repo"] or e.get("verdict") not in VERDICTS:
                errors.append(f"ledger.jsonl:{n}: needs repo and a verdict in {', '.join(VERDICTS)}")
        return errors, warns


STORE_README = """# {name}

A github-scout registry: the questions we asked, what we found on GitHub, what we took from
it, and every repository we looked at and why we passed.

- `INDEX.md` (generated) and `site/index.html` (`github-scout site`) give the overview.
- `projects/<project>/questions/<q>.md`: one question, where we stand, and the answer.
- `repos/<owner>__<repo>.md`: one card per repository we looked at closely.
- `ledger.jsonl`: every verdict, so nobody looks at the same repository twice.
- `scans/`: what each search ran and found.
- `cache/`: downloaded source, not committed.

Agents: load the github-scout skill and run `github-scout find <words>` before reading anything here.
"""
