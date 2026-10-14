"""The registry store: a plain directory (usually a git repo) of Markdown and JSON.

    reuse-first.json                 marker + settings
    INDEX.md                         generated overview (reuse-first index)
    projects/<project>/project.md    what a project is and its constraints
    projects/<project>/needs/<need>.md   one capability: search vocabulary + decision
    repos/<owner>__<repo>.md         one card per reviewed repository
    ledger.jsonl                     every triage verdict, append-only
    scans/<project>/<need>/<stamp>.json  what each search ran and found
    people.txt                       GitHub logins whose stars feed the people lens
    cache/                           downloaded source (not committed)

See docs/store-format.md for the full specification.
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
FORMAT = 1

KINDS = {
    "skill": "agent", "skill-pack": "agent", "rules": "agent",
    "mcp": "software", "cli": "software", "app": "software", "extension": "software",
    "library": "software", "framework": "software", "service": "software",
    "list": "other", "example": "other", "data": "other",
}
FAMILY_TITLES = {"agent": "Agent-facing (skills, skill packs, rules)", "software": "Software (tools, servers, libraries, apps)",
                 "other": "Other (lists, examples, data)"}
# Strongest first: a card's overall status is its strongest relation.
RELATIONS = ["adopt", "extend", "derive", "migrate", "borrow", "watch", "reject"]
NEED_STATUS = ["open", "partial", "covered", "gap", "building"]
VERDICTS = ["peeked", "short", "list", "defer", "skip", "card"]
LEVELS = ["meta", "peek", "read", "trial"]

CARD_ORDER = ["id", "repo", "kind", "summary", "license", "stars", "pushed", "created", "branch", "commit",
              "reviewed", "level", "watch", "aliases", "uses"]
NEED_ORDER = ["id", "project", "want", "status", "entities", "mechanisms", "forms", "problems", "topics",
              "chosen", "scanned"]
PROJECT_ORDER = ["id", "name", "summary", "where", "stack", "constraints", "languages"]

SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]+$")
ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SHA = re.compile(r"^[0-9a-f]{7,40}$")


class StoreError(RuntimeError):
    pass


def today() -> str:
    return _dt.date.today().isoformat()


def now_stamp() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def card_filename(slug: str) -> str:
    owner, name = slug.lower().split("/", 1)
    return f"{owner}__{name}.md"


def family(kind: str | None) -> str:
    return KINDS.get(kind or "", "other")


def as_list(v) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


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


def strongest(relations: list[str]) -> str | None:
    ranked = [r for r in RELATIONS if r in relations]
    return ranked[0] if ranked else None


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
        self._cards: list[Doc] | None = None

    # -- init ------------------------------------------------------------
    @staticmethod
    def init(root: Path, name: str | None = None) -> "Store":
        root = Path(root).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        marker = root / MARKER
        if marker.exists():
            raise StoreError(f"{root} is already a registry")
        for sub in ("projects", "repos", "scans", "cache"):
            (root / sub).mkdir(exist_ok=True)
        marker.write_text(json.dumps({"format": FORMAT, "name": name or root.name, "default_project": None},
                                     indent=2) + "\n", encoding="utf-8")
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
        path = self.root / "repos" / card_filename(ref) if "/" in ref else None
        if path and path.is_file():
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

    # -- projects and needs ---------------------------------------------
    def projects(self) -> list[Doc]:
        d = self.root / "projects"
        return [read_doc(p / "project.md") for p in sorted(d.iterdir()) if (p / "project.md").is_file()] if d.is_dir() else []

    def project(self, pid: str) -> Doc | None:
        p = self.root / "projects" / pid / "project.md"
        return read_doc(p) if p.is_file() else None

    def needs(self, project: str | None = None) -> list[Doc]:
        out = []
        for proj in self.projects():
            pid = proj.path.parent.name
            if project and pid != project:
                continue
            nd = proj.path.parent / "needs"
            if nd.is_dir():
                out.extend(read_doc(p) for p in sorted(nd.glob("*.md")))
        return out

    def need_path(self, project: str, need: str) -> Path:
        return self.root / "projects" / project / "needs" / f"{need}.md"

    def need(self, ref: str) -> Doc:
        project, need = self.split_ref(ref)
        p = self.need_path(project, need)
        if not p.is_file():
            raise StoreError(f"no need {project}/{need} (create it: reuse-first new-need {project}/{need} --want \"...\")")
        doc = read_doc(p)
        if doc.error:
            raise StoreError(f"{p}: {doc.error}")
        return doc

    def split_ref(self, ref: str) -> tuple[str, str]:
        if "/" in ref:
            project, need = ref.split("/", 1)
        else:
            project = self.settings.get("default_project") or read_config().get("REUSE_FIRST_PROJECT")
            need = ref
            if not project:
                raise StoreError(f"write the need as <project>/<need> (no default project set): {ref}")
        return project, need

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
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False, sort_keys=True) + "\n")

    def verdicts(self) -> dict[tuple[str, str], dict]:
        """Latest ledger entry per (repo, project/need)."""
        latest: dict[tuple[str, str], dict] = {}
        for e in self.ledger():
            if "repo" in e:
                latest[(e["repo"].lower(), f"{e.get('project', '')}/{e.get('need', '')}")] = e
        return latest

    def history(self, slug: str) -> list[dict]:
        s = slug.lower()
        return [e for e in self.ledger() if str(e.get("repo", "")).lower() == s]

    # -- scans -----------------------------------------------------------
    def scan_dir(self, project: str, need: str) -> Path:
        return self.root / "scans" / project / need

    def scans(self, project: str, need: str) -> list[Path]:
        d = self.scan_dir(project, need)
        return sorted(d.glob("*.json")) if d.is_dir() else []

    def save_scan(self, scan: dict) -> Path:
        d = self.scan_dir(scan["project"], scan["need"])
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{scan['id']}.json"
        p.write_text(json.dumps(scan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        return p

    def people(self) -> list[str]:
        p = self.root / "people.txt"
        if not p.is_file():
            return []
        return [l.split("#", 1)[0].strip() for l in p.read_text(encoding="utf-8").splitlines() if l.split("#", 1)[0].strip()]

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
        rel = lambda p: str(p.relative_to(self.root))  # noqa: E731
        projects = {p.path.parent.name: p for p in self.projects()}
        for pid, doc in projects.items():
            if doc.error:
                errors.append(f"{rel(doc.path)}: {doc.error}")
                continue
            if doc.id != pid:
                errors.append(f"{rel(doc.path)}: id must be {pid!r}")
            if not ID.match(pid):
                errors.append(f"{rel(doc.path)}: project ids use lowercase letters, digits, . _ -")
        need_ids: set[str] = set()
        for doc in self.needs():
            pid = doc.path.parent.parent.name
            nid = doc.path.stem
            need_ids.add(f"{pid}/{nid}")
            if doc.error:
                errors.append(f"{rel(doc.path)}: {doc.error}")
                continue
            d = doc.data
            if d.get("id") != nid:
                errors.append(f"{rel(doc.path)}: id must be {nid!r}")
            if d.get("project") != pid:
                errors.append(f"{rel(doc.path)}: project must be {pid!r}")
            if not d.get("want"):
                errors.append(f"{rel(doc.path)}: missing want")
            if d.get("status") not in NEED_STATUS:
                errors.append(f"{rel(doc.path)}: status must be one of {', '.join(NEED_STATUS)}")
            for key in ("entities", "mechanisms", "forms", "problems", "topics", "chosen"):
                if d.get(key) is not None and not isinstance(d.get(key), list):
                    errors.append(f"{rel(doc.path)}: {key} must be a list")
            if not (as_list(d.get("entities")) or as_list(d.get("mechanisms")) or as_list(d.get("problems"))):
                warns.append(f"{rel(doc.path)}: no search vocabulary (entities, mechanisms, problems)")
            for slug in as_list(d.get("chosen")):
                if not self.card(str(slug)):
                    warns.append(f"{rel(doc.path)}: chosen {slug} has no card")
            if d.get("scanned") and not DATE.match(str(d.get("scanned"))):
                errors.append(f"{rel(doc.path)}: scanned must be YYYY-MM-DD")
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
                warns.append(f"{r}: no uses (relate it to a project, even as watch or reject)")
            for u in as_list(uses):
                if not isinstance(u, dict):
                    errors.append(f"{r}: each uses item is a mapping (project, need, relation, where, note)")
                    continue
                if u.get("relation") not in RELATIONS:
                    errors.append(f"{r}: relation must be one of {', '.join(RELATIONS)}")
                if not u.get("project"):
                    errors.append(f"{r}: uses item without project")
                elif u["project"] not in projects:
                    warns.append(f"{r}: project {u['project']!r} has no profile")
                elif u.get("need") and f"{u['project']}/{u['need']}" not in need_ids:
                    warns.append(f"{r}: need {u['project']}/{u['need']} does not exist")
                if u.get("relation") in ("reject", "borrow", "migrate") and not u.get("note"):
                    warns.append(f"{r}: {u.get('relation')} without a note (say why / what)")
        for n, e in enumerate(self.ledger(), 1):
            if "_bad" in e:
                errors.append(f"ledger.jsonl:{n}: not JSON")
            elif not e.get("repo") or e.get("verdict") not in VERDICTS:
                errors.append(f"ledger.jsonl:{n}: needs repo and a verdict in {', '.join(VERDICTS)}")
        return errors, warns


STORE_README = """# {name}

A reuse-first registry: every open-source repository
we looked at, what we decided, and what we searched for.

Start with `INDEX.md` (generated). Agents: load the reuse-first skill and run
`reuse-first find <words>` before reading anything here by hand.

- `projects/<project>/project.md`: what the project is and its constraints.
- `projects/<project>/needs/<need>.md`: one capability, its search vocabulary, and the decision.
- `repos/<owner>__<repo>.md`: one card per reviewed repository.
- `ledger.jsonl`: every triage verdict, so nobody reviews the same repo twice.
- `scans/`: what each search ran and found.
- `cache/`: downloaded source, not committed (`reuse-first fetch` restores it).
"""
