"""GitHub (and npm) access with the standard library only.

Auth: GITHUB_TOKEN or GH_TOKEN, else `gh auth token` when the GitHub CLI is
installed and logged in, else anonymous (search code needs a token).
Search endpoints are throttled to stay under GitHub's per-minute limits.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import __version__

API = os.environ.get("REUSE_FIRST_GITHUB_API", "https://api.github.com")
NPM = os.environ.get("REUSE_FIRST_NPM_API", "https://registry.npmjs.org")
SKILLS = os.environ.get("REUSE_FIRST_SKILLS_API", "https://skills.sh/api")
MCP = os.environ.get("REUSE_FIRST_MCP_API", "https://registry.modelcontextprotocol.io/v0")
UA = f"reuse-first/{__version__}"

# Seconds between calls; GitHub allows 30 search/min and 10 code-search/min with a token.
SEARCH_GAP = 2.2
CODE_GAP = 6.5


class GitHubError(RuntimeError):
    def __init__(self, status: int, message: str):
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


def _token() -> str | None:
    for var in ("GITHUB_TOKEN", "GH_TOKEN"):
        if os.environ.get(var):
            return os.environ[var]
    gh = shutil.which("gh")
    if gh:
        try:
            out = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, timeout=10)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


class Client:
    """Thin REST/GraphQL client. `transport` can be swapped in tests."""

    def __init__(self, token: str | None = None, transport=None, verbose: bool = True):
        self.token = token if token is not None else _token()
        self.transport = transport or self._urlopen
        self.verbose = verbose
        self.calls = 0
        self._last = {"search": 0.0, "code": 0.0}

    # -- transport -------------------------------------------------------
    def _urlopen(self, method: str, url: str, headers: dict, body: bytes | None):
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.status, dict(resp.headers), resp.read()
        except urllib.error.HTTPError as exc:
            return exc.code, dict(exc.headers or {}), exc.read()

    def _headers(self, accept: str = "application/vnd.github+json") -> dict:
        h = {"Accept": accept, "User-Agent": UA, "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _log(self, msg: str):
        if self.verbose:
            print(msg, file=sys.stderr)

    def request(self, method: str, url: str, *, accept: str | None = None, body: dict | None = None,
                headers: dict | None = None, retries: int = 3):
        h = headers or self._headers(accept or "application/vnd.github+json")
        data = json.dumps(body).encode() if body is not None else None
        if data is not None:
            h["Content-Type"] = "application/json"
        for attempt in range(retries + 1):
            self.calls += 1
            status, rh, raw = self.transport(method, url, h, data)
            if status in (403, 429) and attempt < retries:
                wait = _retry_wait(rh, status)
                if wait is not None and wait <= 90:
                    self._log(f"rate limited; waiting {wait:.0f}s")
                    time.sleep(wait)
                    continue
            if status >= 500 and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            if status >= 400:
                raise GitHubError(status, _message(raw))
            return status, rh, raw
        raise GitHubError(599, "retries exhausted")

    # -- REST ------------------------------------------------------------
    def get(self, path: str, params: dict | None = None, accept: str | None = None):
        url = path if path.startswith("http") else f"{API}/{path.lstrip('/')}"
        if params:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        _, _, raw = self.request("GET", url, accept=accept)
        if accept and "raw" in accept:
            return raw.decode("utf-8", "replace")
        return json.loads(raw.decode() or "null")

    def get_or_none(self, path: str, params: dict | None = None, accept: str | None = None):
        try:
            return self.get(path, params, accept)
        except GitHubError as exc:
            if exc.status in (404, 409, 451):
                return None
            raise

    def _throttle(self, kind: str):
        gap = CODE_GAP if kind == "code" else SEARCH_GAP
        wait = self._last[kind] + gap - time.monotonic()
        if wait > 0 and self.transport == self._urlopen:
            time.sleep(wait)
        self._last[kind] = time.monotonic()

    def search_repos(self, q: str, sort: str = "stars", per_page: int = 30) -> list[dict]:
        self._throttle("search")
        params = {"q": q, "per_page": per_page}
        if sort:
            params.update(sort=sort, order="desc")
        return (self.get("search/repositories", params) or {}).get("items", [])

    def search_code(self, q: str, per_page: int = 30) -> list[str]:
        if not self.token:
            raise GitHubError(401, "code search needs a token (GITHUB_TOKEN or `gh auth login`)")
        self._throttle("code")
        items = (self.get("search/code", {"q": q, "per_page": per_page}) or {}).get("items", [])
        return sorted({i["repository"]["full_name"] for i in items if i.get("repository")})

    def repo(self, slug: str) -> dict | None:
        return self.get_or_none(f"repos/{slug}")

    def readme(self, slug: str, ref: str | None = None) -> str | None:
        return self.get_or_none(f"repos/{slug}/readme", {"ref": ref} if ref else None,
                                accept="application/vnd.github.raw")

    def file(self, slug: str, path: str, ref: str | None = None) -> str | None:
        return self.get_or_none(f"repos/{slug}/contents/{urllib.parse.quote(path)}",
                                {"ref": ref} if ref else None, accept="application/vnd.github.raw")

    def tree(self, slug: str, ref: str) -> dict | None:
        return self.get_or_none(f"repos/{slug}/git/trees/{ref}", {"recursive": "1"})

    def head(self, slug: str, branch: str) -> str | None:
        data = self.get_or_none(f"repos/{slug}/commits/{urllib.parse.quote(branch)}")
        return data.get("sha") if data else None

    def latest_release(self, slug: str) -> dict | None:
        return self.get_or_none(f"repos/{slug}/releases/latest")

    def releases(self, slug: str, per_page: int = 20) -> list[dict]:
        return self.get_or_none(f"repos/{slug}/releases", {"per_page": per_page}) or []

    def compare(self, slug: str, base: str, head: str) -> dict | None:
        return self.get_or_none(f"repos/{slug}/compare/{base}...{head}")

    def starred(self, user: str, pages: int = 3) -> list[dict]:
        out: list[dict] = []
        for page in range(1, pages + 1):
            batch = self.get_or_none(f"users/{user}/starred", {"per_page": 100, "page": page}) or []
            out.extend(batch)
            if len(batch) < 100:
                break
        return out

    def graphql_repos(self, slugs: list[str]) -> dict[str, dict]:
        """Metadata for many repos, 40 per query. Returns {lower slug: REST-shaped dict}."""
        out: dict[str, dict] = {}
        fields = ("nameWithOwner description stargazerCount createdAt pushedAt isArchived isFork "
                  "homepageUrl licenseInfo{spdxId} primaryLanguage{name} "
                  "repositoryTopics(first:12){nodes{topic{name}}} defaultBranchRef{name}")
        for start in range(0, len(slugs), 40):
            chunk = slugs[start : start + 40]
            parts = []
            for n, slug in enumerate(chunk):
                owner, name = slug.split("/", 1)
                parts.append(f'r{n}: repository(owner: {json.dumps(owner)}, name: {json.dumps(name)}) {{ {fields} }}')
            query = "query {\n" + "\n".join(parts) + "\n}"
            if not self.token:
                for slug in chunk:  # anonymous GraphQL is not allowed; fall back to REST
                    data = self.repo(slug)
                    if data:
                        out[data["full_name"].lower()] = data
                        out.setdefault(slug.lower(), data)
                continue
            _, _, raw = self.request("POST", f"{API}/graphql", body={"query": query})
            payload = json.loads(raw.decode())
            for n, slug in enumerate(chunk):
                node = (payload.get("data") or {}).get(f"r{n}")
                if node:
                    rest = _graphql_to_rest(node)
                    out[rest["full_name"].lower()] = rest
                    out.setdefault(slug.lower(), rest)
        return out

    def tarball(self, slug: str, ref: str, dest: Path) -> Path:
        """Download and safely extract a tarball of `ref` into `dest` (created)."""
        _, _, raw = self.request("GET", f"{API}/repos/{slug}/tarball/{ref}",
                                 headers=self._headers("application/vnd.github+json"))
        dest.mkdir(parents=True, exist_ok=False)
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tar:
            root = dest.resolve()
            for member in tar.getmembers():
                parts = member.name.split("/", 1)
                if len(parts) < 2 or not parts[1]:
                    continue
                member.name = parts[1]
                target = (dest / member.name).resolve()
                if root not in target.parents and target != root:
                    continue  # path traversal
                if member.issym() or member.islnk():
                    continue  # links are not needed for reading source
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    src = tar.extractfile(member)
                    if src is not None:
                        target.write_bytes(src.read())
        return dest

    # -- directories -----------------------------------------------------
    def _get_json(self, url: str):
        _, _, raw = self.request("GET", url, headers={"User-Agent": UA, "Accept": "application/json"})
        return json.loads(raw.decode() or "null")

    def skills_search(self, text: str, limit: int = 30) -> list[tuple[str, int, str]]:
        """skills.sh search: [(owner/repo, installs, skill id)], most installed first."""
        data = self._get_json(f"{SKILLS}/search?" + urllib.parse.urlencode({"q": text, "limit": limit})) or {}
        out = []
        for item in data.get("skills", []):
            slug = github_slug(f"github.com/{item.get('source', '')}")
            if slug:
                out.append((slug, int(item.get("installs") or 0), str(item.get("skillId") or item.get("name") or "")))
        return out

    def mcp_search(self, text: str, limit: int = 30) -> list[str]:
        """Official MCP registry search: GitHub repositories of matching servers."""
        data = self._get_json(f"{MCP}/servers?" + urllib.parse.urlencode({"search": text, "limit": limit})) or {}
        slugs = []
        for item in data.get("servers", []):
            url = ((item.get("server") or {}).get("repository") or {}).get("url") or ""
            slug = github_slug(url)
            if slug and slug.lower() not in {s.lower() for s in slugs}:
                slugs.append(slug)
        return slugs

    # -- npm -------------------------------------------------------------
    def npm_search(self, text: str, size: int = 20) -> list[str]:
        url = f"{NPM}/-/v1/search?" + urllib.parse.urlencode({"text": text, "size": size})
        _, _, raw = self.request("GET", url, headers={"User-Agent": UA, "Accept": "application/json"})
        slugs = []
        for obj in json.loads(raw.decode()).get("objects", []):
            links = obj.get("package", {}).get("links", {})
            slug = github_slug(links.get("repository") or "") or github_slug(links.get("homepage") or "")
            if slug:
                slugs.append(slug)
        return slugs


def _retry_wait(headers: dict, status: int) -> float | None:
    """Seconds to wait before retrying a 403/429, or None when it is not a rate limit."""
    low = {k.lower(): v for k, v in headers.items()}
    if "retry-after" in low:
        try:
            return float(low["retry-after"]) + 1
        except ValueError:
            return None
    if low.get("x-ratelimit-remaining") == "0" and "x-ratelimit-reset" in low:
        try:
            return max(1.0, float(low["x-ratelimit-reset"]) - time.time() + 1)
        except ValueError:
            return None
    return 30.0 if status == 429 else None


def _message(raw: bytes) -> str:
    try:
        return json.loads(raw.decode()).get("message", "")[:300]
    except (ValueError, AttributeError):
        return raw[:300].decode("utf-8", "replace")


def _graphql_to_rest(node: dict) -> dict:
    return {
        "full_name": node["nameWithOwner"],
        "description": node.get("description"),
        "stargazers_count": node.get("stargazerCount", 0),
        "created_at": node.get("createdAt"),
        "pushed_at": node.get("pushedAt"),
        "archived": node.get("isArchived", False),
        "fork": node.get("isFork", False),
        "homepage": node.get("homepageUrl"),
        "license": {"spdx_id": (node.get("licenseInfo") or {}).get("spdxId")},
        "language": (node.get("primaryLanguage") or {}).get("name"),
        "topics": [t["topic"]["name"] for t in (node.get("repositoryTopics") or {}).get("nodes", [])],
        "default_branch": (node.get("defaultBranchRef") or {}).get("name"),
    }


_SLUG_RE = None


def github_slug(text: str) -> str | None:
    """'https://github.com/a/b(.git|/tree/..)', 'git+https://...', 'github.com/a/b', 'a/b' -> 'a/b'."""
    import re

    global _SLUG_RE
    if _SLUG_RE is None:
        _SLUG_RE = re.compile(
            r"^(?:git\+)?(?:(?:https?|git|ssh)://)?(?:git@)?(?:www\.)?(?:github\.com[/:])?"
            r"([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9_.-]+?)(?:\.git)?(?:[/#?].*)?$"
        )
    s = text.strip()
    if not s:
        return None
    if "://" in s or s.startswith(("git@", "github.com", "www.github.com", "git+")):
        if "github.com" not in s:
            return None
    m = _SLUG_RE.match(s)
    if not m:
        return None
    owner, name = m.group(1), m.group(2)
    if name in (".", "..") or owner.lower() in ("orgs", "topics", "sponsors", "features", "marketplace", "settings", "about", "apps", "collections", "trending", "search", "login", "site", "explore"):
        return None
    return f"{owner}/{name}"
