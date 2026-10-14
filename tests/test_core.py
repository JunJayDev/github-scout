import contextlib
import io
import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path

from fake import FakeAPI, client, repo, tarball

from reuse_first import cli, discover, examine, registry, yamlish
from reuse_first.github import github_slug
from reuse_first.store import Store, StoreError, card_filename

NEED = {
    "id": "browser-ops", "project": "ops", "want": "drive logged-in sites from scripts",
    "entities": ["reddit", "xiaohongshu|小红书|rednote", "twitter|x.com"],
    "mechanisms": ["logged-in browser", "chrome extension"],
    "forms": ["cli", "skill"],
    "problems": ["social media automation"],
}


class YamlishTests(unittest.TestCase):
    def test_round_trip_keeps_values(self):
        data = {"id": "a/b", "summary": 'He said: "hi" # not a comment', "stars": 12, "date": "2026-10-15",
                "flag": True, "none": None, "tags": ["x", "y z", "小红书"], "empty": [],
                "uses": [{"project": "ops", "need": "n", "relation": "adopt", "note": "a: b", "paths": ["s/*.ts"]}]}
        text = yamlish.dump(data)
        self.assertEqual(yamlish.parse(text), data)

    def test_dates_and_numbers_like_strings_stay_strings(self):
        self.assertEqual(yamlish.parse(yamlish.dump({"d": "2026-10-15", "n": "123", "t": "true"})),
                         {"d": "2026-10-15", "n": "123", "t": "true"})

    def test_hand_written_variants(self):
        text = "a: plain text # comment\nb: 'it''s'\nc:\n  - one\n  - \"two\"\nd: [1, 'x, y']\n"
        self.assertEqual(yamlish.parse(text), {"a": "plain text", "b": "it's", "c": ["one", "two"], "d": [1, "x, y"]})

    def test_rejects_what_it_cannot_represent(self):
        for bad in ("a: |\n  x\n", "a:\n  b: 1\n", "a: {x: 1}\n", "a: 1\na: 2\n", "\tb: 1\n",
                    "u:\n  - k: v\n      deeper: 1\n"):
            with self.subTest(bad=bad), self.assertRaises(yamlish.FormatError):
                yamlish.parse(bad)

    def test_frontmatter(self):
        data, body = yamlish.split_frontmatter("---\nid: x\n---\n# Title\n")
        self.assertEqual((data, body), ({"id": "x"}, "# Title\n"))
        with self.assertRaises(yamlish.FormatError):
            yamlish.split_frontmatter("id: x\n")


class SlugTests(unittest.TestCase):
    def test_slug_forms(self):
        for text, want in [("https://github.com/jackwener/opencli", "jackwener/opencli"),
                           ("git+https://github.com/a/b.git", "a/b"), ("github.com/a/b/tree/main/x", "a/b"),
                           ("git@github.com:a/b.git", "a/b"), ("a-b/c.d", "a-b/c.d"),
                           ("https://gitlab.com/a/b", None), ("https://github.com/topics/cli", None)]:
            self.assertEqual(github_slug(text), want, text)

    def test_slugs_in_text_dedupes_and_skips_non_repos(self):
        text = "see https://github.com/A/b and github.com/a/B#x, https://github.com/sponsors/me, github.com/c/d.git"
        self.assertEqual(discover.slugs_in_text(text), ["A/b", "c/d"])


class PlanAndScoreTests(unittest.TestCase):
    def test_plan_crosses_vocabularies(self):
        q = discover.plan(NEED)
        queries = {(x["lens"], x["query"]) for x in q}
        self.assertIn(("E", "小红书"), queries)
        self.assertIn(("P", "reddit xiaohongshu in:readme"), queries)
        self.assertIn(("M", '"logged-in browser" in:readme'), queries)
        self.assertIn(("C", '"chrome extension" twitter in:readme'), queries)
        self.assertIn(("Q", "social media automation"), queries)
        self.assertIn(("T", "topic:chrome-extension"), queries)
        self.assertIn(("K", "reddit filename:SKILL.md"), queries)
        self.assertIn(("S", "xiaohongshu"), queries)
        self.assertNotIn("D", {l for l, _ in queries})            # forms has no mcp
        self.assertTrue(any(l == "R" and "created:>" in s for l, s in queries))
        self.assertEqual(len(queries), len(q), "no duplicate searches")

    def test_plan_respects_lens_selection_and_skips_skill_code_for_software_only(self):
        self.assertEqual({x["lens"] for x in discover.plan(NEED, "EP")}, {"E", "P"})
        need = {**NEED, "forms": ["library"]}
        self.assertNotIn("K", {x["lens"] for x in discover.plan(need)})

    def test_fit_counts_own_text_not_readme(self):
        c = {"repo": "jackwener/opencli", "desc": "Make Any Website into CLI & Use your logged-in browser", "topics": ["cli"]}
        self.assertEqual(discover.fit(c, NEED), 1)
        c2 = {"repo": "x/rednote-tool", "desc": "Post to Reddit and 小红书 via a Chrome extension", "topics": []}
        self.assertEqual(discover.fit(c2, NEED), 3)
        self.assertEqual(discover.fit({"repo": "x/xcom", "desc": "boxcom reddits", "topics": []}, NEED), 0)

    def test_relevant_small_repo_beats_famous_unrelated_one(self):
        big = {"repo": "public/apis", "desc": "A collective list of free APIs", "stars": 400000,
               "created": "2016-01-01", "pushed": "2026-10-01", "license": "MIT", "lenses": ["P", "M", "C"], "topics": []}
        small = {"repo": "a/xhs-cli", "desc": "Xiaohongshu and Reddit CLI using your logged-in browser", "stars": 900,
                 "created": "2026-05-01", "pushed": "2026-10-01", "license": "MIT", "lenses": ["E", "P"], "topics": []}
        self.assertGreater(discover.score(small, NEED), discover.score(big, NEED))
        self.assertTrue(discover.is_list(big))
        self.assertTrue(discover.is_list({"repo": "x/awesome-mcp", "desc": ""}))
        self.assertFalse(discover.is_list(small))


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "reg"
        self.store = Store.init(self.root, "test")
        registry.new_project(self.store, "ops", "Ops", "test project")
        path = registry.new_need(self.store, "ops/browser-ops", NEED["want"])
        doc = self.store.need("ops/browser-ops")
        doc.data.update({k: v for k, v in NEED.items() if k not in ("id", "project", "want")})
        from reuse_first.store import NEED_ORDER, write_doc
        write_doc(path, doc.data, doc.body, NEED_ORDER)
        self.api = FakeAPI()
        self.old_factory = cli.make_client
        cli.make_client = lambda args: client(self.api)
        self.env = {k: os.environ.pop(k) for k in ["REUSE_FIRST_STORE"] if k in os.environ}

    def tearDown(self):
        cli.make_client = self.old_factory
        os.environ.update(self.env)
        self.tmp.cleanup()

    def run_cli(self, *argv) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--store", str(self.root), *argv] if argv[0] not in ("init",) else list(argv))
        return code, out.getvalue(), err.getvalue()


class StoreTests(Base):
    def test_init_and_check_clean(self):
        self.assertTrue((self.root / "reuse-first.json").is_file())
        self.assertEqual((self.root / ".gitignore").read_text(), "cache/\n")
        errors, warns = self.store.check()
        self.assertEqual(errors, [])

    def test_check_reports_bad_cards(self):
        (self.root / "repos" / "a__b.md").write_text("---\nid: a/c\nkind: weird\nuses:\n  - project: ops\n    relation: love\n---\n")
        errors, _ = self.store.check()
        text = "\n".join(errors)
        for needle in ("file name must be a__c.md", "kind must be", "relation must be", "missing commit"):
            self.assertIn(needle, text)

    def test_locate_by_marker_in_parent(self):
        from reuse_first.store import locate
        sub = self.root / "projects" / "ops"
        cwd = os.getcwd()
        try:
            os.chdir(sub)
            with unittest.mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.root / "nocfg")}):
                self.assertEqual(locate(None), self.root.resolve())
        finally:
            os.chdir(cwd)
        with self.assertRaises(StoreError):
            locate(str(Path(self.tmp.name)))


class FlowTests(Base):
    def seed_search(self):
        opencli = self.api.add(repo("jackwener/OpenCLI", 30000, "Make Any Website into CLI & Use your logged-in browser by AI agent.",
                                    created="2026-03-14T00:00:00Z", topics=["cli", "browser-automation"], license="Apache-2.0"))
        noise = self.api.add(repo("public-apis/public-apis", 480000, "A collective list of free APIs", created="2016-03-20T00:00:00Z"))
        xhs = self.api.add(repo("xpzouying/xiaohongshu-mcp", 16000, "MCP for xiaohongshu.com", created="2025-08-03T00:00:00Z"))
        skill = self.api.add(repo("someone/reddit-skill", 50, "Reddit skill for agents", created="2026-06-01T00:00:00Z"))
        self.api.search['reddit xiaohongshu in:readme'] = [opencli, noise]
        self.api.search['"logged-in browser"'] = [opencli]
        self.api.search['xiaohongshu'] = [xhs]
        self.api.code['reddit filename:SKILL.md'] = ["someone/reddit-skill"]
        self.api.npm['reddit'] = ["git+https://github.com/someone/reddit-skill.git"]
        self.api.skills['reddit'] = [("someone/reddit-skill", 4200)]
        return opencli, noise, xhs, skill

    def test_scan_triage_peek_card_find_index(self):
        self.seed_search()
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.assertEqual(code, 0, out)
        self.assertIn("jackwener/OpenCLI", out)
        self.assertIn("lists to expand", out)                       # public-apis is a list, not a candidate
        rows = [l for l in out.splitlines() if l.strip()[:3].strip().rstrip(".").isdigit()]
        self.assertTrue(rows[0].strip().startswith("1."))
        self.assertNotIn("public-apis", "\n".join(rows))
        skill_row = next(r for r in rows if "someone/reddit-skill" in r)
        self.assertIn("[KSN]", skill_row)
        self.assertIn("installs 4.2k", skill_row)
        scan = json.loads(next((self.root / "scans/ops/browser-ops").glob("*.json")).read_text())
        self.assertTrue(all("query" in s for s in scan["searches"]))
        self.assertEqual(self.store.need("ops/browser-ops").data["scanned"], discover.today())

        # Triage by row number; the rest is skipped with one reason and hidden next time.
        order = [l.split()[6] for l in rows]
        n = order.index("jackwener/OpenCLI") + 1
        code, out, _ = self.run_cli("triage", "ops/browser-ops", "--short", str(n), "--rest", "not a browser driver")
        self.assertEqual(code, 0, out)
        self.assertIn("peek --need ops/browser-ops jackwener/OpenCLI", out)
        verdicts = {(e["repo"], e["verdict"]) for e in self.store.ledger()}
        self.assertIn(("jackwener/OpenCLI", "short"), verdicts)
        self.assertIn(("xpzouying/xiaohongshu-mcp", "skip"), verdicts)
        _, out, _ = self.run_cli("results", "ops/browser-ops")
        self.assertNotIn("xpzouying/xiaohongshu-mcp", out)
        self.assertIn("jackwener/OpenCLI", out)                     # shortlisted stays open until decided

        # Peek and card.
        self.seed_repo_files()
        code, out, _ = self.run_cli("peek", "--need", "ops/browser-ops", "jackwener/OpenCLI")
        self.assertEqual(code, 0, out)
        self.assertIn("(cli?)", out)
        self.assertIn("skills: skills/opencli/SKILL.md", out)
        code, out, _ = self.run_cli("card", "jackwener/OpenCLI", "--need", "ops/browser-ops", "--relation", "adopt",
                                    "--where", "tools/opencli", "--watch", "clis/reddit/**", "src/daemon.ts")
        self.assertEqual(code, 0, out)
        card = self.store.card("jackwener/opencli")
        self.assertEqual(card.path.name, card_filename("jackwener/OpenCLI"))
        self.assertEqual(card.data["kind"], "cli")
        self.assertEqual(card.data["uses"], [{"project": "ops", "need": "browser-ops", "relation": "adopt", "where": "tools/opencli"}])
        self.assertEqual(card.data["commit"], "b9213a15d63d")
        self.assertIn("## Adoption", card.body)

        # A second project relates to the same card instead of duplicating it.
        registry.new_project(self.store, "other", "Other", "")
        code, out, _ = self.run_cli("relate", "jackwener/OpenCLI", "--project", "other", "--relation", "borrow", "--note", "exit codes")
        self.assertEqual(code, 0, out)
        self.assertEqual(len(self.store.card("jackwener/OpenCLI").data["uses"]), 2)

        _, out, _ = self.run_cli("find", "logged-in", "browser")
        self.assertIn("jackwener/OpenCLI [cli] adopt", out)
        _, out, _ = self.run_cli("find", "free", "APIs")
        self.assertIn("public-apis/public-apis skip", out)
        self.assertEqual(self.run_cli("check")[0], 0)
        code, out, _ = self.run_cli("index")
        index = (self.root / "INDEX.md").read_text()
        self.assertIn("[ops/browser-ops]", index)
        self.assertIn("| [jackwener/OpenCLI](repos/jackwener__opencli.md) | cli | adopt |", index)
        _, out, _ = self.run_cli("show", "ops/browser-ops")
        self.assertIn("cards:", out)

    def seed_repo_files(self):
        slug = "jackwener/OpenCLI"
        self.api.paths[f"repos/{slug}/commits/main"] = {"sha": "b9213a15d63d0000000000000000000000000000"}
        self.api.paths[f"repos/{slug}/git/trees/b9213a15d63d0000000000000000000000000000"] = {"tree": [
            {"path": "package.json", "type": "blob", "size": 400}, {"path": "src/daemon.ts", "type": "blob", "size": 9000},
            {"path": "clis/reddit/read.js", "type": "blob", "size": 3000}, {"path": "skills/opencli/SKILL.md", "type": "blob", "size": 800},
            *[{"path": f"src/x{i}.ts", "type": "blob", "size": 100} for i in range(45)]], "truncated": False}
        self.api.paths[f"repos/{slug}/contents/package.json"] = json.dumps({"name": "@jackwener/opencli", "bin": {"opencli": "dist/cli.js"}})
        self.api.paths[f"repos/{slug}/readme"] = "<p align=center><img src=x></p>\n# OpenCLI\n\n![badge](y)\nTurn websites into commands.\n"

    def test_ingest_and_expand(self):
        self.seed_search()
        code, out, _ = self.run_cli("ingest", "ops/browser-ops", "found https://github.com/xpzouying/xiaohongshu-mcp on X", "--note", "x.com post")
        self.assertEqual(code, 0, out)
        self.assertIn("xpzouying/xiaohongshu-mcp", out)
        self.assertIn("[W]", out)
        self.api.add(repo("someone/awesome-social", 2000, "A curated list of social tools"))
        self.api.add(repo("z/unrelated", 9000, "A database"))
        self.api.paths["repos/someone/awesome-social/readme"] = (
            "- [OpenCLI](https://github.com/jackwener/OpenCLI)\n- [db](https://github.com/z/unrelated)\n")
        code, out, _ = self.run_cli("expand", "ops/browser-ops", "someone/awesome-social")
        self.assertEqual(code, 0, out)
        self.assertIn("jackwener/OpenCLI", out)
        self.assertNotIn("z/unrelated", out)                        # filtered by the need's vocabulary

    def test_mcp_registry_lens(self):
        self.api.add(repo("acme/xhs-mcp", 300, "MCP server for Xiaohongshu"))
        self.api.mcp["xiaohongshu"] = ["https://github.com/acme/xhs-mcp"]
        need = self.store.need("ops/browser-ops")
        need.data["forms"] = ["mcp"]
        from reuse_first.store import NEED_ORDER, write_doc
        write_doc(need.path, need.data, need.body, NEED_ORDER)
        code, out, _ = self.run_cli("scan", "ops/browser-ops", "--quiet", "--lenses", "D")
        self.assertEqual(code, 0, out)
        self.assertIn("acme/xhs-mcp", out)
        self.assertIn("[D]", out)

    def test_resurface_when_a_skipped_repo_grows(self):
        self.seed_search()
        self.run_cli("scan", "ops/browser-ops", "--quiet")
        self.run_cli("mark", "xpzouying/xiaohongshu-mcp", "--need", "ops/browser-ops", "--verdict", "skip", "--reason", "x")
        led = self.store.ledger()
        led[-1]["stars"] = 1000
        (self.root / "ledger.jsonl").write_text("".join(json.dumps(e) + "\n" for e in led))
        _, out, _ = self.run_cli("results", "ops/browser-ops")
        self.assertIn("grew, look again", out)

    def test_outdated_diff_bump(self):
        slug = "jackwener/OpenCLI"
        self.api.add(repo(slug, 31000, "x"))
        meta = {"repo": slug, "desc": "x", "stars": 30000, "license": "Apache-2.0", "branch": "main", "commit": "aaaaaaaaaaaa"}
        registry.new_card(self.store, meta, "cli", [{"project": "ops", "need": "browser-ops", "relation": "adopt"}],
                          ["clis/reddit/**"], "read")
        self.api.paths[f"repos/{slug}/compare/aaaaaaaaaaaa...main"] = {
            "ahead_by": 3, "commits": [{"sha": "c" * 40, "commit": {"message": "fix reddit"}}],
            "files": [{"filename": "clis/reddit/read.js", "status": "modified", "additions": 2, "deletions": 1,
                       "patch": "@@ -1 +1 @@\n-old\n+new"}, {"filename": "README.md", "status": "modified", "patch": "x"}]}
        self.api.paths[f"repos/{slug}/releases"] = [{"tag_name": "v2", "published_at": "2999-01-01T00:00:00Z"}]
        code, out, _ = self.run_cli("outdated")
        self.assertEqual(code, 0, out)
        self.assertIn("review", out)
        self.assertIn("watched: clis/reddit/read.js", out)
        self.assertIn("releases v2", out)
        _, out, _ = self.run_cli("diff", slug)
        self.assertIn("+new", out)
        self.assertNotIn("README.md (", out)
        self.api.paths[f"repos/{slug}/commits/main"] = {"sha": "c" * 40}
        code, out, _ = self.run_cli("bump", slug)
        self.assertEqual(self.store.card(slug).data["commit"], "c" * 12)
        self.assertEqual(self.store.card(slug).data["stars"], 31000)

    def test_fetch_extracts_safely_and_digests(self):
        slug = "a/b"
        self.api.add(repo(slug))
        self.api.paths[f"repos/{slug}/commits/main"] = {"sha": "d" * 40}
        self.api.paths[f"repos/{slug}/tarball/{'d' * 40}"] = tarball(
            {"README.md": "# b", "src/main.py": "print(1)\n" * 100, "../evil.txt": "x"})
        code, out, _ = self.run_cli("fetch", slug)
        self.assertEqual(code, 0, out)
        dest = self.root / "cache" / "a__b@ddddddd"
        self.assertTrue((dest / "src/main.py").is_file())
        self.assertFalse((self.root / "cache" / "evil.txt").exists())
        self.assertIn("entry points: README.md, src/main.py", out)


class ExamineTests(unittest.TestCase):
    def test_guess_kind(self):
        g = examine.guess_kind
        self.assertEqual(g(["skills/x/SKILL.md", "README.md"], {}, "x", "")[0], "skill")
        self.assertEqual(g(["a/SKILL.md", "b/SKILL.md"], {}, "x", "")[0], "skill-pack")
        big = ["SKILL.md"] + [f"examples/e{i}.tsx" for i in range(200)]
        self.assertEqual(g(big, {}, "x", "", "AI video skill for Claude Code")[0], "skill")
        self.assertEqual(g(big, {"package.json": "{}"}, "x", "", "Write HTML. Render video.")[0], "library")
        cli_with_skill = ["skills/a/SKILL.md", "package.json"] + [f"src/m{i}.ts" for i in range(50)]
        self.assertEqual(g(cli_with_skill, {"package.json": '{"bin": {"x": "c.js"}}'}, "x", "", "agent skill and CLI")[0], "cli")
        self.assertEqual(g(["src/index.ts"], {"package.json": '{"dependencies":{"@modelcontextprotocol/sdk":"1"}}'}, "x", "")[0], "mcp")
        self.assertEqual(g(["manifest.json"], {"manifest.json": '{"manifest_version":3}'}, "x", "")[0], "extension")
        self.assertEqual(g(["README.md"], {}, "awesome-things", "")[0], "list")
        self.assertEqual(g(["pyproject.toml", "pkg/a.py"], {"pyproject.toml": "[project.scripts]\nx='a:b'"}, "x", "")[0], "cli")
        self.assertEqual(g(["pyproject.toml", "pkg/a.py"], {"pyproject.toml": "[project]"}, "x", "")[0], "library")

    def test_watched_globs(self):
        files = ["clis/reddit/read.js", "src/daemon.ts", "docs/a.md", "skills/x/SKILL.md"]
        self.assertEqual(examine.watched(files, ["clis/reddit/**", "src/daemon.ts", "skills/"]),
                         ["clis/reddit/read.js", "src/daemon.ts", "skills/x/SKILL.md"])

    def test_clean_readme_drops_badges_and_html(self):
        text = '<p align="center"><img src="x"></p>\n# T\n[![b](u)](v)\n\n\n\nBody\n```\n<keep>\n```\n'
        out = examine.clean_readme(text, 1000)
        self.assertNotIn("img", out)
        self.assertIn("<keep>", out)
        self.assertNotIn("\n\n\n", out)


if __name__ == "__main__":
    unittest.main()
