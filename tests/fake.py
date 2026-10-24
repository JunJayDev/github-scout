"""An offline stand-in for the GitHub and npm APIs."""

from __future__ import annotations

import io
import json
import sys
import tarfile
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills" / "github-scout" / "scripts"))

from github_scout.github import Client  # noqa: E402


def repo(slug, stars=100, desc="", created="2026-01-01T00:00:00Z", pushed="2026-10-01T00:00:00Z", topics=(),
         license="MIT", archived=False, fork=False, branch="main", lang="Python"):
    owner, name = slug.split("/")
    return {"full_name": slug, "name": name, "owner": {"login": owner}, "description": desc,
            "stargazers_count": stars, "created_at": created, "pushed_at": pushed, "topics": list(topics),
            "license": {"spdx_id": license} if license else None, "archived": archived, "fork": fork,
            "default_branch": branch, "language": lang, "html_url": f"https://github.com/{slug}",
            "forks_count": 1, "open_issues_count": 2, "homepage": ""}


def commit(sha: str, date: str, message: str = "change") -> dict:
    return {"sha": sha, "commit": {"message": message, "committer": {"date": f"{date}T00:00:00Z"}}}


def tarball(files: dict[str, str], prefix="owner-repo-abc1234") -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for path, text in files.items():
            data = text.encode()
            info = tarfile.TarInfo(f"{prefix}/{path}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class FakeAPI:
    """Routes: exact path -> payload, plus search handlers. Records every call."""

    def __init__(self):
        self.repos: dict[str, dict] = {}
        self.search: dict[str, list] = {}       # query -> list of repo dicts
        self.best: dict[str, list] = {}         # query -> repos in best-match order (no sort); else as in search
        self.totals: dict[str, int] = {}        # query -> total_count, when more repos match than are listed
        self.code: dict[str, list] = {}         # query -> list of slugs
        self.npm: dict[str, list] = {}          # text -> list of repo urls
        self.skills: dict[str, list] = {}       # text -> list of (owner/repo, installs)
        self.mcp: dict[str, list] = {}          # text -> list of repo urls
        self.paths: dict[str, object] = {}      # api path -> payload (dict/list/str/bytes)
        self.history: dict[str, object] = {}    # upstream path -> commits touching it (list), or an HTTP status (int)
        self.sites: dict[str, int] = {}         # a site outside GitHub -> the status it answers with (else 404)
        self.downloads: dict[str, int] = {}     # npm package -> downloads last month
        self.calls: list[str] = []
        self.down: set[str] = set()             # hosts that do not answer (a timeout)
        self.token_hosts: set[str] = set()      # hosts a token was sent to

    def add(self, r: dict):
        self.repos[r["full_name"].lower()] = r
        return r

    def __call__(self, method, url, headers, body):
        self.calls.append(f"{method} {url}")
        u = urlparse(url)
        if u.netloc in self.down:
            raise TimeoutError("timed out")
        if "Authorization" in headers:
            self.token_hosts.add(u.netloc)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        path = u.path.lstrip("/")
        if url in self.sites:
            return self.sites[url], {}, b""
        if u.netloc == "api.npmjs.org":
            name = path.split("last-month/", 1)[-1]
            return self._ok({"downloads": self.downloads[name]}) if name in self.downloads else (404, {}, b'{"error":"no"}')
        if u.netloc == "skills.sh":
            items = [{"source": slug, "skillId": "x", "installs": n} for slug, n in self.skills.get(q.get("q", ""), [])]
            return self._ok({"skills": items})
        if u.netloc == "registry.modelcontextprotocol.io":
            items = [{"server": {"repository": {"url": url}}} for url in self.mcp.get(q.get("search", ""), [])]
            return self._ok({"servers": items})
        if u.netloc == "registry.npmjs.org":
            objs = [{"package": {"links": {"repository": r}}} for r in self.npm.get(q.get("text", ""), [])]
            return self._ok({"objects": objs})
        if path == "graphql":
            query = json.loads(body.decode())["query"]
            data = {}
            for line in query.splitlines():
                line = line.strip()
                if not line.startswith("r") or "repository(" not in line:
                    continue
                alias = line.split(":", 1)[0]
                owner = line.split('owner: "', 1)[1].split('"', 1)[0]
                name = line.split('name: "', 1)[1].split('"', 1)[0]
                r = self.repos.get(f"{owner}/{name}".lower())
                data[alias] = None if not r else {
                    "nameWithOwner": r["full_name"], "description": r["description"],
                    "stargazerCount": r["stargazers_count"], "createdAt": r["created_at"], "pushedAt": r["pushed_at"],
                    "isArchived": r["archived"], "isFork": r["fork"], "homepageUrl": "",
                    "licenseInfo": {"spdxId": (r.get("license") or {}).get("spdx_id")} if r.get("license") else None,
                    "primaryLanguage": {"name": r["language"]},
                    "repositoryTopics": {"nodes": [{"topic": {"name": t}} for t in r["topics"]]},
                    "defaultBranchRef": {"name": r["default_branch"]}}
            return self._ok({"data": data})
        if path == "search/repositories":
            items = self.search.get(q["q"], []) if "sort" in q else self.best.get(q["q"], self.search.get(q["q"], []))
            return self._ok({"total_count": self.totals.get(q["q"], len(items)), "items": items})
        if path == "search/code":
            return self._ok({"items": [{"repository": {"full_name": s}} for s in self.code.get(q["q"], [])]})
        if path.endswith("/commits") and "path" in q:
            v = self.history.get(q["path"], [])
            return (v, {}, b'{"message":"Forbidden"}') if isinstance(v, int) else self._ok(v)
        if path in self.paths:
            v = self.paths[path]
            if isinstance(v, bytes):
                return 200, {}, v
            if isinstance(v, str):
                return 200, {}, v.encode()
            return self._ok(v)
        if path.startswith("repos/") and path.count("/") == 2:
            r = self.repos.get(path[6:].lower())
            return self._ok(r) if r else (404, {}, b'{"message":"Not Found"}')
        return 404, {}, b'{"message":"Not Found"}'

    @staticmethod
    def _ok(payload):
        return 200, {}, json.dumps(payload).encode()


def client(api: FakeAPI, token="test-token") -> Client:
    return Client(token=token, transport=api, verbose=False)
