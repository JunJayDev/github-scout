"""The registry store: a plain directory (usually a git repo) of Markdown and JSON.

    reuse-first.json                         marker + settings ({"format", "name", "lang"})
    INDEX.md                                 generated overview
    projects/<project>/project.md            what the project is, where its code is, its rules
    projects/<project>/questions/<q>.md      one question: stage, vocabulary, and the answer (the brief)
    repos/<owner>__<repo>.md                 one card per repository we looked at closely
    ledger.jsonl                             every verdict, append-only
    scans/<project>/<q>/<stamp>.json         what each search ran and found
    people.txt                               GitHub logins whose stars feed the people lens
    site/index.html                          generated viewer (reuse-first site)
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

from .yamlish import FormatError, join_frontmatter, split_frontmatter

MARKER = "reuse-first.json"
FORMAT = 2

# What a repository is. Skills and software are judged differently (references/evaluation.md).
KINDS = ["skill", "software", "list", "other"]
# What we take from it, strongest first. A card's status is its strongest take.
TAKES = ["use", "adapt", "learn", "later", "skip"]
# Where our own work stands. It decides what is worth borrowing.
STAGES = ["idea", "prototype", "working", "polishing"]
QUESTION_STATUS = ["open", "answered"]
VERDICTS = ["peeked", "short", "list", "later", "skip", "card"]
LEVELS = ["meta", "look", "read", "trial"]
# Languages a question searches in. Terms are told apart by script, so Latin-script languages count as en.
# Default en + zh: in real runs Chinese projects supplied half of the repos picked.
LANGS = ["en", "zh", "ja", "ko"]
DEFAULT_LANGS = ["en", "zh"]

CARD_ORDER = ["id", "repo", "kind", "form", "summary", "license", "stars", "created", "pushed", "branch", "commit",
              "reviewed", "level", "watch", "aliases", "uses"]
QUESTION_ORDER = ["id", "project", "ask", "stage", "status", "langs", "entities", "mechanisms", "forms", "problems",
                  "topics", "picked", "scanned"]
PROJECT_ORDER = ["id", "name", "summary", "code", "stack", "constraints", "languages"]

SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]+$")
ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA = re.compile(r"^[0-9a-f]{7,40}$")
KANA = re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\uff66-\uff9f]")
HANGUL = re.compile(r"[\u1100-\u11ff\u3130-\u318f\uac00-\ud7af]")
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")


class StoreError(RuntimeError):
    pass


def today() -> str:
    return _dt.date.today().isoformat()


def now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


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


# ---------------------------------------------------------------------------
# Locating the store


def _config_files() -> list[Path]:
    home = Path.home()
    xdg = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    files = []
    if os.environ.get("REUSE_FIRST_CONFIG"):
        files.append(Path(os.environ["REUSE_FIRST_CONFIG"]).expanduser())
    files.append(xdg / "reuse-first" / "config.env")
    files.append(Path(os.environ.get("AGENT_SKILLS_CONFIG_DIR") or xdg / "agent-skills") / "reuse-first" / "config.env")
    return files


def read_config() -> dict:
    """KEY=value lines; parsed, never executed. Unknown keys are an error."""
    allowed = {"REUSE_FIRST_STORE", "REUSE_FIRST_PROJECT"}
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
            out[key] = val.strip("'\"")
        return out
    return {}


def locate(explicit: str | None = None) -> Path:
    if explicit:
        root = Path(explicit).expanduser()
    elif os.environ.get("REUSE_FIRST_STORE"):
        root = Path(os.environ["REUSE_FIRST_STORE"]).expanduser()
    else:
        cfg = read_config()
        if cfg.get("REUSE_FIRST_STORE"):
            root = Path(cfg["REUSE_FIRST_STORE"]).expanduser()
        else:
            here = Path.cwd().resolve()
            found = next((p for p in [here, *here.parents] if (p / MARKER).is_file()), None)
            if not found:
                raise StoreError("no registry found. Create one with `reuse-first init <dir>` and set "
                                 "REUSE_FIRST_STORE=<dir> (or pass --store).")
            root = found
    if not (root / MARKER).is_file():
        raise StoreError(f"{root} is not a registry (no {MARKER}). Run `reuse-first init {root}`.")
    return root.resolve()


# ---------------------------------------------------------------------------


class Store:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.settings = json.loads((self.root / MARKER).read_text(encoding="utf-8"))
        if int(self.settings.get("format", 1)) > FORMAT:
            raise StoreError(f"{self.root} uses registry format {self.settings['format']}; this reuse-first reads "
                             f"format {FORMAT}. Upgrade reuse-first.")
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
        if marker.exists():
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
            raise StoreError(f"no question {project}/{qid} (create it: reuse-first ask {project}/{qid} \"...\")")
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
            project = self.settings.get("default_project") or read_config().get("REUSE_FIRST_PROJECT")
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
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    out.append({"_bad": line})
        return out

    def append_ledger(self, entries: list[dict]) -> None:
        if not entries:
            return
        with (self.root / "ledger.jsonl").open("a", encoding="utf-8") as f:
            f.write("".join(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n" for e in entries))

    def verdicts(self) -> dict[tuple[str, str], dict]:
        """Latest ledger entry per (repo, project/question)."""
        latest: dict[tuple[str, str], dict] = {}
        for e in self.ledger():
            if "repo" in e:
                latest[(e["repo"].lower(), f"{e.get('project', '')}/{e.get('question', '')}")] = e
        return latest

    def history(self, slug: str) -> list[dict]:
        s = slug.lower()
        return [e for e in self.ledger() if str(e.get("repo", "")).lower() == s]

    # -- scans -----------------------------------------------------------
    def scan_dir(self, project: str, qid: str) -> Path:
        return self.root / "scans" / project / qid

    def scans(self, project: str, qid: str) -> list[Path]:
        d = self.scan_dir(project, qid)   # only scan files (named by their id); other files may sit beside them
        return sorted(p for p in d.glob("*.json") if re.fullmatch(r"\d{8}-\d{6}", p.stem)) if d.is_dir() else []

    def save_scan(self, scan: dict) -> Path:
        d = self.scan_dir(scan["project"], scan["question"])
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{scan['id']}.json"
        p.write_text(json.dumps(scan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return p

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
    def check(self) -> tuple[list[str], list[str]]:
        errors: list[str] = []
        warns: list[str] = []

        def rel(p: Path) -> str:
            return str(p.relative_to(self.root))

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
            for key in ("repo", "kind", "summary", "license", "commit", "reviewed"):
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
        for n, e in enumerate(self.ledger(), 1):
            if "_bad" in e:
                errors.append(f"ledger.jsonl:{n}: not JSON")
            elif not e.get("repo") or e.get("verdict") not in VERDICTS:
                errors.append(f"ledger.jsonl:{n}: needs repo and a verdict in {', '.join(VERDICTS)}")
        return errors, warns


STORE_README = """# {name}

A reuse-first registry: the questions we asked, what we found on GitHub, what we took from
it, and every repository we looked at and why we passed.

- `INDEX.md` (generated) and `site/index.html` (`reuse-first site`) give the overview.
- `projects/<project>/questions/<q>.md`: one question, where we stand, and the answer.
- `repos/<owner>__<repo>.md`: one card per repository we looked at closely.
- `ledger.jsonl`: every verdict, so nobody looks at the same repository twice.
- `scans/`: what each search ran and found.
- `cache/`: downloaded source, not committed.

Agents: load the reuse-first skill and run `reuse-first find <words>` before reading anything here.
"""
